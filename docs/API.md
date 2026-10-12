# 本机 API

[返回首页](../README.md)

默认根地址为 `http://127.0.0.1:8765`。启动后可从 [/openapi.json](http://127.0.0.1:8765/openapi.json) 取得机器可读的接口模式。本项目的界面与接口文档不需要加载外部 CDN；使用本页说明调用接口即可。

本机 API 面向桌面工具，不提供多用户认证或公网部署配置。写入请求如果携带 `Origin`，必须与当前服务地址相同。

## 接口一览

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 应用名、版本、运行状态、是否使用 AI；`title_matching: "strict-v1"` 表示已加载新版标题规则 |
| GET | `/api/sample` | 读取公开输入示例 |
| GET | `/api/abbreviations` | 缩写数量及 BibTeX 字符串定义 |
| GET | `/api/jobs` | 最近 100 个任务摘要 |
| POST | `/api/jobs` | 解析输入并保存新任务，不立即抓取 |
| GET | `/api/jobs/{id}` | 任务状态、条目和统计 |
| POST | `/api/jobs/{id}/start` | 排队执行／继续／重试失败条目 |
| POST | `/api/jobs/{id}/cancel` | 停止当前任务 |
| GET | `/api/jobs/{id}/events` | 实时事件流或事件分页 |
| GET | `/api/jobs/{id}/responses/{sha256}` | 查看属于该任务的响应正文 |
| GET | `/api/jobs/{id}/export` | 下载合并 BibTeX、ZIP 或日志 |

## 创建任务

JSON 参数：

| 字段 | 类型 | 默认 |
| --- | --- | --- |
| `text` | string，必填 | UTF-8 解码后的 BibTeX |
| `filename` | string | `references.bib` |
| `sources` | string[] | `["crossref", "datacite", "arxiv", "dblp"]` |
| `mailto` | string | 空 |
| `cache` | boolean | `false` |
| `keep_keys` | boolean | `true` |

输入限 5 MB、3,000 条；创建时至少启用一个有效来源。参数或 BibTeX 语法错误返回 422。响应中的 `id` 用于后续操作。任务详情省略原始输入全文，完整输入可从导出包取得。

下面的客户端示例会在运行时真实发起抓取：

```python
import time
from pathlib import Path

import httpx

base = "http://127.0.0.1:8765"
with httpx.Client(base_url=base, timeout=120) as client:
    sample = client.get("/api/sample")
    sample.raise_for_status()
    created = client.post(
        "/api/jobs",
        json={
            "text": sample.json()["text"],
            "filename": "sample.bib",
            "sources": ["crossref", "datacite", "arxiv", "dblp"],
        },
    )
    created.raise_for_status()
    job_id = created.json()["id"]
    client.post(f"/api/jobs/{job_id}/start").raise_for_status()
    while True:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        if job["state"] not in {"running", "queued"}:
            break
        time.sleep(1)
    result = client.get(
        f"/api/jobs/{job_id}/export",
        params={
            "format": "zip",
            "include_url": "false",
            "abbreviate": "true",
        },
    )
    result.raise_for_status()
    Path("bibtex-fetch-results.zip").write_bytes(result.content)
    print(job["counts"])
```

## 事件流

`GET /api/jobs/{id}/events?stream=true&after=0` 返回 `text/event-stream`。每条 SSE 的 `id` 为任务内递增序号，`data` 为 JSON 事件；支持 `Last-Event-ID` 断线续读。界面通过 EventSource 使用该接口。

`stream=false` 返回最多 1,000 条 JSON 事件。下一页使用上一页最后一条的 `seq` 作为 `after`；没有新事件时返回空数组。流不会因任务完成而自动关闭，客户端可读取任务状态后主动关闭。

共同字段为 `seq`、`time`、`kind`、`row_id`、`entry_key`、`message`。具体事件可能包含 `url`、`status`、`elapsed_ms`、`sha256`、`hits` 或 `rule`。不要假定每种事件都有全部字段。

标题匹配事件：`no_title_match` 表示无同名候选，`ambiguous_title` 表示多个不同记录同名，`title_match`／`title_mismatch` 表示下载后标题一致／不一致，`title_unavailable` 表示输入没有标题。下载后比较事件包含 `input_title`、`downloaded_title`、两个 `normalized_*_title` 及响应 `sha256`。被拒绝的响应仍可从日志中的哈希读取。

新抓取成功的条目会包含 `title_match: "matched"` 或 `"not_checked"`；后者仅用于没有输入标题的标识符／记录链接直取。旧成功条目没有这个字段，不能视为已通过新版标题匹配。未匹配与歧义最终未能从其他来源取到结果时仍使用 `status: "failed"`，原因和各次尝试在日志中。

## 下载与导出

`/responses/{sha256}` 返回 UTF-8 原文。加 `?download=bib` 或 `?download=txt` 触发附件下载。只有在当前任务事件中出现过的哈希可被读取；未找到返回 404。

`/export` 参数：

| 参数 | 值 | 含义 |
| --- | --- | --- |
| `format` | `bib` / `zip` / `log` | 默认 `bib` |
| `include_url` | `true` / `false` | 是否保留 URL |
| `abbreviate` | `true` / `false` | 是否使用缩写 |
| `include_unfetched` | `true` / `false` | 默认 `true`，保留未抓取输入并标记来源；`false` 只导出成功条目 |

未指定格式选项时使用任务中保存的默认值；GUI 创建的任务默认保留 URL、不缩写、保留未抓取输入，旧任务同样默认保留未抓取输入。显式查询参数只影响本次导出，不修改下载原文。只有关闭 `include_unfetched` 且无成功条目时，导出 `bib` 才返回 409；仍可下载 ZIP 或日志。`/health` 的 `complete_export: "v1"` 表示支持完整导出。

2.0.3 的 `/api/health` 另返回 `export_formatting: "v2"`，表示服务已加载扩展缩写与会议／预印本类型兼容规则。新版网页会提示重启旧服务。类型转换和触发原因写入 `formatting.json` 的 `entry_type` 动作，详见 [LaTeX 导出规则](LATEX.md#来源条目类型兼容)。

所有 `merged.bib` 自动执行 [LaTeX 兼容处理](LATEX.md)，不需要额外参数。直接下载 `bib` 与 ZIP 中的合并文件使用同一流程。`formatting.json` 中 `latex_compatibility` 固定为 `true`，`changes` 的 `latex_compatibility` 动作记录具体字段的 `before` / `after`；原始响应下载保持不变。

常见状态码：`403` 跨来源写入、`404` 任务／响应不存在、`409` 任务已运行／无可处理条目／尚无成功结果、`413` 请求长度超限、`422` 参数或输入错误。
