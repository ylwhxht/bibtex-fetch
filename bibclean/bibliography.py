from __future__ import annotations

import calendar
import hashlib
import html
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import unquote

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from pylatexenc.latex2text import LatexNodes2Text


class BibError(ValueError):
    pass


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    value = str(value or "")
    if re.search(r"</?[A-Za-z][^>]*>", value):
        parser = PlainHTML()
        parser.feed(value)
        value = "".join(parser.parts)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalized(value):
    value = LatexNodes2Text().latex_to_text(plain(value))
    value = unicodedata.normalize("NFKD", value).casefold()
    return " ".join(
        "".join(c if c.isalnum() else " " for c in value if not unicodedata.combining(c)).split()
    )


def doi_of(value):
    value = unquote(str(value or "")).strip().strip("{}")
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", value, flags=re.I)
    # Do not strip punctuation from a DOI suffix: it can be part of the identifier.
    if re.fullmatch(r"10\.\d{4,9}/[^\s<>\"{}]+", value, re.I):
        return value.lower()
    return ""


def arxiv_of(value):
    value = unquote(str(value or "")).strip().strip("{}")
    value = re.sub(
        r"^(?:https?://(?:export\.)?arxiv\.org/(?:abs|pdf)/|arxiv\s*:\s*)", "", value, flags=re.I
    )
    value = re.sub(r"\.pdf$", "", value, flags=re.I)
    return (
        value
        if re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", value, re.I)
        else ""
    )


def input_ids(entry):
    doi = doi_of(entry.get("doi")) or doi_of(entry.get("url"))
    arxiv = arxiv_of(entry.get("eprint")) or arxiv_of(entry.get("url"))
    if not arxiv and doi.startswith("10.48550/arxiv."):
        arxiv = arxiv_of(doi.split("arxiv.", 1)[1])
    return doi, arxiv


def _blocks(text, positions=False):
    """Scan entry boundaries, including nested braces and quoted values.

    bibtexparser treats malformed entries as implicit comments. Counting scanned
    blocks against parsed entries prevents silent partial imports.
    """
    blocks, i, n = [], 0, len(text)
    while i < n:
        if text[i] == "%":
            end = text.find("\n", i)
            i = n if end < 0 else end + 1
            continue
        if text[i] != "@":
            i += 1
            continue
        match = re.match(r"@\s*([A-Za-z][\w-]*)\s*([{(])", text[i:])
        if not match:
            # Email addresses and prose outside entries are legal comments.
            i += 1
            continue
        start = i
        typ, opener = match.groups()
        i += match.end()
        braces, quoted = (1 if opener == "{" else 0), False
        outer = braces
        while i < n:
            ch = text[i]
            if ch == "\\":
                i += 2
                continue
            if ch == '"' and braces == outer:
                quoted = not quoted
            elif ch == "{":
                braces += 1
            elif ch == "}":
                braces -= 1
                if braces < 0:
                    raise BibError(f"第 {text.count(chr(10), 0, i) + 1} 行的花括号不匹配。")
                if opener == "{" and braces == 0 and not quoted:
                    i += 1
                    break
            elif ch == ")" and opener == "(" and braces == 0 and not quoted:
                i += 1
                break
            i += 1
        else:
            raise BibError(f"第 {text.count(chr(10), 0, start) + 1} 行开始的 @{typ} 未闭合。")
        blocks.append((typ.lower(), start, i) if positions else (typ.lower(), text[start:i]))
    return blocks


def parse_bib(text, limit=3000, raw_strings=False):
    if len(text.encode("utf-8")) > 5_000_000:
        raise BibError("文件超过 5 MB，请拆分后导入。")
    blocks = _blocks(text.lstrip("\ufeff"))
    raw_entries = [raw for typ, raw in blocks if typ not in {"comment", "preamble", "string"}]
    if len(raw_entries) > limit:
        raise BibError(f"单次最多 {limit} 条，请拆分文献库。")
    parser = BibTexParser(
        ignore_nonstandard_types=False,
        common_strings=True,
        interpolate_strings=not raw_strings,
        add_missing_from_crossref=False,
    )
    # Crossref also returns bare full month names such as month=June. These are
    # only expanded in the parsed view; the original response is never rewritten.
    parser.bib_database.strings.update({name.lower(): name for name in calendar.month_name if name})
    parser.bib_database.strings["sept"] = "September"
    try:
        db = parser.parse(text, partial=False)
    except Exception as exc:
        raise BibError(f"BibTeX 解析失败：{exc}") from exc
    if len(db.entries) != len(raw_entries):
        # Removing a sole URL field can leave a valid empty entry. The upstream
        # parser silently skips these; restore their keys without adding fields.
        empty = [
            re.fullmatch(r"@\s*([\w-]+)\s*([{(])\s*([^\s,{}()]+)\s*,\s*([})])", raw)
            for raw in raw_entries
        ]
        empty = [m if m and (m[2], m[4]) in {("{", "}"), ("(", ")")} else None for m in empty]
        if len(db.entries) + sum(m is not None for m in empty) == len(raw_entries):
            parsed_entries = iter(db.entries)
            db.entries = [
                {"ENTRYTYPE": m[1].lower(), "ID": m[3]} if m else next(parsed_entries)
                for m in empty
            ]
    if len(db.entries) != len(raw_entries):
        raise BibError(
            "发现无法解析的条目，请检查字段逗号、引号、花括号或字符串宏。未进行部分导入。"
        )
    if not db.entries:
        raise BibError(
            "没有找到文章条目，请输入 @article、@inproceedings 或 @misc 等 BibTeX 条目。"
        )
    rows, used = [], set()
    for index, (entry, raw) in enumerate(zip(db.entries, raw_entries)):
        if raw_strings:
            # Source records may rely on external string macros. Syntactic
            # parsing need not resolve them in order to save the original text.
            entry = dict(entry)
            for field, value in entry.items():
                if hasattr(value, "get_value"):
                    try:
                        entry[field] = value.get_value()
                    except (KeyError, RecursionError):
                        entry[field] = str(value)
        original_key = entry["ID"]
        base = re.sub(r"[^\w:./+\-]", "_", original_key, flags=re.UNICODE) or f"ref{index + 1}"
        key, count = base, 2
        while key.casefold() in used:
            key, count = f"{base}_{count}", count + 1
        used.add(key.casefold())
        notes = []
        if key != original_key:
            notes.append(f"引用键已调整为 {key}，原键保存在引用键映射中。")
        if entry.get("crossref"):
            notes.append("包含 BibTeX crossref 继承；检索仅采用本条目显式字段，原始库完整保留。")
        rows.append(
            {
                "id": index,
                "key": key,
                "original_key": original_key,
                "original": entry,
                "raw": raw,
                "notes": notes,
                "status": "pending",
                "errors": [],
                "raw_bibtex": None,
            }
        )
    return rows


def render_entries(entries):
    db = BibDatabase()
    db.entries = entries
    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = None
    writer.display_order = [
        "title",
        "author",
        "journal",
        "booktitle",
        "year",
        "volume",
        "number",
        "pages",
        "publisher",
        "doi",
        "eprint",
        "archiveprefix",
        "primaryclass",
        "url",
    ]
    return bibtexparser.dumps(db, writer=writer)


def fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
