"""Aggregate downloaded source text; never generate bibliographic fields."""

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


def export_files(
    job, store, *, include_url=None, abbreviate=None, include_unfetched=None, tpami_minimal=None
):
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
        "tpami_minimal": job["settings"].get("tpami_minimal", False)
        if tpami_minimal is None
        else tpami_minimal,
    }
    formatting_options = {
        name: options[name] for name in ("include_url", "abbreviate", "tpami_minimal")
    }
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
                ],
                report,
            ),
            "README.txt": (
                "merged.bib: downloaded BibTeX plus original unfetched inputs by default, in input order. No fields are generated.\n"
                "Input fallbacks have explicit comments and do not count as successful retrievals. Disable include_unfetched for downloaded entries only.\n"
                "downloaded.bib: only successfully downloaded entries, with the same export formatting.\n"
                "export-summary.json: counts and each row's downloaded/input/omitted origin.\n"
                "entries/: exact UTF-8 source response text, without citation-key changes.\n"
                "Citation keys may change in merged.bib; see key-map.csv. Duplicate keys gain suffixes.\n"
                f"Export options: include_url={options['include_url']}, abbreviate={options['abbreviate']}, include_unfetched={options['include_unfetched']}, tpami_minimal={options['tpami_minimal']}.\n"
                "TPAMI minimal, when enabled, overrides URL and acronym options with IEEE word abbreviations, >6 authors -> first and others, optional print details omitted, online locators retained.\n"
                "TPAMI minimal is a formatting preset, not publication verification or a guarantee of manuscript compliance. See manual-review.md for unresolved formatting gaps.\n"
                "Optional formatting removes URL fields and/or replaces known journal/booktitle names with the supplied abbreviations.\n"
                "Abbreviations are written as braced text values, without external string-macro dependencies.\n"
                "All merged exports apply LaTeX compatibility: full month tokens, supported Unicode text, and special text characters.\n"
                "Existing math, commands, URL/DOI identifiers and raw responses are retained. Unknown Unicode and external macros may need template support.\n"
                "formatting.json: exact field edits in merged.bib. Other files retain their original content.\n"
                "Each input entry remains independent; there is no paper deduplication.\n"
                "failed.bib: original unsuccessful/unprocessed entries, with string macros expanded.\n"
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
    if options["abbreviate"] and not options["tpami_minimal"]:
        files["abbreviations.bib"] = string_definitions()
    if options["tpami_minimal"]:
        notes = [c for c in formatting_changes if c["action"] == "manual_review"]
        lines = [
            "# TPAMI 精简格式：需手动调整的项目",
            "",
            "以下仅检查现有字段和缩写表，不做文献真实性核验，也不自动补造数据。",
            "原始作者及全部来源字段保存在 original.bib、entries/ 中；字段修改见 formatting.json。",
            "配合期刊提供的 IEEE LaTeX 模板和参考文献样式使用；最终排版由模板决定。",
            "",
        ]
        for note in notes:
            key = str(note["exported_key"]).replace("`", "'").replace("\n", " ")
            lines.append(f"- 第 {note['row']} 条 `{key}` / {note['field']}：{note['reason']}")
        if not notes:
            lines.append("未发现此格式预设能识别的待处理项目；这不等同于完成投稿核验。")
        files["manual-review.md"] = "\n".join(lines) + "\n"
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
