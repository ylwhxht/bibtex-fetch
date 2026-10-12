"""Apply export options and LaTeX compatibility to exact source field spans."""

from __future__ import annotations

import re

from .abbreviations import abbreviation
from .bibliography import _blocks, parse_bib
from .latex_compat import compatible_expression


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


def format_bibtex(raw, *, include_url=True, abbreviate=False):
    parsed = iter(parse_bib(raw, raw_strings=True)) if abbreviate else None
    blocks = list(_blocks(raw, positions=True))
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
        values = next(parsed)["original"] if parsed is not None else {}
        for field, removal_start, removal_end, value_start, value_end, comments in _fields(
            raw, start, end
        ):
            expression = raw[value_start:value_end]
            replacement = expression
            if field == "url" and not include_url:
                edits.append((removal_start, removal_end, comments))
                changes.append(
                    {"field": field, "action": "remove", "before": expression, "after": ""}
                )
                continue
            if abbreviate and field in {"journal", "journaltitle", "booktitle"}:
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
