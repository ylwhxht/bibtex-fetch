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


def export_files(job, store, *, include_url=None, abbreviate=None):
    bibs, failed, mapping, report, files = [], [], [], [], {}
    used = set()
    keep_keys = job["settings"].get("keep_keys", True)
    options = {
        "include_url": job["settings"].get("include_url", True)
        if include_url is None
        else include_url,
        "abbreviate": job["settings"].get("abbreviate", False)
        if abbreviate is None
        else abbreviate,
    }
    formatting_changes = []
    for row in job["rows"]:
        key = ""
        if row["status"] == "success":
            raw = row["raw_bibtex"]
            base = row["key"] if keep_keys else row["source_key"]
            key, count = base, 2
            while key.casefold() in used:
                key, count = f"{base}_{count}", count + 1
            used.add(key.casefold())
            formatted, changes = format_bibtex(raw, **options)
            bibs.append(formatted if key == row["source_key"] else rewrite_key(formatted, key))
            formatting_changes.extend(
                {"row": row["id"] + 1, "exported_key": key, **change} for change in changes
            )
            safe_name = re.sub(r"[^\w.-]", "_", row["key"])[:90]
            files[f"entries/{row['id'] + 1:04d}-{safe_name}.bib"] = raw
        else:
            failed.append(dict(row["original"], ID=row["key"]))
        mapping.append(
            [row["id"] + 1, row["original_key"], row.get("source_key", ""), key, row["status"]]
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
            ]
        )
    events = store.events(job["id"])
    files.update(
        {
            "merged.bib": "\n\n".join(bibs),
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
            "key-map.csv": csv_text(
                ["row", "input_key", "source_key", "exported_key", "status"], mapping
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
                ],
                report,
            ),
            "README.txt": (
                "merged.bib: successfully downloaded BibTeX, in input order. No fields are generated.\n"
                "entries/: exact UTF-8 source response text, without citation-key changes.\n"
                "Citation keys may change in merged.bib; see key-map.csv. Duplicate keys gain suffixes.\n"
                f"Export options: include_url={options['include_url']}, abbreviate={options['abbreviate']}.\n"
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
                "When an input title is supplied, downloaded BibTeX must match it before acceptance.\n"
                "Rows without an input title use direct identifiers/record URLs and log title_unavailable.\n"
                "Older saved successes are not retroactively title-checked; see results.json and process.jsonl.\n"
                "No authenticity evaluation, scoring, manual approval, or AI generation is performed.\n"
                "This export is a snapshot; pending entries have not been fetched yet.\n"
            ),
        }
    )
    if options["abbreviate"]:
        files["abbreviations.bib"] = string_definitions()
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
