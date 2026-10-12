from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .abbreviations import VENUES, string_definitions
from .bibliography import BibError
from .config import SAMPLE_FILE, STATIC_DIR, data_directory
from .exports import export_files, zip_bytes
from .runner import Runner, new_job
from .storage import Store

STORE = Store(data_directory())
JOBS = {job["id"]: job for job in STORE.jobs() if job.get("mode") == "crawl"}
TASKS = {}
WORK_LOCK = asyncio.Lock()


@asynccontextmanager
async def lifespan(app):
    for job in JOBS.values():
        job["event_count"] = STORE.last_seq(job["id"])
        if job["state"] in {"running", "queued"}:
            job["state"] = "interrupted"
            for row in job["rows"]:
                if row["status"] == "processing":
                    row["status"] = "pending"
            Runner(STORE, job).emit("interrupted", "上次运行中断；可以继续未完成条目")
            STORE.save_job(job)
    yield
    tasks = list(TASKS.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(
    title="BibTeX Fetch",
    version=__version__,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
)


@app.middleware("http")
async def local_only(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "仅允许本机界面发起操作"}, status_code=403)
        try:
            if int(request.headers.get("content-length", "0")) > 7_000_000:
                return JSONResponse({"detail": "请求超过 7 MB"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "请求长度无效"}, status_code=400)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    return response


class ImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5_000_000)
    filename: str = Field(default="references.bib", max_length=200)
    sources: list[str] = Field(default_factory=lambda: ["crossref", "datacite", "arxiv", "dblp"])
    mailto: str = Field(default="", max_length=254)
    cache: bool = False
    keep_keys: bool = True


def get_job(job_id):
    if job_id not in JOBS:
        raise HTTPException(404, "未找到任务")
    return JOBS[job_id]


def snapshot(job):
    value = {k: v for k, v in job.items() if k != "original_text"}
    counts = {status: 0 for status in ["pending", "processing", "success", "failed"]}
    for row in job["rows"]:
        counts[row["status"]] += 1
    value.update(
        counts=counts, total=len(job["rows"]), processed=counts["success"] + counts["failed"]
    )
    return value


async def run_job(job):
    try:
        async with WORK_LOCK:
            await Runner(STORE, job).run()
    except asyncio.CancelledError:
        if job["state"] == "queued":
            job["state"] = "cancelled"
            Runner(STORE, job).emit("job_cancelled", "排队任务已停止")
            STORE.save_job(job)
    finally:
        TASKS.pop(job["id"], None)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "app": "bibtex-fetch",
        "version": __version__,
        "ai": False,
        "title_matching": "strict-v1",
        "complete_export": "v1",
        "export_formatting": "v2",
        "tpami_minimal": "v1",
    }


@app.get("/api/sample")
async def sample():
    return {"text": SAMPLE_FILE.read_text(encoding="utf-8")}


@app.get("/api/abbreviations")
async def abbreviations():
    return {"count": len(VENUES), "bibtex": string_definitions()}


@app.get("/api/jobs")
async def list_jobs():
    return [
        {
            "id": j["id"],
            "filename": j["filename"],
            "state": j["state"],
            "created_at": j["created_at"],
            "total": len(j["rows"]),
        }
        for j in sorted(JOBS.values(), key=lambda j: j["created_at"], reverse=True)[:100]
    ]


@app.post("/api/jobs")
async def import_job(body: ImportRequest):
    sources = list(dict.fromkeys(body.sources))
    if not sources or set(sources) - {"crossref", "datacite", "arxiv", "dblp"}:
        raise HTTPException(422, "请至少启用一个有效来源")
    mailto = body.mailto.strip()
    if mailto and not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", mailto):
        raise HTTPException(422, "联系邮箱格式不正确，可留空")
    try:
        job = new_job(
            body.text,
            body.filename,
            {
                "sources": sources,
                "mailto": mailto,
                "cache": body.cache,
                "keep_keys": body.keep_keys,
            },
        )
    except BibError as exc:
        raise HTTPException(422, str(exc)) from exc
    JOBS[job["id"]] = job
    STORE.save_job(job)
    return snapshot(job)


@app.get("/api/jobs/{job_id}")
async def read_job(job_id: str):
    return snapshot(get_job(job_id))


@app.post("/api/jobs/{job_id}/start")
async def start_job(job_id: str):
    job = get_job(job_id)
    if job_id in TASKS:
        raise HTTPException(409, "任务已在运行")
    for row in job["rows"]:
        if row["status"] in {"failed", "processing"}:
            row.update(status="pending", reason="", errors=[], raw_bibtex=None)
    if not any(row["status"] == "pending" for row in job["rows"]):
        raise HTTPException(409, "全部条目已抓取成功")
    job["state"] = "queued"
    STORE.save_job(job)
    TASKS[job_id] = asyncio.create_task(run_job(job))
    return snapshot(job)


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = get_job(job_id)
    if task := TASKS.get(job_id):
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        TASKS.pop(job_id, None)
        if job["state"] in {"queued", "running"}:
            job["state"] = "cancelled"
            Runner(STORE, job).emit("job_cancelled", "任务已停止")
            STORE.save_job(job)
    return snapshot(job)


@app.get("/api/jobs/{job_id}/events")
async def events(job_id: str, request: Request, after: int = 0, stream: bool = True):
    get_job(job_id)
    if not stream:
        return STORE.events(job_id, after=max(0, after), limit=1000)
    try:
        cursor = max(after, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        cursor = max(0, after)

    async def generate():
        nonlocal cursor
        idle = 0
        while not await request.is_disconnected():
            for event in STORE.events(job_id, after=cursor, limit=250):
                cursor = event["seq"]
                yield f"id: {cursor}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                idle = 0
            idle += 1
            if idle >= 30:
                yield ": keepalive\n\n"
                idle = 0
            await asyncio.sleep(0.3)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/jobs/{job_id}/responses/{digest}")
async def response_body(job_id: str, digest: str, download: str = ""):
    get_job(job_id)
    if download not in {"", "bib", "txt"}:
        raise HTTPException(422, "下载格式为 bib 或 txt")
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or not any(
        e.get("sha256") == digest for e in STORE.events(job_id)
    ):
        raise HTTPException(404, "此任务没有该响应")
    response = STORE.evidence(digest)
    if not response:
        raise HTTPException(404, "响应原文不存在")
    headers = (
        {"Content-Disposition": f'attachment; filename="source.{download}"'} if download else {}
    )
    return Response(response["body"], media_type="text/plain; charset=utf-8", headers=headers)


@app.get("/api/jobs/{job_id}/export")
async def export_job(
    job_id: str,
    format: str = "bib",
    include_url: bool | None = None,
    abbreviate: bool | None = None,
    include_unfetched: bool | None = None,
    tpami_minimal: bool | None = None,
):
    job = get_job(job_id)
    if format not in {"bib", "zip", "log"}:
        raise HTTPException(422, "支持 bib、zip 或 log")
    retain = (
        job["settings"].get("include_unfetched", True)
        if include_unfetched is None
        else include_unfetched
    )
    if (
        format == "bib"
        and not retain
        and not any(row["status"] == "success" for row in job["rows"])
    ):
        raise HTTPException(409, "暂时没有成功抓取的 BibTeX")
    files = export_files(
        job,
        STORE,
        include_url=include_url,
        abbreviate=abbreviate,
        include_unfetched=include_unfetched,
        tpami_minimal=tpami_minimal,
    )
    name, media, data = {
        "bib": ("merged.bib", "application/x-bibtex", files["merged.bib"]),
        "log": ("process.jsonl", "application/x-ndjson", files["process.jsonl"]),
        "zip": ("bibtex-fetch-results.zip", "application/zip", None),
    }[format]
    return Response(
        zip_bytes(files) if format == "zip" else data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
