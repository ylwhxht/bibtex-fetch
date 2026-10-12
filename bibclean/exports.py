"""Aggregate source text with traceable formatting; never invent metadata."""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile

from .abbreviations import string_definitions
from .bibliography import render_entries
from .crawler import rewrite_key
from .formatting import format_bibtex


def csv_text(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(
        [("'" + str(v)) if str(v).startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in row]
        for row in rows
    )
    return "\ufeff" + stream.getvalue()


def export_files(job, store, *, include_url=None, abbreviate=None, include_unfetched=None):
    bibs, downloaded, failed, mapping, report, files = [], [], [], [], [], {}
    used = set()
    keep_keys = job["settings"].get("keep_keys", True)
    options = {
        "include_url": job["settings"].get("include_url", True)
        if include_url is None
        else include_url,
        "abbreviate": job["settings"].get("abbreviate", False)
        if abbreviate is None
        else abbreviate,
        "include_unfetched": job["settings"].get("include_unfetched", True)
        if include_unfetched is None
        else include_unfetched,
    }
    formatting_options = {name: options[name] for name in ("include_url", "abbreviate")}
    formatting_changes = []
    provenance = []
    for row in job["rows"]:
        key = ""
        success = row["status"] == "success"
        origin = "downloaded" if success else "input" if options["include_unfetched"] else "omitted"
        if not success:
            failed.append(dict(row["original"], ID=row["key"]))
        if origin != "omitted":
            base = row["key"] if keep_keys or not success else row["source_key"]
            key, count = base, 2
            while key.casefold() in used:
                key, count = f"{base}_{count}", count + 1
            used.add(key.casefold())
        if success:
            raw = row["raw_bibtex"]
            safe_name = re.sub(r"[^\w.-]", "_", row["key"])[:90]
            files[f"entries/{row['id'] + 1:04d}-{safe_name}.bib"] = raw
        elif origin == "input":
            # Input strings were expanded on import; keep every input field.
            # Never substitute a rejected response or fabricate missing data.
            raw = render_entries([dict(row["original"], ID=key)])
        if origin != "omitted":
            formatted, changes = format_bibtex(raw, **formatting_options)
            if success and key != row["source_key"]:
                formatted = rewrite_key(formatted, key)
            if success:
                downloaded.append(formatted)
            else:
                formatted = (
                    f"% BibTeX Fetch: original input retained; not downloaded (row {row['id'] + 1}).\n"
                    + formatted
                )
            bibs.append(formatted)
            formatting_changes.extend(
                {"row": row["id"] + 1, "exported_key": key, "origin": origin, **change}
                for change in changes
            )
        provenance.append(
            {
                "row": row["id"] + 1,
                "input_key": row["original_key"],
                "exported_key": key,
                "retrieval_status": row["status"],
                "origin": origin,
            }
        )
        mapping.append(
            [
                row["id"] + 1,
                row["original_key"],
                row.get("source_key", ""),
                key,
                row["status"],
                origin,
            ]
        )
        report.append(
            [
                row["id"] + 1,
                row["key"],
                row["status"],
                row["original"].get("title", ""),
                row.get("source_title", ""),
                row.get("source", ""),
                row.get("source_url", ""),
                row.get("reason", ""),
                origin,
                row.get("failure_code", ""),
            ]
        )
    retained = sum(p["origin"] == "input" for p in provenance)
    merged = "\n\n".join(bibs)
    if retained:
        merged = (
            f"% BibTeX Fetch: {len(bibs)} entries; {len(downloaded)} downloaded; "
            f"{retained} retained from input (not downloaded).\n\n" + merged
        )
    events = store.events(job["id"])
    files.update(
        {
            "merged.bib": merged,
            "downloaded.bib": "\n\n".join(downloaded),
            "failed.bib": render_entries(failed),
            "original.bib": job["original_text"],
            "process.jsonl": "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events),
            "results.json": json.dumps(
                {**job, "export_options": options}, ensure_ascii=False, indent=2
            ),
            "formatting.json": json.dumps(
                {"options": options, "latex_compatibility": True, "changes": formatting_changes},
                ensure_ascii=False,
                indent=2,
            ),
            "export-summary.json": json.dumps(
                {
                    "input_count": len(job["rows"]),
                    "exported_count": len(bibs),
                    "downloaded_count": len(downloaded),
                    "retained_input_count": retained,
                    "omitted_count": len(job["rows"]) - len(bibs),
                    "rows": provenance,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "key-map.csv": csv_text(
                ["row", "input_key", "source_key", "exported_key", "status", "export_origin"],
                mapping,
            ),
            "report.csv": csv_text(
                [
                    "row",
                    "input_key",
                    "status",
                    "input_title",
                    "downloaded_title",
                    "source",
                    "url",
                    "error",
                    "export_origin",
                    "failure_code",
                ],
                report,
            ),
            "README.txt": (
                "merged.bib: downloaded BibTeX plus original unfetched inputs by default, in input order. No metadata is invented.\n"
                "Input fallbacks have explicit comments and do not count as successful retrievals. Disable include_unfetched for downloaded entries only.\n"
                "downloaded.bib: only successfully downloaded entries, with the same export formatting.\n"
                "export-summary.json: counts and each row's downloaded/input/omitted origin.\n"
                "entries/: exact UTF-8 source response text, without citation-key changes.\n"
                "Citation keys may change in merged.bib; see key-map.csv. Duplicate keys gain suffixes.\n"
                f"Export options: include_url={options['include_url']}, abbreviate={options['abbreviate']}, include_unfetched={options['include_unfetched']}.\n"
                "Existing explicit arXiv identifiers are also exposed in howpublished/note for classic BibTeX styles, independently of URL/abbreviation options.\n"
                "Missing or conflicting arXiv identifiers are not guessed; see formatting-review.md.\n"
                "Optional formatting removes URL fields and/or replaces known journal/booktitle names with the supplied abbreviations.\n"
                "Abbreviations are written as braced text values, without external string-macro dependencies.\n"
                "All merged exports apply LaTeX compatibility: full month tokens, supported Unicode text, and special text characters.\n"
                "Existing math, commands, URL/DOI identifiers and raw responses are retained. Unknown Unicode and external macros may need template support.\n"
                "formatting.json: exact field edits in merged.bib. Other files retain their original content.\n"
                "Each input entry remains independent; there is no paper deduplication.\n"
                "failed.bib: original unsuccessful/unprocessed entries, with string macros expanded.\n"
                "retrieval-review.md: unsuccessful entries, source failure reasons and ambiguous candidates for manual follow-up.\n"
                "original.bib: the full input text.\n"
                "process.jsonl: actual search, HTTP, redirect, retry, cache and download events.\n"
                "responses/: decoded UTF-8 HTTP bodies, named by SHA-256 of their UTF-8 bytes.\n"
                "Current retrieval rule: direct identifier first; title search requires a unique same-title record. No first-result fallback.\n"
                "When an input title is supplied, downloaded BibTeX must match it before acceptance. Rejected responses are never substituted for input fallbacks.\n"
                "Rows without an input title use direct identifiers/record URLs and log title_unavailable.\n"
                "Older saved successes are not retroactively title-checked; see results.json and process.jsonl.\n"
                "No authenticity evaluation, scoring, manual approval, or AI generation is performed.\n"
                "This export is a snapshot; pending entries have not been fetched yet.\n"
            ),
        }
    )

    def display(value):
        return str(value).replace("`", "'").replace("\r", " ").replace("\n", " ")

    lines = [
        "# 未抓取条目与手动处理清单",
        "",
        "这里只整理本次真实请求的结果；没有修改输入，没有生成或猜测文献字段。",
        "访问受限、限流及网络错误可稍后重试；同标题多版本或标题文字差异需自行确认。",
        "修正输入或补充确定的 DOI / arXiv 编号后，可重新导入；原始输入见 original.bib。",
        "",
    ]
    for row in job["rows"]:
        if row["status"] == "success":
            continue
        lines.extend(
            [
                f"## {row['id'] + 1}. `{display(row['original_key'])}`",
                "",
                f"标题：`{display(row['original'].get('title', ''))}`",
                "",
                f"原因：`{display(row.get('reason') or '尚未抓取')}`",
                "",
            ]
        )
        for issue in row.get("issues", []):
            lines.append(f"- {display(issue['source'])}：`{display(issue['message'])}`")
            if issue.get("downloaded_title"):
                lines.append(f"- 来源标题：`{display(issue['downloaded_title'])}`")
            if issue.get("url"):
                lines.append(f"- 请求地址：`{display(issue['url'])}`")
            for hit in issue.get("candidates", []):
                lines.append(
                    f"- 待选记录：`{display(hit['id'])}` / `{display(hit['title'])}` / "
                    f"`{display(hit['bib_url'])}`"
                )
        lines.append("")
    if all(row["status"] == "success" for row in job["rows"]):
        lines.append("没有未抓取条目。")
    files["retrieval-review.md"] = "\n".join(lines) + "\n"
    if options["abbreviate"]:
        files["abbreviations.bib"] = string_definitions()
    notes = [c for c in formatting_changes if c["action"] == "manual_review"]
    if notes:
        lines = [
            "# 导出格式：需手动调整的项目",
            "",
            "以下条目的 arXiv 编号缺失或冲突，程序保留现有字段，没有猜测编号。",
            "原始输入与来源分别保存在 original.bib、entries/ 中；格式调整见 formatting.json。",
            "",
        ]
        for note in notes:
            key = str(note["exported_key"]).replace("`", "'").replace("\n", " ")
            lines.append(f"- 第 {note['row']} 条 `{key}` / {note['field']}：{note['reason']}")
        files["formatting-review.md"] = "\n".join(lines) + "\n"
    for digest in {e["sha256"] for e in events if "sha256" in e}:
        response = store.evidence(digest)
        if response:
            files[f"responses/{digest}.txt"] = response["body"]
    return files


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()
