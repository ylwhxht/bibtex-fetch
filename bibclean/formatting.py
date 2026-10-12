"""Apply export options and LaTeX compatibility to exact source field spans."""

from __future__ import annotations

import re

from .abbreviations import CONFERENCES, abbreviation
from .bibliography import _blocks, arxiv_of, doi_of, parse_bib
from .latex_compat import compatible_expression
from .tpami import compact_author, removable_fields, review_notes, venue_name


def _fields(raw, start, end):
    header = re.match(r"@\s*[\w-]+\s*[{(][^,]*,", raw[start:end])
    if not header:
        return
    segment_start = start + header.end()
    i, depth, quoted = segment_start, 0, False
    boundaries = []
    while i < end - 1:
        char = raw[i]
        if char == "\\":
            i += 2
            continue
        if char == "%" and depth == 0 and not quoted:
            newline = raw.find("\n", i, end - 1)
            i = end - 1 if newline < 0 else newline + 1
            continue
        if char == '"' and depth == 0:
            quoted = not quoted
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0 and not quoted:
            boundaries.append((segment_start, i, i + 1))
            segment_start = i + 1
        i += 1
    boundaries.append((segment_start, end - 1, end - 1))
    for field_start, field_end, removal_end in boundaries:
        head = re.match(
            r"(?:\s|%[^\r\n]*(?:\r?\n|$))*([A-Za-z][\w-]*)\s*=\s*", raw[field_start:field_end]
        )
        if not head:
            continue
        value_start = field_start + head.end()
        # Exclude trailing whitespace and top-level comments from replacement.
        i, value_end, depth, quoted = value_start, value_start, 0, False
        while i < field_end:
            char = raw[i]
            if char == "%" and depth == 0 and not quoted:
                newline = raw.find("\n", i, field_end)
                i = field_end if newline < 0 else newline + 1
                continue
            if char == "\\":
                i = min(i + 2, field_end)
                value_end = i
                continue
            if char == '"' and depth == 0:
                quoted = not quoted
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            if not char.isspace():
                value_end = i + 1
            i += 1
        prefix = raw[field_start : field_start + head.start(1)]
        suffix = raw[value_end:field_end]
        comments = (prefix if "%" in prefix else "") + (suffix if "%" in suffix else "")
        yield head.group(1).lower(), field_start, removal_end, value_start, value_end, comments


def _preprint_repository(values):
    """Identify repositories from explicit identifiers, without adding metadata."""
    doi = doi_of(values.get("doi")) or doi_of(values.get("url"))
    if re.fullmatch(r"10\.36227/techrxiv\.\d+(?:\.\d+)?(?:(?:/v|\.v)\d+)?", doi):
        return "TechRxiv"
    ssrn = re.fullmatch(r"10\.2139/ssrn\.(\d+)", doi)
    if ssrn:
        return "SSRN " + ssrn[1]
    ident = ""
    if doi.startswith("10.48550/arxiv."):
        ident = arxiv_of(doi.split("arxiv.", 1)[1])
    elif values.get("archiveprefix", "").casefold() == "arxiv":
        ident = arxiv_of(values.get("eprint"))
    elif re.match(r"https?://(?:export\.)?arxiv\.org/(?:abs|pdf)/", values.get("url", ""), re.I):
        ident = arxiv_of(values["url"])
    return "arXiv:" + ident if ident else ""


def format_bibtex(raw, *, include_url=True, abbreviate=False, tpami_minimal=False):
    blocks = list(_blocks(raw, positions=True))
    # Parse a semantic view without top-level field comments, which the
    # upstream parser can mistake for malformed entries. Edits still target
    # exact spans in the untouched source, including all comments.
    semantic, entry_count = [], 0
    for typ, start, end in blocks:
        if typ == "string":
            semantic.append(raw[start:end])
        elif typ not in {"comment", "preamble"}:
            head = re.match(r"@\s*[\w-]+\s*[{(]([^,]*),", raw[start:end])
            fields = [f"{name}={raw[a:b]}" for name, _, _, a, b, _ in _fields(raw, start, end)]
            semantic.append(f"@{typ}{{{head[1]}," + ",\n".join(fields) + "}")
            entry_count += 1
    parsed = iter(parse_bib("\n".join(semantic), raw_strings=True)) if entry_count else iter(())
    defined_strings = set()
    for typ, start, end in blocks:
        if typ == "string":
            match = re.match(r"@\s*string\s*[{(]\s*([^\s=]+)\s*=", raw[start:end], re.I)
            if match:
                defined_strings.add(match.group(1).lower())
    edits, changes = [], []
    for typ, start, end in blocks:
        if typ in {"comment", "string", "preamble"}:
            continue
        values = next(parsed)["original"]
        fields = list(_fields(raw, start, end))
        expressions = {field: raw[a:b] for field, _, _, a, b, _ in fields}
        venue = abbreviation(values.get("booktitle", ""), expressions.get("booktitle", ""))
        repository = _preprint_repository(values)
        new_type = typ
        reason = ""
        if typ in {"inbook", "incollection"} and venue and venue[0] in CONFERENCES:
            new_type, reason = "inproceedings", "booktitle matches a known conference"
        elif (
            typ == "article"
            and repository
            and not any(
                values.get(f) for f in ("journal", "journaltitle", "booktitle", "crossref", "xdata")
            )
        ):
            new_type, reason = "misc", "repository identifier present; no journal supplied"
        if new_type != typ:
            head = re.match(r"@\s*([\w-]+)", raw[start:end])
            edits.append((start + head.start(1), start + head.end(1), new_type))
            changes.append(
                {
                    "field": "ENTRYTYPE",
                    "action": "entry_type",
                    "before": typ,
                    "after": new_type,
                    "reason": reason,
                }
            )
        # The explicit preset owns names and URL policy. Old switches resume
        # unchanged when it is disabled. Online-only locators must survive.
        removed = (
            removable_fields(new_type, values)
            if tpami_minimal
            else {"url"}
            if not include_url
            else set()
        )
        if tpami_minimal:
            changes.extend(
                {"field": field, "action": "manual_review", "reason": reason}
                for field, reason in review_notes(new_type, values)
            )
        for field, removal_start, removal_end, value_start, value_end, comments in fields:
            expression = raw[value_start:value_end]
            replacement = expression
            if field in removed:
                edits.append((removal_start, removal_end, comments))
                changes.append(
                    {
                        "field": field,
                        "action": "tpami_remove" if tpami_minimal else "remove",
                        "before": expression,
                        "after": "",
                    }
                )
                continue
            if tpami_minimal and field == "author":
                author = compact_author(values.get(field, ""))
                if author != values.get(field, ""):
                    replacement = "{" + author + "}"
                    changes.append(
                        {
                            "field": field,
                            "action": "tpami_authors",
                            "before": expression,
                            "after": replacement,
                            "reason": "more than six authors: first author and others",
                        }
                    )
            if (abbreviate or tpami_minimal) and field in {"journal", "journaltitle", "booktitle"}:
                lookup = venue_name if tpami_minimal else abbreviation
                match = lookup(values.get(field, ""), expression)
                if (
                    tpami_minimal
                    and field == "booktitle"
                    and not values.get("year")
                    and re.search(r"(?:19|20)\d{2}", values.get(field, ""))
                ):
                    # The name may be the only supplied publication date.
                    match = None
                if match:
                    macro, short = match
                    replacement = "{" + short + "}"
                    if expression != replacement:
                        changes.append(
                            {
                                "field": field,
                                "action": "tpami_abbreviate" if tpami_minimal else "abbreviate",
                                "key": macro,
                                "before": expression,
                                "after": replacement,
                            }
                        )
            compatible = compatible_expression(field, replacement, defined_strings)
            if compatible != replacement:
                changes.append(
                    {
                        "field": field,
                        "action": "latex_compatibility",
                        "before": replacement,
                        "after": compatible,
                    }
                )
                replacement = compatible
            if replacement != expression:
                edits.append((value_start, value_end, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    return raw, changes
