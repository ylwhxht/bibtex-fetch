"""The GUI and CLI share this sequential crawler and the same real event log."""

from __future__ import annotations

import asyncio
import uuid

from .bibliography import parse_bib
from .crawler import Crawler
from .transport import Fetcher, utcnow


def new_job(text, filename, settings):
    return {
        "id": uuid.uuid4().hex,
        "mode": "crawl",
        "filename": filename,
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "state": "ready",
        "original_text": text,
        "rows": parse_bib(text),
        "settings": settings,
        "event_count": 0,
        "request_count": 0,
    }


class Runner:
    def __init__(self, store, job, on_event=None):
        self.store, self.job, self.on_event = store, job, on_event
        self.row_id = None

    def emit(self, kind, message, **details):
        job = self.job
        job["event_count"] += 1
        if kind == "request":
            job["request_count"] += 1
        event = {
            "seq": job["event_count"],
            "time": utcnow(),
            "kind": kind,
            "row_id": self.row_id,
            "entry_key": job["rows"][self.row_id]["key"] if self.row_id is not None else None,
            "message": message,
            **details,
        }
        self.store.append_event(job["id"], event)
        if self.on_event:
            self.on_event(event)

    def save(self):
        self.job["updated_at"] = utcnow()
        self.store.save_job(self.job)

    async def run(self, fetcher=None):
        job = self.job
        fetcher = fetcher or Fetcher(
            self.store,
            self.emit,
            cache=job["settings"].get("cache", False),
            mailto=job["settings"].get("mailto", ""),
        )
        crawler = Crawler(fetcher, self.emit, job["settings"])
        job["state"] = "running"
        self.emit("job_start", "开始逐条检索与抓取", sources=job["settings"]["sources"])
        self.save()
        try:
            for row in job["rows"]:
                if row["status"] != "pending":
                    continue
                self.row_id = row["id"]
                row["status"] = "processing"
                self.save()
                try:
                    row.update(await crawler.crawl(row["original"]))
                except Exception as exc:
                    row.update(
                        status="failed", reason=f"{type(exc).__name__}: {exc}", raw_bibtex=None
                    )
                    self.emit("failure", "本条目处理失败，继续下一条", error=row["reason"])
                self.emit(
                    "row_done",
                    "本条目抓取完成" if row["status"] == "success" else "本条目未抓取成功",
                    status=row["status"],
                )
                self.save()
            job["state"] = "done"
            self.row_id = None
            self.emit("job_done", "全部条目已处理")
        except asyncio.CancelledError:
            job["state"] = "cancelled"
            for row in job["rows"]:
                if row["status"] == "processing":
                    row["status"] = "pending"
            self.emit("job_cancelled", "任务已停止；再次启动将处理未完成和失败条目")
            raise
        finally:
            await fetcher.close()
            self.save()
