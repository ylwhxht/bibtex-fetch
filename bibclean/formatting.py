"""Apply export options and LaTeX compatibility to exact source field spans."""

from __future__ import annotations

import re

from .abbreviations import CONFERENCE_TITLES, abbreviation
from .arxiv_display import display_field, identifier, labelled_ids
from .bibliography import _blocks, arxiv_of, doi_of, parse_bib
from .latex_compat import compatible_expression
from .publication_versions import publication_version


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


def format_bibtex(raw, *, include_url=True, abbreviate=False, input_key=None):
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
        publication, publication_issue = publication_version(values, input_key)
        overrides = publication["fields"] if publication else {}
        for issue in [publication_issue]:
            if issue:
                changes.append({"field": "ENTRYTYPE", "action": "manual_review", "reason": issue})
        effective = {**values, **overrides}
        venue = abbreviation(
            effective.get("booktitle", ""),
            "" if "booktitle" in overrides else expressions.get("booktitle", ""),
        )
        repository = _preprint_repository(values)
        arxiv_id, arxiv_issue = identifier(values) if not publication else ("", "")
        if arxiv_issue:
            changes.append({"field": "eprint", "action": "manual_review", "reason": arxiv_issue})
        new_type = typ
        reason = ""
        if publication:
            new_type, reason = "inproceedings", "explicitly requested official publication version"
        elif (
            typ == "article"
            and (repository or arxiv_id)
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
        removed = {"url"} if not include_url else set()
        if (
            abbreviate
            and new_type in {"inproceedings", "conference"}
            and venue
            and venue[0] in CONFERENCE_TITLES
        ):
            removed.add("publisher")
        if publication:
            # Remove only an arXiv-only display locator from an older export;
            # retain eprint/archivePrefix, links and all substantive notes.
            for field in ("note", "howpublished"):
                value = values.get(field, "").replace("{", "").replace("}", "").strip()
                ids = labelled_ids(value)
                if len(ids) == 1 and re.fullmatch(r"arxiv\s*:\s*" + re.escape(ids[0]), value, re.I):
                    removed.add(field)
        locator_field = display_field(values, new_type, arxiv_id) if arxiv_id else ""
        locator = "{{arXiv}:" + arxiv_id + "}"
        additions = []
        for field, value in overrides.items():
            if field not in expressions:
                replacement = "{" + value + "}"
                additions.append(f"\n  {field} = {replacement},")
                changes.append(
                    {
                        "field": field,
                        "action": "published_version",
                        "before": "",
                        "after": replacement,
                        "reason": "explicitly requested official publication version",
                        "source": publication["source"],
                    }
                )
        if locator_field and locator_field not in expressions:
            additions.append(f"\n  {locator_field} = {locator},")
            changes.append(
                {
                    "field": locator_field,
                    "action": "arxiv_display",
                    "before": "",
                    "after": locator,
                    "reason": "print existing arXiv identifier in classic BibTeX styles",
                }
            )
        if additions:
            head = re.match(r"@\s*[\w-]+\s*[{(][^,]*,", raw[start:end])
            position = start + head.end()
            edits.append((position, position, "".join(additions)))
        for field, removal_start, removal_end, value_start, value_end, comments in fields:
            expression = raw[value_start:value_end]
            replacement = expression
            if field in removed:
                edits.append((removal_start, removal_end, comments))
                changes.append(
                    {
                        "field": field,
                        "action": "remove",
                        "before": expression,
                        "after": "",
                        "reason": (
                            "listed conference; publisher redundant with standardized proceedings title"
                            if field == "publisher"
                            else "official conference version uses its venue instead of an arXiv-only note"
                            if publication and field in {"note", "howpublished"}
                            else "URL option disabled"
                        ),
                    }
                )
                continue
            if field in overrides:
                replacement = "{" + overrides[field] + "}"
                if replacement != expression:
                    changes.append(
                        {
                            "field": field,
                            "action": "published_version",
                            "before": expression,
                            "after": replacement,
                            "reason": "explicitly requested official publication version",
                            "source": publication["source"],
                        }
                    )
            if field == locator_field:
                replacement = (
                    expression + " # {; " + locator[1:-1] + "}" if values.get(field) else locator
                )
                changes.append(
                    {
                        "field": field,
                        "action": "arxiv_display",
                        "before": expression,
                        "after": replacement,
                        "reason": "print existing arXiv identifier in classic BibTeX styles",
                    }
                )
            if (
                abbreviate
                and field in {"journal", "journaltitle", "booktitle"}
                and field not in overrides
            ):
                match = abbreviation(values.get(field, ""), expression)
                if match:
                    macro, short = match
                    replacement = "{" + short + "}"
                    if expression != replacement:
                        changes.append(
                            {
                                "field": field,
                                "action": "abbreviate",
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
