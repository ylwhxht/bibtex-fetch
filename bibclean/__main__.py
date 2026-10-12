"""python -m bibclean references.bib -o output --sources crossref arxiv"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .bibliography import BibError
from .config import data_directory
from .exports import export_files, zip_bytes
from .runner import Runner, new_job
from .storage import Store


def main():
    # Both streams must remain UTF-8 when redirected on Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="逐条检索并下载原站 BibTeX，同时输出实际过程日志。"
    )
    parser.add_argument("--version", action="version", version=f"BibTeX Fetch {__version__}")
    parser.add_argument("input", type=Path, help="UTF-8 BibTeX 输入文件")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output") / datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["crossref", "datacite", "arxiv", "dblp"],
        default=["crossref", "datacite", "arxiv", "dblp"],
    )
    parser.add_argument("--cache", action="store_true", help="启用 24 小时缓存，命中时明确记录")
    parser.add_argument(
        "--source-keys", action="store_true", help="使用来源引用键，重复键自动添加后缀"
    )
    parser.add_argument(
        "--no-url", action="store_true", help="合并文件移除 URL 字段，保留 DOI 及抓取原文"
    )
    parser.add_argument(
        "--abbreviate", action="store_true", help="按内置名称表缩写合并文件的期刊和会议名称"
    )
    parser.add_argument("--mailto", default="", help="传给 Crossref 的联系邮箱，可选")
    parser.add_argument(
        "--data-dir", type=Path, default=data_directory(), help="本地任务和缓存目录"
    )
    args = parser.parse_args()
    try:
        text = args.input.read_text(encoding="utf-8-sig")
        job = new_job(
            text,
            args.input.name,
            {
                "sources": args.sources,
                "mailto": args.mailto,
                "cache": args.cache,
                "keep_keys": not args.source_keys,
                "include_url": not args.no_url,
                "abbreviate": args.abbreviate,
            },
        )
    except (OSError, UnicodeError, BibError) as exc:
        parser.error(str(exc))
    store = Store(args.data_dir)
    store.save_job(job)
    code = 0
    try:
        asyncio.run(
            Runner(store, job, lambda e: print(json.dumps(e, ensure_ascii=False), flush=True)).run()
        )
    except KeyboardInterrupt:
        code = 130
    files = export_files(job, store)
    for name, content in files.items():
        target = args.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="")
    (args.output / "bibtex-fetch-results.zip").write_bytes(zip_bytes(files))
    success = sum(row["status"] == "success" for row in job["rows"])
    print(
        f"已下载 {success}/{len(job['rows'])} 条。输出目录：{args.output.resolve()}",
        file=sys.stderr,
    )
    return code or (0 if success == len(job["rows"]) else 2)


if __name__ == "__main__":
    raise SystemExit(main())
