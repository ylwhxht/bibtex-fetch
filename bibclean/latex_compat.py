"""Deterministic BibTeX/LaTeX syntax fixes; never supply bibliographic metadata."""

from __future__ import annotations

import calendar
import re
import unicodedata
from functools import lru_cache

from pylatexenc.latexencode import UnicodeToLatexEncoder

# Identifiers (URL, DOI, eprint, crossref, etc.) keep their literal spelling.
TEXT_FIELDS = frozenset(
    "author editor title subtitle booktitle booksubtitle journal journaltitle "
    "shorttitle publisher school institution organization address location series "
    "note howpublished type chapter pages volume number edition month year "
    "annotation abstract keywords collection".split()
)
MONTHS = {name.lower(): name for name in calendar.month_name if name}
MONTHS["sept"] = "September"
ENCODER = UnicodeToLatexEncoder(
    non_ascii_only=True,
    replacement_latex_protection="braces-all",
    unknown_char_policy="keep",
    unknown_char_warning=False,
)
PUNCTUATION = {
    "\u2013": "--",
    "\u2014": "---",
    "\u2018": "`",
    "\u2019": "'",
    "\u201c": "``",
    "\u201d": "''",
    "\u00a0": "~",
}


@lru_cache(maxsize=4096)
def _unicode(char):
    # Outer braces are essential when a .bst abbreviates an accented first name.
    return PUNCTUATION.get(char, ENCODER.unicode_to_latex(char))


def _group_end(text, start):
    """End (exclusive) of a balanced braced group, or None."""
    if start >= len(text) or text[start] != "{":
        return None
    depth, i = 1, start + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def _closing(text, token, start):
    """Find an unescaped math delimiter; escaped dollar signs are literal."""
    i = start
    while i < len(text):
        if text.startswith(token, i):
            return i + len(token)
        i += 2 if text[i] == "\\" else 1
    return None


def latex_text(text):
    """Escape text, preserving existing commands, paired math and URL arguments.

    This is deliberately not a general TeX interpreter. Unknown Unicode is kept,
    never replaced by a question mark or guessed transliteration.
    """
    text = unicodedata.normalize("NFC", text)
    out, i = [], 0
    while i < len(text):
        char = text[i]
        if char == "\\":
            command = re.match(r"\\([A-Za-z]+\*?|.)", text[i:], re.S)
            if not command:
                out.append(char)
                i += 1
                continue
            name = command.group(1)
            end = i + command.end()
            if name in {"url", "path", "nolinkurl", "href", "detokenize", "ensuremath"}:
                arg = end
                while arg < len(text) and text[arg].isspace():
                    arg += 1
                end = _group_end(text, arg) or end
            elif name in {"verb", "verb*"} and end < len(text):
                delimiter = text[end]
                found = text.find(delimiter, end + 1)
                if found >= 0:
                    end = found + 1
            elif name in {"(", "["}:
                end = _closing(text, "\\)" if name == "(" else "\\]", end) or end
            out.append(text[i:end])
            i = end
            continue
        if char == "$":
            delimiter = "$$" if text.startswith("$$", i) else "$"
            end = _closing(text, delimiter, i + len(delimiter))
            if end:
                out.append(text[i:end])
                i = end
                continue
            out.append(r"\$")
        elif char in "_&%#":
            out.append("\\" + char)
        elif char == "^":
            out.append(r"{\textasciicircum}")
        elif ord(char) > 127:
            out.append(_unicode(char))
        else:
            out.append(char)
        i += 1
    return "".join(out)


def compatible_expression(field, expression, defined_strings=()):
    """Edit literal parts of a BibTeX expression, retaining # concatenation/macros."""
    if field not in TEXT_FIELDS:
        return expression
    out, i = [], 0
    while i < len(expression):
        char = expression[i]
        if char == "{":
            end = _group_end(expression, i)
            if end is None:
                return expression
            out.append("{" + latex_text(expression[i + 1 : end - 1]) + "}")
            i = end
        elif char == '"':
            end, depth = i + 1, 0
            while end < len(expression):
                if expression[end] == "\\":
                    end += 2
                    continue
                if expression[end] == "{":
                    depth += 1
                elif expression[end] == "}":
                    depth -= 1
                elif expression[end] == '"' and depth == 0:
                    break
                end += 1
            if end == len(expression):
                return expression
            out.append('"' + latex_text(expression[i + 1 : end]) + '"')
            i = end + 1
        elif char == "%":
            end = expression.find("\n", i)
            end = len(expression) if end < 0 else end + 1
            out.append(expression[i:end])
            i = end
        elif char.isalpha():
            token = re.match(r"[\w:./+\-]+", expression[i:]).group()
            name = token.lower()
            # Built-in jun/jul remain valid; nonstandard June/July become literals.
            out.append(
                "{" + MONTHS[name] + "}"
                if field == "month" and name in MONTHS and name not in defined_strings
                else token
            )
            i += len(token)
        else:
            out.append(char)
            i += 1
    return "".join(out)
