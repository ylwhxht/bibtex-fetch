"""HTTP transport with real, durable request/response events."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

import httpx

from . import __version__
from .bibliography import fingerprint

HOSTS = {
    "api.crossref.org",
    "api.datacite.org",
    "data.datacite.org",
    "data.crosscite.org",
    "arxiv.org",
    "export.arxiv.org",
    "dblp.org",
    "dblp.dagstuhl.de",
}
LAST_REQUEST = {}


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class FetchError(RuntimeError):
    pass


class Fetcher:
    def __init__(self, store, emit, *, cache=False, mailto="", client=None):
        self.store, self.emit, self.cache, self.mailto = store, emit, cache, mailto
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=10),
            follow_redirects=False,
            headers={
                "User-Agent": f"BibTeX-Fetch/{__version__}"
                + (f" (mailto:{mailto})" if mailto else "")
            },
        )

    async def close(self):
        await self.client.aclose()

    async def get(self, url, params=None, accept="application/json"):
        params = dict(params or {})
        if urlsplit(url).hostname == "api.crossref.org" and self.mailto:
            params["mailto"] = self.mailto
        current = str(httpx.URL(url, params=params))
        cache_key = fingerprint(current + "\n" + accept)
        if self.cache and (cached := self.store.cached(cache_key, time.time())):
            self.emit(
                "cache",
                "命中本地缓存，本次未发送 HTTP 请求",
                url=current,
                sha256=cached["sha256"],
                retrieved_at=cached["retrieved_at"],
                bytes=len(cached["body"].encode("utf-8")),
            )
            return dict(cached, cached=True)
        for redirect in range(5):
            parsed = urlsplit(current)
            if (
                parsed.scheme != "https"
                or parsed.hostname not in HOSTS
                or parsed.port not in {None, 443}
                or parsed.username
            ):
                raise FetchError("请求或跳转地址不在已支持来源中：" + current)
            host = parsed.hostname
            response = None
            for attempt in range(2):
                delay = 3.1 if host in {"arxiv.org", "export.arxiv.org"} else 1.1
                wait = max(0, LAST_REQUEST.get(host, 0) + delay - time.monotonic())
                if wait > 0.05:
                    self.emit(
                        "wait",
                        f"遵守来源请求间隔，等待 {wait:.1f} 秒",
                        host=host,
                        seconds=round(wait, 2),
                    )
                    await asyncio.sleep(wait)
                LAST_REQUEST[host] = time.monotonic()
                started = time.monotonic()
                self.emit(
                    "request",
                    "发送 HTTP GET",
                    method="GET",
                    url=current,
                    accept=accept,
                    attempt=attempt + 1,
                )
                try:
                    async with self.client.stream(
                        "GET", current, headers={"Accept": accept}
                    ) as response:
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 4_000_000:
                                raise FetchError("响应超过 4 MB，已停止读取")
                            chunks.append(chunk)
                        body = b"".join(chunks).decode("utf-8", errors="strict")
                        data = {
                            "url": current,
                            "retrieved_at": utcnow(),
                            "sha256": fingerprint(body),
                            "body": body,
                            "content_type": response.headers.get("content-type", ""),
                            "status": response.status_code,
                            "cached": False,
                        }
                        # Keep failures/redirects too, so every completed response
                        # can be inspected. Only successful responses enter cache.
                        self.store.put_evidence(
                            cache_key
                            if response.status_code == 200
                            else "response:" + data["sha256"],
                            data,
                            time.time(),
                        )
                        self.emit(
                            "response",
                            f"收到 HTTP {response.status_code}",
                            url=current,
                            status=response.status_code,
                            elapsed_ms=round((time.monotonic() - started) * 1000),
                            bytes=size,
                            content_type=data["content_type"],
                            sha256=data["sha256"],
                        )
                        if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                            retry_after = response.headers.get("Retry-After", "2")
                            try:
                                seconds = float(retry_after)
                            except ValueError:
                                try:
                                    seconds = (
                                        parsedate_to_datetime(retry_after)
                                        - datetime.now(timezone.utc)
                                    ).total_seconds()
                                except (ValueError, TypeError):
                                    seconds = 2
                            if seconds > 25:
                                raise FetchError(
                                    f"HTTP {response.status_code}，来源要求 {int(seconds)} 秒后再试"
                                )
                            self.emit(
                                "retry",
                                f"来源暂时不可用，{max(1, seconds):.0f} 秒后重试",
                                seconds=max(1, seconds),
                                url=current,
                            )
                            await asyncio.sleep(max(1, seconds))
                            continue
                        break
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    self.emit(
                        "network_error",
                        str(exc) or type(exc).__name__,
                        url=current,
                        elapsed_ms=round((time.monotonic() - started) * 1000),
                    )
                    if attempt:
                        raise FetchError(f"{host} 连接失败：{type(exc).__name__}") from exc
                    self.emit("retry", "2 秒后重试连接", url=current, seconds=2)
                    await asyncio.sleep(2)
                except (httpx.HTTPError, UnicodeError) as exc:
                    self.emit("network_error", str(exc), url=current)
                    raise FetchError(str(exc)) from exc
            if response is None:
                raise FetchError("没有收到响应")
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise FetchError("跳转响应缺少 Location")
                target = urljoin(current, location)
                self.emit("redirect", "跟随来源返回的跳转", url=current, target=target)
                current = target
                continue
            if response.status_code != 200:
                raise FetchError(f"{host} HTTP {response.status_code}")
            self.store.put_evidence(cache_key, data, time.time())
            return data
        raise FetchError("来源跳转次数超过 5 次")
