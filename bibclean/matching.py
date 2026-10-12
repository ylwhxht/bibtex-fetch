"""Conservative title equality; no fuzzy matching or bibliographic synthesis."""

from __future__ import annotations

import html
import re
import unicodedata

from pylatexenc.latex2text import LatexNodes2Text


class _TitleText(LatexNodes2Text):
    def specials_node_to_text(self, node):
        # A plain-text ampersand is a title character, not a TeX table separator.
        if node.specials_chars == "&":
            return "&"
        return super().specials_node_to_text(node)

    def macro_node_to_text(self, node):
        # Unknown commands must not disappear and make unrelated titles equal.
        if self.latex_context.get_macro_spec(node.macroname) is None:
            return node.latex_verbatim()
        return super().macro_node_to_text(node)


def title_text(value):
    value = str(value or "")
    # Remove presentation tags only. Keep superscripts, subscripts and unknown
    # markup instead of flattening them into a potentially different title.
    value = re.sub(r"</?(?:i|b|em|strong|span|italic|bold)\b[^>]*>", "", value, flags=re.I)
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = html.unescape(value)
    return " ".join(
        _TitleText(keep_comments=True, math_mode="verbatim").latex_to_text(value).split()
    )


def normalized_title(value):
    """Ignore case, display syntax, whitespace and one terminal full stop.

    Keep meaningful punctuation, accents, numbers, subtitles and math. This is
    intentionally stricter than the normalization used for venue abbreviations.
    """
    value = unicodedata.normalize("NFC", title_text(value))
    # Publishers sometimes put a plain method name in a math font. Only unwrap
    # a complete font-wrapped word, never a variable, expression or script.
    value = re.sub(
        r"\$\{?\\(?:mathsf|mathrm|mathbf|mathtt)\{([A-Za-z][A-Za-z0-9]{2,})\}\}?\$",
        r"\1",
        value,
    )
    # Case is significant inside mathematical expressions (e.g. X versus x).
    parts = re.split(r"(\$\$.*?\$\$|\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\])", value)

    def prose(part):
        part = part.translate(str.maketrans("‘’“”", "''\"\""))
        # Retain the hyphen and plus themselves. Do not turn A-B into AB, or
        # change a mathematical minus sign into a hyphen.
        part = re.sub(r"(?<=\w)[‐‑–](?=\w)", "-", part)
        part = re.sub(r"\s*\+\s*", "+", part)
        return part.casefold()

    value = "".join(part if i % 2 else prose(part) for i, part in enumerate(parts))
    return value.removesuffix(".").strip()


def same_title(left, right):
    left, right = normalized_title(left), normalized_title(right)
    return bool(left and right and left == right)
