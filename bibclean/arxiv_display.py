"""Expose existing arXiv identifiers to classic BibTeX styles; never invent IDs."""

from __future__ import annotations

import re

from .bibliography import arxiv_of, doi_of

LABELLED_ID = re.compile(
    r"\barxiv\s*:\s*((?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z]{2})?/\d{7})(?:v\d+)?)(?![\w./])",
    re.I,
)
ARXIV_URL = re.compile(r"https?://(?:export\.)?arxiv\.org/(?:abs|pdf)/", re.I)


def labelled_ids(value):
    # Braces protecting the proper name do not change its rendered text.
    return [m[1] for m in LABELLED_ID.finditer(value.replace("{", "").replace("}", ""))]


def identifier(values):
    """Return a source-derived ID or an explicit reason requiring manual input."""
    candidates = []
    declared = any(
        values.get(field, "").strip().casefold() == "arxiv"
        for field in ("archiveprefix", "eprinttype")
    )
    eprint = values.get("eprint", "")
    if declared or re.match(r"arxiv\s*:", eprint, re.I) or ARXIV_URL.match(eprint):
        candidates.append(arxiv_of(eprint))
    for field in ("doi", "url"):
        value = values.get(field, "")
        doi = doi_of(value)
        if doi.startswith("10.48550/arxiv."):
            candidates.append(arxiv_of(doi.split("arxiv.", 1)[1]))
        if ARXIV_URL.match(value):
            candidates.append(arxiv_of(value))
    for field in ("journal", "journaltitle", "note", "howpublished"):
        candidates.extend(labelled_ids(values.get(field, "")))
    candidates = list(dict.fromkeys(value for value in candidates if value))
    if not candidates:
        return "", "arXiv declared but no valid identifier supplied" if declared else ""
    bases = {re.sub(r"v\d+$", "", value, flags=re.I).casefold() for value in candidates}
    versions = {m[0].casefold() for value in candidates if (m := re.search(r"v\d+$", value, re.I))}
    if len(bases) > 1 or len(versions) > 1:
        return "", "conflicting arXiv identifiers: " + ", ".join(candidates)
    # A DOI can omit the version that is explicitly supplied in eprint/URL.
    return next(
        (value for value in candidates if re.search(r"v\d+$", value, re.I)), candidates[0]
    ), ""


def display_field(values, entry_type, ident):
    """Choose a field printed by classic styles, avoiding an existing locator."""
    visible = ["note"]
    if entry_type in {"misc", "online", "electronic"}:
        visible.append("howpublished")
    if entry_type == "article":
        visible.append("journal")
    if entry_type in {"inproceedings", "conference", "incollection", "inbook"}:
        visible.append("booktitle")
    if any(
        ident.casefold() == existing.casefold()
        for field in visible
        for existing in labelled_ids(values.get(field, ""))
    ):
        return ""
    return "note"
