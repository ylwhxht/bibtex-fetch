"""Opt-in, deterministic IEEE reference formatting; never supply missing metadata.

Policy and primary source: docs/TPAMI.md. These are word abbreviations, separate
from the user's acronym table. This is not a manuscript compliance checker.
"""

from __future__ import annotations

import re

from .abbreviations import VENUES, abbreviation, normalized
from .bibliography import doi_of

CONFERENCE_NAMES = {
    "ACCV": "Proc. Asian Conf. Comput. Vis.",
    "AAAI": "Proc. AAAI Conf. Artif. Intell.",
    "CVPRW": "Proc. Conf. Comput. Vis. Pattern Recognit. Workshops",
    "CVPR": "Proc. Conf. Comput. Vis. Pattern Recognit.",
    "ICCV": "Proc. Int. Conf. Comput. Vis.",
    "ECCV": "Proc. Eur. Conf. Comput. Vis.",
    "NIPS": "Adv. Neural Inf. Process. Syst.",
    "ICPR": "Proc. Int. Conf. Pattern Recognit.",
    "BMVC": "Proc. Brit. Mach. Vis. Conf.",
    "ACMMM": "Proc. ACM Int. Conf. Multimedia",
    "ICME": "Proc. IEEE Int. Conf. Multimedia Expo",
    "ICASSP": "Proc. IEEE Int. Conf. Acoust., Speech Signal Process.",
    "ICIP": "Proc. IEEE Int. Conf. Image Process.",
    "ICLR": "Proc. Int. Conf. Learn. Represent.",
    "IROS": "Proc. IEEE/RSJ Int. Conf. Intell. Robots Syst.",
    "ICRA": "Proc. IEEE Int. Conf. Robot. Autom.",
    "IJCAI": "Proc. Int. Joint Conf. Artif. Intell.",
    "WACV": "Proc. IEEE Winter Conf. Appl. Comput. Vis.",
    "EDGE": "Proc. ACM/IEEE Symp. Edge Comput.",
    "ICCVW": "Proc. Int. Conf. Comput. Vis. Workshops",
    "IV": "Proc. IEEE Intell. Vehicles Symp.",
    "ITSC": "Proc. IEEE Int. Conf. Intell. Transp. Syst.",
    "ICPRS": "Proc. Int. Conf. Pattern Recognit. Syst.",
    "ICVES": "Proc. IEEE Int. Conf. Veh. Electron. Saf.",
    "ICDL": "Proc. IEEE Int. Conf. Develop. Learn.",
    "ICTC": "Proc. Int. Conf. Inf. Commun. Technol. Converg.",
    "ICECET": "Proc. Int. Conf. Elect., Comput. Energy Technol.",
    "NNICE": "Proc. Int. Conf. Neural Netw., Inf. Commun. Eng.",
    "INDIN": "Proc. IEEE Int. Conf. Ind. Informat.",
    "SECON": "Proc. IEEE Int. Conf. Sens., Commun. Netw.",
    "ISAS": "Proc. Int. Symp. Auton. Syst.",
    "CCC": "Proc. Chin. Control Conf.",
    "RadarConf": "Proc. IEEE Radar Conf.",
    "VTCSpring": "Proc. IEEE Veh. Technol. Conf. (Spring)",
    "VTCFall": "Proc. IEEE Veh. Technol. Conf. (Fall)",
    "ICONIP": "Proc. Int. Conf. Neural Inf. Process.",
    "ECCVW": "Proc. Eur. Conf. Comput. Vis. Workshops",
    "GeMiC": "Proc. German Microw. Conf.",
    "CRV": "Proc. Conf. Comput. Robot Vis.",
    "MCSoC": "Proc. IEEE Int. Symp. Embedded Multicore/Many-core Syst.-on-Chip",
    "ICCRI": "Proc. Int. Conf. Control, Robot. Informat.",
    "ROBIO": "Proc. IEEE Int. Conf. Robot. Biomimetics",
    "VCIP": "Proc. Int. Conf. Vis. Commun. Image Process.",
    "CSCWD": "Proc. Int. Conf. Comput. Supported Cooperative Work Design",
    "IECON": "Proc. Annu. Conf. IEEE Ind. Electron. Soc.",
    "ICAUS": "Proc. Int. Conf. Auton. Unmanned Syst.",
    "ECSA": "Proc. Int. Electron. Conf. Sensors Appl.",
    "CoRL": "Proc. Conf. Robot Learn.",
    "EuRAD": "Proc. Eur. Radar Conf.",
}
JOURNAL_OVERRIDES = {
    "TOG": "ACM Trans. Graph.",
    "TCSVT": "IEEE Trans. Circuits Syst. Video Technol.",
    "SPL": "IEEE Signal Process. Lett.",
    "TVC": "Vis. Comput.",
    "JCST": "J. Comput. Sci. Technol.",
    "CVM": "Comput. Vis. Media",
    "RAL": "IEEE Robot. Autom. Lett.",
    "ISPRSARCH": "Int. Arch. Photogramm. Remote Sens. Spatial Inf. Sci.",
}
IEEE_NAMES = {
    key: CONFERENCE_NAMES.get(key, JOURNAL_OVERRIDES.get(key, short)) for key, short, _ in VENUES
}
# Computer-vision conference sponsorship changes over time. Retain a supplied
# IEEE/CVF or IEEE prefix; an acronym alone does not establish a sponsor/year.
SPONSOR_VARIANTS = {"CVPR", "CVPRW", "ICCV", "ICCVW", "WACV", "VCIP"}
IEEE_ALIASES = {normalized(name): (key, name) for key, name in IEEE_NAMES.items()}
AUTHOR_SEPARATOR = re.compile(r"\s+and\s+", re.I)
for _key in SPONSOR_VARIANTS:
    _base = IEEE_NAMES[_key].removeprefix("Proc. ").removeprefix("IEEE ")
    for _sponsor in ("", "IEEE ", "IEEE/CVF "):
        _name = "Proc. " + _sponsor + _base
        IEEE_ALIASES[normalized(_name)] = (_key, _name)


def venue_name(value, expression=""):
    """Exact known venues only. Unknown/joint events are returned unchanged."""
    existing = IEEE_ALIASES.get(normalized(value))
    if existing:
        return existing
    match = abbreviation(value, expression)
    if not match:
        return None
    key = match[0]
    name = IEEE_NAMES[key]
    if key in SPONSOR_VARIANTS:
        base = name.removeprefix("Proc. ").removeprefix("IEEE ")
        sponsor = (
            "IEEE/CVF "
            if re.search(r"IEEE\s*/\s*CVF", value, re.I)
            else ("IEEE " if re.search(r"\bIEEE\b", value, re.I) else "")
        )
        name = "Proc. " + sponsor + base
    return key, name


def split_authors(value):
    """Split only BibTeX's top-level 'and', preserving corporate/TeX groups."""
    names, start, depth, i = [], 0, 0, 0
    while i < len(value):
        if value[i] == "\\":
            i += 2
            continue
        if value[i] == "{":
            depth += 1
        elif value[i] == "}":
            depth -= 1
        if depth == 0 and value[i].isspace():
            match = AUTHOR_SEPARATOR.match(value, i)
            if match:
                names.append(value[start:i].strip())
                i = match.end()
                start = i
                continue
        i += 1
    names.append(value[start:].strip())
    return names


def compact_author(value):
    names = split_authors(value)
    people = [name for name in names if name.casefold() != "others"]
    if (len(people) > 6 or (len(people) == 6 and len(names) > 6)) and all(people):
        return people[0] + " and others"
    return value


def removable_fields(typ, values):
    """Omit only optional print details; online references keep their locator."""
    removed = set()
    doi = doi_of(values.get("doi"))
    conference = typ in {"conference", "inproceedings"}
    article = typ == "article"
    has_year = bool(values.get("year"))
    has_pages = any(values.get(f) for f in ("pages", "eid", "articleno"))
    complete_print = (
        has_year
        and has_pages
        and (
            (conference and values.get("booktitle"))
            or (article and values.get("journal") and values.get("volume"))
        )
    )
    # Do not treat early-access/unpublished items as final print references.
    early = any(
        re.search(r"early\s*access|in\s*press|to\s*appear|forthcoming", values.get(f, ""), re.I)
        for f in ("note", "pubstate", "howpublished")
    )
    if (article or conference) and complete_print and not early:
        removed.add("url")
    if conference and values.get("booktitle") and not early:
        removed.add("address")  # Conference location is explicitly optional.
        # Retain the publisher when this is a volume in a book/series.
        if not any(values.get(f) for f in ("series", "volume", "edition", "crossref", "xdata")):
            removed.update({"publisher", "organization"})
        # The proceedings-with-DOI basic format allows a year-only date.
        if doi and has_year:
            removed.add("month")
    return removed


def review_notes(typ, values):
    """Local formatting gaps only: no retrieval, inferred fields, or verification."""
    notes = []
    for field in ("author", "title", "year"):
        if not values.get(field):
            notes.append((field, f"缺少 {field}；请根据原始来源自行补齐。"))
    if typ == "article" and not values.get("journal"):
        notes.append(("journal", "缺少 journal；请确认条目类型或期刊信息，程序不会填造期刊名。"))
    if typ in {"inproceedings", "conference"} and not values.get("booktitle"):
        notes.append(("booktitle", "缺少 booktitle；请自行补充会议名称。"))
    venue_fields = ["journal", "journaltitle"]
    if typ in {"inproceedings", "conference"}:
        venue_fields.append("booktitle")
    for field in venue_fields:
        if values.get(field) and not venue_name(values[field]):
            notes.append((field, "名称不在规范词语缩写表中，已保留原文；请自行确认缩写。"))
    if typ in {"article", "inproceedings", "conference"}:
        if not any(values.get(f) for f in ("pages", "eid", "articleno")):
            notes.append(
                ("pages", "未提供页码或文章编号；请确认是否为 early access／无页码出版物。")
            )
    if (
        typ not in {"article", "inproceedings", "conference"}
        and (values.get("doi") or values.get("eprint"))
        and not values.get("url")
    ):
        notes.append(
            ("url", "在线来源只有 DOI／eprint；请确认模板会显示该标识，必要时自行添加来源 URL。")
        )
    if any(values.get(f) for f in ("crossref", "xdata")):
        notes.append(("crossref", "条目依赖外部共享字段，请在编译项目中保留被引用的父条目。"))
    if typ == "article" and not values.get("volume"):
        notes.append(("volume", "未提供卷号；请确认出版状态及期刊是否使用卷号。"))
    names = split_authors(values.get("author", ""))
    if any(name.casefold() == "others" for name in names) and 2 < len(names) < 7:
        notes.append(("author", "来源作者已被截断，无法确定是否超过 6 位；保留原样，请自行确认。"))
    return notes
