"""Deterministic search -> download original BibTeX. No verification or synthesis."""

from __future__ import annotations

import json
import re
from urllib.parse import quote, urlsplit

from defusedxml import ElementTree as ET

from .bibliography import (
    BibError,
    _blocks,
    arxiv_of,
    doi_of,
    input_ids,
    parse_bib,
)
from .matching import normalized_title, same_title, title_text
from .transport import FetchError


def rewrite_key(raw, key):
    """Change the citation key only. All source fields remain byte-for-byte text."""
    pattern = r"(@\s*[a-zA-Z][\w-]*\s*[{(]\s*)([^,\s]+)(\s*,)"
    for typ, start, end in _blocks(raw, positions=True):
        if typ not in {"comment", "string", "preamble"}:
            entry = re.sub(
                pattern, lambda m: m.group(1) + key + m.group(3), raw[start:end], count=1
            )
            return raw[:start] + entry + raw[end:]
    raise BibError("返回内容中没有可替换引用键的条目")


class Crawler:
    def __init__(self, fetcher, emit, settings):
        self.fetcher, self.emit, self.settings = fetcher, emit, settings
        self.sources = settings["sources"]

    def select(self, hits, title, source):
        self.emit(
            "search_results", f"{source} 返回 {len(hits)} 条检索结果", source=source, hits=hits
        )
        matches = [(i, h) for i, h in enumerate(hits) if same_title(h["title"], title)]
        if not matches:
            self.emit(
                "no_title_match",
                "没有标题一致的候选，跳过本来源；不使用首条或相似结果",
                source=source,
                input_title=title,
                normalized_input_title=normalized_title(title),
                rule="same_title_required",
            )
            return None
        if len({h["bib_url"] for _, h in matches}) > 1:
            self.emit(
                "ambiguous_title",
                "存在多个标题一致的不同记录，无法仅凭标题选定；跳过本来源",
                source=source,
                input_title=title,
                hits=[h for _, h in matches],
                rule="unique_same_title_required",
            )
            return None
        index, choice = matches[0]
        self.emit(
            "selection",
            f"选取第 {index + 1} 条搜索结果（标题一致，下载后仍须比较标题）",
            source=source,
            rank=index + 1,
            selected_title=choice["title"],
            target=choice["bib_url"],
            rule="same_title",
        )
        return choice

    async def crossref_search(self, title):
        query = title_text(title)[:600]
        self.emit("search", "按标题检索 Crossref", source="Crossref", query=query)
        result = await self.fetcher.get(
            "https://api.crossref.org/works",
            {"query.bibliographic": query, "rows": 5},
        )
        items = json.loads(result["body"])["message"]["items"]
        hits = []
        for item in items:
            doi = doi_of(item.get("DOI"))
            if doi:
                hits.append(
                    {
                        "title": str((item.get("title") or [""])[0]),
                        "id": doi,
                        "bib_url": "https://api.crossref.org/works/"
                        + quote(doi, safe="")
                        + "/transform/application/x-bibtex",
                    }
                )
        return self.select(hits, title, "Crossref")

    async def dblp_search(self, title):
        query = title_text(title)[:600]
        self.emit("search", "按标题检索 DBLP", source="DBLP", query=query)
        result = await self.fetcher.get(
            "https://dblp.org/search/publ/api",
            {"q": query, "format": "json", "h": 5},
        )
        records = json.loads(result["body"])["result"]["hits"].get("hit", [])
        records = [records] if isinstance(records, dict) else records
        hits = []
        for record in records:
            info = record.get("info", {})
            key = info.get("key", "")
            if key and re.fullmatch(r"[\w./:+-]+", key):
                hits.append(
                    {
                        "title": str(info.get("title", "")),
                        "id": key,
                        "bib_url": "https://dblp.org/rec/" + quote(key, safe="/") + ".bib",
                    }
                )
        return self.select(hits, title, "DBLP")

    async def arxiv_search(self, title):
        query = 'ti:"' + re.sub(r"[^\w\s-]", " ", title_text(title))[:600] + '"'
        self.emit("search", "按标题检索 arXiv", source="arXiv", query=query)
        result = await self.fetcher.get(
            "https://export.arxiv.org/api/query",
            {"search_query": query, "max_results": 5},
            "application/atom+xml",
        )
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(result["body"])
        hits = []
        for item in root.findall("a:entry", ns):
            link = item.findtext("a:id", "", ns)
            if "/api/errors" in link:
                raise FetchError("arXiv 查询错误：" + item.findtext("a:summary", "", ns))
            ident = arxiv_of(link)
            if ident:
                hits.append(
                    {
                        "title": item.findtext("a:title", "", ns),
                        "id": ident,
                        "bib_url": "https://arxiv.org/bibtex/" + quote(ident, safe="/"),
                    }
                )
        return self.select(hits, title, "arXiv")

    async def crawl(self, entry):
        errors, attempted = [], set()
        doi, arxiv = input_ids(entry)
        title = entry.get("title", "")
        self.emit(
            "entry",
            "开始处理输入条目",
            key=entry["ID"],
            title=entry.get("title", ""),
            doi=doi,
            arxiv=arxiv,
        )

        async def download(source, url):
            if url in attempted:
                self.emit("skip", "本条目已尝试过该地址，继续下一来源", source=source, url=url)
                return None
            attempted.add(url)
            try:
                result = await self.fetcher.get(
                    url, accept="application/x-bibtex, text/plain;q=0.9"
                )
                raw = result["body"]
                if result.get("content_type", "").split(";", 1)[0].strip().lower() in {
                    "text/html",
                    "application/xhtml+xml",
                } or re.match(r"\s*(?:<!doctype\s+html|<html)", raw, re.I):
                    raise FetchError("返回的是 HTML 页面，不是 BibTeX（可能为访问限制页面）")
                rows = parse_bib(raw, raw_strings=True)
                if len(rows) != 1:
                    raise FetchError(f"返回了 {len(rows)} 个 BibTeX 条目，无法按单条引用汇总")
                source_key = rows[0]["original_key"]
                source_title = rows[0]["original"].get("title", "")
                if str(title).strip():
                    matched = same_title(title, source_title)
                    self.emit(
                        "title_match" if matched else "title_mismatch",
                        "下载的 BibTeX 标题与输入一致"
                        if matched
                        else "下载的 BibTeX 标题缺失或不一致，拒绝汇总并继续下一来源",
                        source=source,
                        url=result["url"],
                        input_title=title,
                        downloaded_title=source_title,
                        normalized_input_title=normalized_title(title),
                        normalized_downloaded_title=normalized_title(source_title),
                        rule="downloaded_title_required",
                        sha256=result["sha256"],
                    )
                    if not matched:
                        raise FetchError("下载的 BibTeX 标题缺失或与输入不一致（未匹配）")
                    title_match = "matched"
                else:
                    title_match = "not_checked"
                    self.emit(
                        "title_unavailable",
                        "输入未提供标题，按已有标识或记录链接抓取；未进行标题比较",
                        source=source,
                        url=result["url"],
                        downloaded_title=source_title,
                        rule="input_title_unavailable",
                    )
                self.emit(
                    "bibtex",
                    "已取得原站 BibTeX，原文已保存",
                    source=source,
                    url=result["url"],
                    source_key=source_key,
                    bytes=len(raw.encode("utf-8")),
                    sha256=result["sha256"],
                    bibtex=raw,
                )
                return {
                    "status": "success",
                    "source": source,
                    "source_url": result["url"],
                    "source_key": source_key,
                    "raw_bibtex": raw,
                    "retrieved_at": result["retrieved_at"],
                    "sha256": result["sha256"],
                    "source_title": source_title,
                    "title_match": title_match,
                    "errors": errors,
                }
            except (FetchError, BibError, ValueError) as exc:
                errors.append({"source": source, "url": url, "message": str(exc)})
                self.emit(
                    "source_error", "抓取失败，尝试下一来源", source=source, url=url, error=str(exc)
                )
                return None

        if arxiv and "arxiv" in self.sources:
            self.emit("route", "输入含 arXiv 编号，直接请求原站 BibTeX", identifier=arxiv)
            if result := await download(
                "arXiv", "https://arxiv.org/bibtex/" + quote(arxiv, safe="/")
            ):
                return result
        if doi:
            for source, url in [
                (
                    "Crossref",
                    "https://api.crossref.org/works/"
                    + quote(doi, safe="")
                    + "/transform/application/x-bibtex",
                ),
                (
                    "DataCite",
                    "https://data.datacite.org/application/x-bibtex/" + quote(doi, safe=""),
                ),
            ]:
                if source.lower() in self.sources:
                    self.emit(
                        "route", "输入含 DOI，直接请求来源 BibTeX", source=source, identifier=doi
                    )
                    if result := await download(source, url):
                        return result
        input_url = urlsplit(entry.get("url", ""))
        if (
            "dblp" in self.sources
            and input_url.hostname in {"dblp.org", "dblp.dagstuhl.de"}
            and input_url.path.startswith("/rec/")
        ):
            path = re.sub(r"\.(html|bib)$", "", input_url.path)
            if result := await download("DBLP", "https://dblp.org" + path + ".bib"):
                return result
        if normalized_title(title):
            for key, source, search in [
                ("crossref", "Crossref", self.crossref_search),
                ("dblp", "DBLP", self.dblp_search),
                ("arxiv", "arXiv", self.arxiv_search),
            ]:
                if key not in self.sources:
                    continue
                try:
                    hit = await search(title)
                    if hit and (result := await download(source, hit["bib_url"])):
                        return result
                except (FetchError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
                    errors.append({"source": source, "message": str(exc)})
                    self.emit(
                        "source_error", "检索失败，尝试下一来源", source=source, error=str(exc)
                    )
        message = (
            "未匹配：没有抓取到标题一致且可解析的原站 BibTeX"
            if str(title).strip()
            else "没有抓取到可解析的原站 BibTeX"
            if doi or arxiv or title
            else "条目缺少可检索的 DOI、arXiv 编号或标题"
        )
        self.emit("failure", message, errors=errors)
        return {"status": "failed", "reason": message, "errors": errors, "raw_bibtex": None}
