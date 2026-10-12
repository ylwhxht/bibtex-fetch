"use strict";
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const states = {
  ready: "准备就绪",
  queued: "排队中",
  running: "抓取中",
  done: "已完成",
  cancelled: "已停止",
  interrupted: "可继续",
};
const rowStates = {
  pending: "等待中",
  processing: "正在抓取",
  success: "已抓取",
  failed: "失败",
};
const failureLabels = {
  ambiguous_title: "需选择版本",
  title_mismatch: "标题有差异",
  rate_limited: "来源限流",
  access_blocked: "访问受限",
  network_error: "网络失败",
  source_unavailable: "来源不可用",
  invalid_response: "响应异常",
  not_found: "未找到记录",
  missing_identifier: "缺少检索信息",
};
function rowLabel(row) {
  return row.status === "failed"
    ? failureLabels[row.failure_code] || "未抓取成功"
    : rowStates[row.status];
}
const kinds = {
  job_start: "START",
  entry: "ENTRY",
  route: "ROUTE",
  search: "SEARCH",
  search_fallback: "检索回退",
  source_unavailable: "访问受限",
  request: "GET",
  response: "HTTP",
  search_results: "RESULTS",
  selection: "SELECT",
  no_title_match: "未匹配",
  ambiguous_title: "同名歧义",
  title_match: "标题一致",
  title_mismatch: "标题不符",
  title_unavailable: "无输入标题",
  bibtex: "BIBTEX",
  source_error: "ERROR",
  failure: "FAILED",
  network_error: "NETWORK",
  retry: "RETRY",
  redirect: "REDIRECT",
  cache: "CACHE",
  cache_ignored: "跳过旧缓存",
  wait: "WAIT",
  skip: "SKIP",
  row_done: "DONE",
  job_done: "FINISH",
  job_cancelled: "STOP",
  interrupted: "RESUME",
};
let job = null,
  filename = "references.bib",
  events = [],
  eventSeq = 0,
  stream = null,
  filter = "all",
  generation = 0;
let toastTimer,
  logFrame,
  refreshTimer,
  fetching = false;
let titleMatchingReady = false;
let completeExportReady = false;
const emptyRecords = $("records").innerHTML;

function toast(message, error = false) {
  $("toast").textContent = message;
  $("toast").classList.toggle("error", error);
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 5000);
}
async function api(path, body) {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "请求失败，请检查输入内容。",
    );
  return data;
}
function listen(id, event, callback) {
  $(id).addEventListener(event, async (e) => {
    try {
      await callback(e);
    } catch (error) {
      toast(error.message, true);
    }
  });
}
async function checkServerRules() {
  const notice = $("server-notice");
  try {
    const health = await api("/api/health");
    titleMatchingReady = health.title_matching === "strict-v2";
    completeExportReady =
      health.complete_export === "v1" && health.export_formatting === "v3" &&
      health.arxiv_display === "v1";
    notice.textContent =
      "当前服务尚未加载新版导出或标题匹配规则。请先关闭正在运行的 BibTeX Fetch，再重新启动并刷新页面。";
  } catch {
    titleMatchingReady = false;
    completeExportReady = false;
    notice.textContent = "无法连接本地服务。请启动 BibTeX Fetch 后刷新页面。";
  }
  notice.hidden = titleMatchingReady && completeExportReady;
  render();
}
function timeLabel(value) {
  return new Date(value).toLocaleTimeString("zh-CN", { hour12: false });
}
function active() {
  return job && ["running", "queued"].includes(job.state);
}
function closeStream() {
  if (stream) stream.close();
  stream = null;
}
function connection(label, live = false) {
  $("connection").innerHTML = `<i></i>${esc(label)}`;
  $("connection").classList.toggle("live", live);
}
function render() {
  const counts = job?.counts || {
    success: 0,
    failed: 0,
    pending: 0,
    processing: 0,
  };
  $("stat-total").textContent = job?.total || 0;
  $("stat-success").textContent = counts.success;
  $("stat-failed").textContent = counts.failed;
  $("stat-requests").textContent = job?.request_count || 0;
  $("job-label").textContent = job
    ? `${job.filename} · ${job.total} 个条目`
    : "等待导入文献";
  $("job-state").textContent = job ? states[job.state] : "未开始";
  $("job-state").className =
    "status-badge " +
    (active() ? "processing" : job?.state === "done" ? "success" : "neutral");
  $("progress").value = job?.total ? (100 * job.processed) / job.total : 0;
  $("progress-text").textContent = job
    ? `已处理 ${job.processed} / ${job.total} · 成功 ${counts.success} · 失败 ${counts.failed}`
    : "导入后可查看全部文章列表。";
  $("start-button").disabled =
    !titleMatchingReady || !job || active() || counts.success === job.total;
  $("start-button").textContent =
    !job || job.state === "ready"
      ? "开始抓取 →"
      : counts.success === job.total
        ? "全部抓取完成 ✓"
        : job.state === "done"
          ? "重试失败条目 ↻"
          : "继续抓取 →";
  $("cancel-button").hidden = !active();
  const retain = $("include-unfetched").checked;
  const exportCount = retain ? job?.total || 0 : counts.success;
  $("export-bib").disabled = !completeExportReady || !exportCount;
  $("preview-export").disabled = !completeExportReady || !exportCount;
  $("export-zip").disabled = !completeExportReady || !job;
  $("download-log").disabled = !events.length;
  $("export-label").textContent = job
    ? retain
      ? `导出 ${exportCount} / ${job.total} 条 · 已抓取 ${counts.success} · 保留输入 ${job.total - counts.success}`
      : `导出 ${counts.success} / ${job.total} 条 · 将遗漏 ${job.total - counts.success} 条未抓取条目`
    : "等待导入文献";
  renderRows();
  if (job) {
    const selected = $("log-row").value;
    if ($("log-row").options.length !== job.rows.length + 1) {
      $("log-row").innerHTML =
        '<option value="all">全部条目</option>' +
        job.rows
          .map(
            (r) =>
              `<option value="${r.id}">${r.id + 1}. ${esc(r.key)}</option>`,
          )
          .join("");
      $("log-row").value = selected;
    }
  }
}
function renderRows() {
  if (!job) {
    $("records").innerHTML = emptyRecords;
    return;
  }
  const query = $("search").value.trim().toLowerCase();
  const rows = job.rows.filter(
    (r) =>
      (filter === "all" || r.status === filter) &&
      (!query ||
        `${r.key} ${r.original.title || ""} ${r.source_title || ""} ${r.reason || ""} ${rowLabel(r)}`
          .toLowerCase()
          .includes(query)),
  );
  $("records").innerHTML = rows.length
    ? rows
        .map(
          (r) =>
            `<div class="record-row" role="button" tabindex="0" data-row="${r.id}" aria-label="查看 ${esc(r.key)} 的抓取结果"><span class="record-number">${String(r.id + 1).padStart(2, "0")}</span><div class="record-body"><div class="record-top"><h3 class="record-title">${esc(r.original.title || "未提供标题")}</h3><span class="status-badge ${r.status}">${esc(rowLabel(r))}</span></div><div class="record-meta"><code>${esc(r.key)}</code><span>${esc(r.source || r.original.doi || r.original.eprint || "按标题检索")}</span></div>${r.status === "failed" && r.reason ? `<p class="record-reason">${esc(r.reason)}</p>` : ""}</div><span class="record-arrow">↗</span></div>`,
        )
        .join("")
    : '<div class="no-results">没有符合筛选条件的条目</div>';
}
async function history() {
  const list = await api("/api/jobs");
  $("history").innerHTML = list.length
    ? list
        .map(
          (j) =>
            `<button class="history-item ${job?.id === j.id ? "selected" : ""}" data-job="${esc(j.id)}">${esc(j.filename)}<small>${j.total} 个条目 · ${states[j.state]} · ${new Date(j.created_at).toLocaleDateString("zh-CN")}</small></button>`,
        )
        .join("")
    : '<p class="muted">还没有任务。<br>从一份 BibTeX 开始。</p>';
  return list;
}
async function refresh() {
  if (!job || fetching) return;
  const id = job.id,
    currentGeneration = generation;
  fetching = true;
  try {
    const data = await api(`/api/jobs/${id}`);
    if (generation === currentGeneration && job?.id === id) {
      job = data;
      render();
    }
  } finally {
    fetching = false;
  }
}
function scheduleRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(
    () => refresh().catch((e) => toast(e.message, true)),
    120,
  );
}
async function openJob(id) {
  const currentGeneration = ++generation;
  closeStream();
  events = [];
  eventSeq = 0;
  $("log-row").innerHTML = '<option value="all">全部条目</option>';
  const data = await api(`/api/jobs/${id}`);
  if (generation !== currentGeneration) return;
  job = data;
  localStorage.setItem("bibtex-fetch-job", id);
  render();
  renderLogs();
  let more = true;
  while (more) {
    const batch = await api(
      `/api/jobs/${id}/events?stream=false&after=${eventSeq}`,
    );
    if (generation !== currentGeneration) return;
    for (const event of batch) {
      events.push(event);
      eventSeq = event.seq;
    }
    more = batch.length === 1000;
  }
  renderLogs();
  render();
  if (active()) connect();
  else connection(events.length ? "历史记录" : "等待开始");
  await history();
}
function connect() {
  closeStream();
  if (!job) return;
  const id = job.id,
    currentGeneration = generation;
  const source = new EventSource(`/api/jobs/${id}/events?after=${eventSeq}`);
  stream = source;
  connection("连接中");
  source.onopen = () => {
    if (generation === currentGeneration) connection("实时连接", true);
  };
  source.onmessage = (message) => {
    if (generation !== currentGeneration) return;
    const event = JSON.parse(message.data);
    if (event.seq <= eventSeq) return;
    eventSeq = event.seq;
    events.push(event);
    if (!logFrame)
      logFrame = requestAnimationFrame(() => {
        logFrame = null;
        renderLogs();
      });
    if (
      [
        "request",
        "entry",
        "row_done",
        "job_start",
        "job_done",
        "job_cancelled",
      ].includes(event.kind)
    )
      scheduleRefresh();
    if (["job_done", "job_cancelled"].includes(event.kind)) {
      source.close();
      if (stream === source) stream = null;
      connection(event.kind === "job_done" ? "抓取结束" : "已停止");
      history().catch(() => {});
    }
  };
  source.onerror = () => {
    if (generation === currentGeneration) connection("连接中断，正在重连");
  };
}
function eventHTML(e) {
  let extra = "";
  if (e.query) extra += `<div class="log-extra">查询词：${esc(e.query)}</div>`;
  if (e.url) extra += `<span class="log-url">${esc(e.url)}</span>`;
  if (e.target) extra += `<span class="log-url">→ ${esc(e.target)}</span>`;
  if (e.identifier)
    extra += `<div class="log-extra">${esc(e.identifier)}</div>`;
  if (e.kind === "response")
    extra += `<span class="log-extra">${e.elapsed_ms} ms · ${e.bytes.toLocaleString()} bytes · ${esc(e.content_type || "未声明内容类型")}</span> `;
  if (e.kind === "request")
    extra += `<div class="log-extra">Accept: ${esc(e.accept)} · 第 ${e.attempt} 次尝试</div>`;
  if (e.kind === "cache")
    extra += `<div class="log-extra">原抓取时间：${esc(e.retrieved_at)}</div>`;
  if (e.selected_title)
    extra += `<div class="log-extra">${esc(e.selected_title)}</div>`;
  if (e.input_title !== undefined)
    extra += `<div class="log-extra">输入标题：${esc(e.input_title)}</div>`;
  if (e.downloaded_title !== undefined)
    extra += `<div class="log-extra">下载标题：${esc(e.downloaded_title || "（缺失）")}</div>`;
  if (e.normalized_input_title !== undefined)
    extra += `<div class="log-extra">比较用输入标题：${esc(e.normalized_input_title || "（空）")}</div>`;
  if (e.normalized_downloaded_title !== undefined)
    extra += `<div class="log-extra">比较用下载标题：${esc(e.normalized_downloaded_title || "（空）")}</div>`;
  if (e.error) extra += `<div class="log-extra">${esc(e.error)}</div>`;
  if (e.hits?.length)
    extra += `<ol class="log-hits">${e.hits.map((h) => `<li>${esc(h.title)} <span>(${esc(h.id)})</span></li>`).join("")}</ol>`;
  if (e.sha256)
    extra += `<button class="log-link" data-response="${e.sha256}" data-seq="${e.seq}">${e.kind === "bibtex" ? "查看 BibTeX 原文" : "查看响应正文"}</button>`;
  return `<div class="log-line ${esc(e.kind)}"><time class="log-time" title="${esc(e.time)}">${timeLabel(e.time)}</time><span class="log-kind">${kinds[e.kind] || esc(e.kind)}</span><div class="log-detail"><span class="log-message">${e.entry_key ? `<span class="log-entry">${esc(e.entry_key)}</span>` : ""}${esc(e.message)}</span>${extra}</div></div>`;
}
function renderLogs() {
  const selected = $("log-row").value;
  const filtered = events.filter(
    (e) => selected === "all" || String(e.row_id) === selected,
  );
  const visible = filtered.slice(-600);
  const box = $("log-stream");
  const previousScroll = box.scrollTop;
  box.innerHTML = visible.length
    ? visible.map(eventHTML).join("")
    : '<div class="log-empty"><span>●</span> 等待实际请求<br><small>查询词、请求地址、返回状态、耗时与下载原文会在这里实时显示。</small></div>';
  box.scrollTop = $("auto-scroll").checked ? box.scrollHeight : previousScroll;
  $("log-count").textContent =
    `${events.length} 条过程记录${selected !== "all" ? ` · 当前条目 ${filtered.length} 条` : ""}${filtered.length > 600 ? " · 显示最近 600 条" : ""}`;
  $("download-log").disabled = !events.length;
}
function downloadURL(url, name) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}
function exportOptions() {
  return {
    include_url: $("include-url").checked,
    abbreviate: $("abbreviate").checked,
    include_unfetched: $("include-unfetched").checked,
  };
}
function exportURL(format) {
  return `/api/jobs/${job.id}/export?${new URLSearchParams({ format, ...exportOptions() })}`;
}
function showExportOptions() {
  const options = exportOptions();
  const style = `${options.include_url ? "保留 URL" : "移除 URL，保留 DOI"} · ${options.abbreviate ? "按表缩写期刊／会议名" : "保留来源名称"}。arXiv 标识与编号不随 URL 选项隐藏。`;
  $("export-hint").textContent =
    `${style}${options.include_unfetched ? "未抓取条目保留输入内容及引用键，并标记来源；不计为抓取成功。" : "仅导出抓取成功条目，其他引用键不会进入合并文件。"}合并导出自动处理 LaTeX 兼容格式。`;
}
function showRow(id) {
  const row = job?.rows.find((r) => r.id === Number(id));
  if (!row) return;
  $("detail-heading").textContent = "条目与下载原文";
  $("detail-dialog").querySelector(".eyebrow").textContent = "SOURCE RESPONSE";
  $("detail-content").innerHTML =
    `<h3 class="detail-title">${esc(row.original.title || row.key)}</h3><div class="detail-meta"><span class="status-badge ${row.status}">${rowStates[row.status]}</span><span>输入键：${esc(row.original_key)}</span>${row.source ? `<span>来源：${esc(row.source)}</span><span>来源键：${esc(row.source_key)}</span>` : ""}</div>${row.source_url ? `<a class="detail-source" href="${esc(row.source_url)}" target="_blank" rel="noopener noreferrer">${esc(row.source_url)} ↗</a>` : ""}${row.raw_bibtex ? `<pre class="source-pre">${esc(row.raw_bibtex)}</pre><div class="detail-meta">抓取时间：${esc(row.retrieved_at)}<br>SHA-256：${esc(row.sha256)}</div>` : `<div class="notice">${esc(row.reason || (row.status === "processing" ? "正在发送请求，可在下方过程日志查看进展。" : "本条目尚未开始抓取。"))}</div>`}<div class="detail-actions">${row.raw_bibtex ? '<button class="button secondary small" id="copy-raw">复制原文</button><button class="button primary small" id="download-raw">下载原文 .bib ↓</button>' : ""}<button class="button secondary small" id="show-row-log">查看本条抓取过程 ↗</button></div>${row.errors?.length ? `<details class="detail-section"><summary>本条目中失败的尝试（${row.errors.length}）</summary><pre>${esc(JSON.stringify(row.errors, null, 2))}</pre></details>` : ""}<details class="detail-section"><summary>输入的原始条目</summary><pre>${esc(row.raw)}</pre></details>${row.notes.length ? `<p class="detail-meta">${row.notes.map(esc).join("<br>")}</p>` : ""}`;
  if (row.status === "failed" && row.issues?.length) {
    $("detail-content").insertAdjacentHTML(
      "beforeend",
      `<section class="detail-section"><h4>逐来源原因与待选记录</h4>${row.issues.map((issue) =>
        `<p><strong>${esc(issue.source)} · ${esc(failureLabels[issue.code] || issue.code)}</strong><br>${esc(issue.message)}${issue.downloaded_title ? `<br>来源标题：${esc(issue.downloaded_title)}` : ""}</p>${(issue.candidates || []).map((candidate) => `<pre class="source-pre">${esc(candidate.title)}\n${esc(candidate.id)}\n${esc(candidate.bib_url)}</pre>`).join("")}`
      ).join("")}<p class="detail-meta">原输入保留。多版本或标题文字差异需要自行确认；完整抓取包内含 retrieval-review.md 清单。</p></section>`,
    );
  }
  if (row.raw_bibtex) {
    const titleNote =
      row.title_match === "matched"
        ? "下载标题与输入一致；作者、年份和发表版本未核验。"
        : row.title_match === "not_checked"
          ? "输入未提供标题，本条按标识或记录链接抓取，未比较标题。"
          : "历史结果：没有新版标题匹配记录。重新导入可按新规则抓取。";
    $("detail-content").insertAdjacentHTML(
      "afterbegin",
      `<p class="notice">${titleNote}</p>`,
    );
    listen("copy-raw", "click", async () => {
      await navigator.clipboard.writeText(row.raw_bibtex);
      toast("原文已复制");
    });
    listen("download-raw", "click", () =>
      downloadURL(
        `/api/jobs/${job.id}/responses/${row.sha256}?download=bib`,
        `${row.key.replace(/[^\w.-]/g, "_")}.bib`,
      ),
    );
  }
  listen("show-row-log", "click", () => {
    $("detail-dialog").close();
    $("log-row").value = String(row.id);
    renderLogs();
    $("log-stream").scrollIntoView({ behavior: "smooth", block: "center" });
  });
  $("detail-dialog").showModal();
}
async function showResponse(digest, seq) {
  if (!job) return;
  const id = job.id,
    event = events.find((e) => e.seq === Number(seq));
  const response = await fetch(`/api/jobs/${id}/responses/${digest}`);
  if (!response.ok) throw new Error("读取响应正文失败");
  const raw = await response.text();
  $("detail-heading").textContent =
    event?.kind === "bibtex" ? "原站 BibTeX" : "实际 HTTP 响应正文";
  $("detail-dialog").querySelector(".eyebrow").textContent = "SOURCE RESPONSE";
  $("detail-content").innerHTML =
    `<div class="detail-meta">${esc(event?.url || "")}<br>时间：${esc(event?.time)}<br>SHA-256：${esc(digest)}</div><pre class="source-pre">${esc(raw)}</pre><div class="detail-actions"><button class="button secondary small" id="copy-response">复制正文</button><button class="button primary small" id="save-response">下载正文 ↓</button></div>`;
  listen("copy-response", "click", async () => {
    await navigator.clipboard.writeText(raw);
    toast("响应正文已复制");
  });
  listen("save-response", "click", () =>
    downloadURL(
      `/api/jobs/${id}/responses/${digest}?download=${event?.kind === "bibtex" ? "bib" : "txt"}`,
      event?.kind === "bibtex" ? "source.bib" : "response.txt",
    ),
  );
  $("detail-dialog").showModal();
}
async function filesInput(files) {
  const list = [...files];
  if (!list.length) return;
  if (list.reduce((s, f) => s + f.size, 0) > 5_000_000)
    throw new Error("文件总计超过 5 MB，请拆分后导入。");
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const texts = [];
  for (const file of list) {
    try {
      texts.push(decoder.decode(await file.arrayBuffer()));
    } catch {
      throw new Error(`${file.name} 不是 UTF-8 文本，请转换编码后导入。`);
    }
  }
  filename = list.length === 1 ? list[0].name : `${list.length} 个 BibTeX 文件`;
  $("bib-input").value = texts.join("\n\n");
  $("file-label").textContent = filename;
}
listen("file-input", "change", (e) => filesInput(e.target.files));
for (const name of ["dragenter", "dragover"])
  $("dropzone").addEventListener(name, (e) => {
    e.preventDefault();
    $("dropzone").classList.add("dragover");
  });
listen("dropzone", "dragleave", () =>
  $("dropzone").classList.remove("dragover"),
);
listen("dropzone", "drop", async (e) => {
  e.preventDefault();
  $("dropzone").classList.remove("dragover");
  await filesInput(e.dataTransfer.files);
});
listen("clear-input", "click", () => {
  $("bib-input").value = "";
  $("file-label").textContent = "未选择文件";
  $("file-input").value = "";
  filename = "references.bib";
});
listen("load-sample", "click", async () => {
  const data = await api("/api/sample");
  $("bib-input").value = data.text;
  filename = "sample.bib";
  $("file-label").textContent = "sample.bib · 3 条示例，点击读取后开始抓取";
  toast("示例已填入，点击“读取文章列表”");
});
listen("import-button", "click", async () => {
  if (!$("bib-input").value.trim()) throw new Error("请先导入或粘贴 BibTeX。");
  if (!$("mailto").checkValidity())
    throw new Error("联系邮箱格式不正确，可留空。");
  $("import-button").disabled = true;
  try {
    const data = await api("/api/jobs", {
      text: $("bib-input").value,
      filename,
      sources: [
        ...document.querySelectorAll('input[name="source"]:checked'),
      ].map((e) => e.value),
      mailto: $("mailto").value,
      cache: $("use-cache").checked,
      keep_keys: $("keep-keys").checked,
    });
    await openJob(data.id);
    toast(`已读取 ${data.total} 个条目，可以开始抓取。`);
  } finally {
    $("import-button").disabled = false;
  }
});
listen("start-button", "click", async () => {
  if (!job || !titleMatchingReady) return;
  const id = job.id;
  job = await api(`/api/jobs/${id}/start`, {});
  render();
  connect();
  await history();
});
listen("cancel-button", "click", async () => {
  if (!job) return;
  const id = job.id;
  await api(`/api/jobs/${id}/cancel`, {});
  await openJob(id);
  toast("已停止，已下载的条目和日志均已保存。");
});
for (const [id, format] of [
  ["export-bib", "bib"],
  ["export-zip", "zip"],
  ["download-log", "log"],
])
  listen(id, "click", () => {
    if (!job) return;
    downloadURL(
      exportURL(format),
      {
        bib: "merged.bib",
        zip: "bibtex-fetch-results.zip",
        log: "process.jsonl",
      }[format],
    );
  });
for (const id of ["include-url", "abbreviate", "include-unfetched"])
  listen(id, "change", () => {
    showExportOptions();
    render();
    localStorage.setItem(
      "bibtex-fetch-export-options",
      JSON.stringify(exportOptions()),
    );
  });
listen("preview-export", "click", async () => {
  if (!job) return;
  const url = exportURL("bib"),
    hint = $("export-hint").textContent,
    currentGeneration = generation;
  $("preview-export").disabled = true;
  $("preview-export").textContent = "正在生成预览…";
  try {
    const response = await fetch(url);
    if (!response.ok)
      throw new Error((await response.json()).detail || "预览失败");
    const raw = await response.text();
    if (currentGeneration !== generation) return;
    $("detail-dialog").querySelector(".eyebrow").textContent = "EXPORT PREVIEW";
    $("detail-heading").textContent = "合并 BibTeX 预览";
    $("detail-content").innerHTML =
      `<p class="detail-meta">${esc(hint)}</p><pre class="source-pre" id="merged-preview">${esc(raw)}</pre><div class="detail-actions"><button class="button primary small" id="download-preview">下载此版本 .bib ↓</button></div>`;
    listen("download-preview", "click", () => downloadURL(url, "merged.bib"));
    $("detail-dialog").showModal();
  } finally {
    $("preview-export").textContent = "预览合并结果";
    $("preview-export").disabled = !(
      $("include-unfetched").checked ? job?.total : job?.counts.success
    );
  }
});
listen("show-abbreviations", "click", async () => {
  const data = await api("/api/abbreviations");
  $("detail-dialog").querySelector(".eyebrow").textContent =
    "ABBREVIATION TABLE";
  $("detail-heading").textContent = `期刊／会议缩写表 · ${data.count} 项`;
  $("detail-content").innerHTML =
    `<p class="detail-meta">沿用提供的缩写拼写，重复键合并。TOG 使用最后给定的 ACM TOG；The Visual Computer 全称使用 TVCOMP（Vis. Comput.）。未匹配名称保留原样。</p><pre class="source-pre">${esc(data.bibtex)}</pre><p class="detail-meta">合并文件直接写入缩写文本，例如 booktitle = {CVPR}，无需另行加载字符串宏。完整抓取包包含此表。</p>`;
  $("detail-dialog").showModal();
});
listen("history", "click", async (e) => {
  const item = e.target.closest("[data-job]");
  if (item) await openJob(item.dataset.job);
});
listen("refresh-history", "click", history);
listen("new-workspace", "click", () => {
  ++generation;
  closeStream();
  job = null;
  events = [];
  eventSeq = 0;
  localStorage.removeItem("bibtex-fetch-job");
  $("log-row").innerHTML = '<option value="all">全部条目</option>';
  $("search").value = "";
  connection("等待任务");
  render();
  renderLogs();
  history().catch(() => {});
  $("bib-input").focus();
});
listen("records", "click", (e) => {
  const row = e.target.closest("[data-row]");
  if (row) showRow(row.dataset.row);
});
listen("records", "keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    const row = e.target.closest("[data-row]");
    if (row) {
      e.preventDefault();
      showRow(row.dataset.row);
    }
  }
});
listen("log-stream", "click", async (e) => {
  const button = e.target.closest("[data-response]");
  if (button) await showResponse(button.dataset.response, button.dataset.seq);
});
listen("log-row", "change", renderLogs);
listen("search", "input", renderRows);
document.querySelectorAll(".filter").forEach((button) =>
  button.addEventListener("click", () => {
    filter = button.dataset.filter;
    document
      .querySelectorAll(".filter")
      .forEach((b) => b.classList.toggle("active", b === button));
    renderRows();
  }),
);
for (const id of ["help-open", "about-link"])
  listen(id, "click", () => $("help-dialog").showModal());
document
  .querySelectorAll(".close-dialog")
  .forEach((button) =>
    button.addEventListener("click", () => button.closest("dialog").close()),
  );
document.querySelectorAll("dialog").forEach((dialog) =>
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (
        e.clientX < r.left ||
        e.clientX > r.right ||
        e.clientY < r.top ||
        e.clientY > r.bottom
      )
        dialog.close();
    }
  }),
);
setInterval(() => {
  if (active()) refresh().catch(() => connection("本机服务暂不可用"));
}, 1500);
window.addEventListener("pagehide", closeStream);
(async () => {
  try {
    try {
      const options = JSON.parse(
        localStorage.getItem("bibtex-fetch-export-options") || "{}",
      );
      $("include-url").checked = options.include_url !== false;
      $("abbreviate").checked = options.abbreviate === true;
      $("include-unfetched").checked = options.include_unfetched !== false;
      // Persist only current controls; obsolete preset preferences are discarded.
      localStorage.setItem("bibtex-fetch-export-options", JSON.stringify(exportOptions()));
    } catch {
      /* Ignore obsolete or malformed local display preferences. */
    }
    showExportOptions();
    await checkServerRules();
    const list = await history();
    const saved = localStorage.getItem("bibtex-fetch-job");
    if (saved && list.some((j) => j.id === saved)) await openJob(saved);
  } catch (e) {
    toast(e.message, true);
  }
})();
