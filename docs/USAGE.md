# 使用手册

[返回首页](../README.md)

## 安装与启动

完整跨平台安装命令见[快速开始](../README.md#快速开始)。所有命令均在仓库目录执行；通过安装包安装后，也可以直接调用 `bibtex-fetch` 与 `bibtex-fetch-cli`。

推荐 Python 3.12，最低要求 3.11。uv 按 `uv.lock` 安装锁定的依赖；pip 用户可按 `requirements.txt` 安装相同运行依赖，然后安装本项目。

```shell
uv run --frozen --no-dev bibtex-fetch
uv run --frozen --no-dev bibtex-fetch --port 8877
uv run --frozen --no-dev bibtex-fetch --no-browser --data-dir ./data
```

- 默认地址为 [http://127.0.0.1:8765](http://127.0.0.1:8765)。
- `--port`：指定 1–65535 范围内的本机端口。
- `--no-browser`：不自动打开浏览器，服务仍正常运行。
- `--data-dir`：本地任务、日志、响应与缓存目录。目录不存在时自动创建。
- `--version`：打印版本。
- 关闭服务可在启动终端按 Ctrl+C。浏览器标签页关闭后，服务仍运行。
- 同一端口已有本工具时，重复启动会打开该实例，数据目录保持该实例启动时的设置。需要第二个实例时，请使用另一端口与另一数据目录。

Windows 的 `start.bat` 支持相同参数，例如 `start.bat --port 8877`。首次运行需安装依赖；遇到问题时窗口保留错误信息。

## 导入和抓取

1. 选择或拖入一个／多个 UTF-8 `.bib` 文件，也可直接粘贴文本。合计上限 5 MB、3,000 条。
2. 选择来源。默认启用 Crossref、DataCite、arXiv、DBLP。联系邮箱可留空；填写后随 Crossref 请求发送。
3. **保留输入引用键**默认开启；**使用响应缓存**默认关闭。它们与来源设置均在新建任务时保存。
4. 点击 **读取文章列表**。语法错误会提示，不会悄悄忽略无法解析的条目。
5. 点击 **开始抓取**。每条处理完成后立即保存；单条失败会继续处理下一条。

有 DOI、arXiv 编号或 DBLP 记录链接时优先直取，随后按标题搜索。Crossref 和 arXiv 在首次未匹配时增加一次检索回退，最多读取 25 个候选；DBLP 最多读取 5 个。只选择标题一致的唯一记录；没有同名结果或存在多个不同的同名记录时继续下一来源，不取首条兜底。输入提供了标题时，所有下载路径都必须让最终 BibTeX 的标题与输入一致，否则拒绝汇总。程序不检查作者／年份是否与输入一致，也不进行真实性判定。输入只有标识符而没有标题时保留直取能力，并明确记录未比较标题。详见[标题匹配规则](TITLE_MATCHING.md)。

“试用示例”只加载公开文献的输入列表。点击开始后才联网，没有演示用的虚构抓取记录。

## 查看真实过程

**真实抓取过程**区域展示：

- 搜索词、来源候选与选取规则；
- 输入标题、下载标题、比较用标题及匹配／拒绝原因；
- 每次 HTTP GET 的完整 URL、尝试次数；
- 实际响应状态、耗时、正文长度与 SHA-256；
- 等待、重试、跳转、下载成功和失败原因；
- 缓存命中与原始抓取时间，缓存不会计入 HTTP 请求数。

可以按条目筛选、关闭自动滚动、查看响应正文或下载完整日志。界面最多保留 600 条日志 DOM 节点以减少卡顿；完整日志可从导出包或日志下载获得。

点击成功条目可查看来源返回的 BibTeX。这里展示原文；URL 与缩写格式选项以及自动 LaTeX 兼容处理作用于“预览合并结果”和合并文件下载。

未抓取条目会显示具体原因，点击可查看每个来源的错误和同标题待选记录。完整抓取包中的 `retrieval-review.md` 汇总未抓取清单；它与 TPAMI 格式的 `manual-review.md` 各自保留。限流／网络问题可再次点击重试，版本选择与实质标题差异由使用者决定后修改输入再导入，程序不自动替换。

“原文”指 HTTP 解压后按 UTF-8 解码的文本，不是包含 HTTP 头的网络抓包。正文哈希使用该文本重新编码后的 UTF-8 字节。收到 HTML 验证页或非 BibTeX 内容时会记录失败。

## 停止、继续与历史

- **停止**会中止当前执行，已完成内容和日志保留。
- 再次启动会处理待处理条目并重试失败条目；成功条目不重复抓取。
- 旧版本已成功的记录不会自动重新匹配；详情会提示缺少新版匹配记录。重新导入原 `.bib` 建立新任务，才能让这些条目按新规则抓取。
- 左侧 **本地任务**可打开最近 100 个任务。浏览器刷新不会删除本机数据库。
- 服务异常退出后，启动时将残留的运行任务标记为“中断”，可以继续。
- 同一服务的多个任务排队执行，避免同时向来源大量发请求。
- 运行中导出得到当时已保存的快照；未完成条目仍列在 `failed.bib` 中。

## 导出格式

所有合并导出自动处理 LaTeX 兼容格式：月份宏、重音字母、Unicode 标点和普通文本特殊字符。网页预览、`.bib` 下载、ZIP 中的 `merged.bib` 以及 CLI 输出共用此流程，已有任务无需重新抓取，也无需增加勾选项。具体规则与旧文件替换方法见 [LaTeX 兼容说明](LATEX.md)。

导出勾选项对新旧任务即时生效，浏览器会记住选项：

| 选项 | 操作范围 |
| --- | --- |
| 保留 URL 字段 | 关闭时，仅删除顶层 `url` 字段，大小写不敏感；不会删除注释、正文或其他字段里的网址 |
| 使用期刊／会议缩写 | 对 `journal`、`journaltitle`、`booktitle` 使用固定映射；未匹配名称保持原样 |
| TPAMI 精简格式 | 默认关闭；接管 URL／缩写选项，使用规范词语缩写、精简长作者列表和可选会议信息，保留在线文献链接；[详细规则](TPAMI.md) |
| 保留未抓取条目的输入内容 | 默认开启，失败／等待／处理中的条目保留输入字段和引用键，并标记为输入来源；关闭则只导出成功条目 |

启用缩写后生成 `journal = {IEEE Trans. Pattern Anal. Mach. Intell.}`、`booktitle = {CVPR}` 这样的文本值。完整包附 `abbreviations.bib`，但合并文件不依赖该宏文件。重复定义处理见[缩写说明](ABBREVIATIONS.md)。

合并文件默认按输入顺序保留全部条目及输入引用键。抓取成功使用来源 BibTeX；未抓取条目使用输入内容并加注释，不使用被拒绝的响应，不计为抓取成功。两类条目均应用格式选项及 LaTeX 兼容处理。不同输入条目对应同一篇文章时仍独立导出；程序只消除引用键冲突，不做论文去重。冲突键添加 `_2`、`_3` 等后缀。

界面显示“导出数 / 输入数、已抓取、保留输入”；关闭保留选项时明确显示遗漏数量。若旧版导出后出现 `Citation ... undefined`，打开原任务，保留默认选项重新导出即可恢复原输入中的引用键。输入本身缺少的引用键不会凭空补造。

### 导出文件

| 文件 | 内容 |
| --- | --- |
| `merged.bib` | 按当前引用键、URL、缩写选项及自动 LaTeX 兼容处理生成的合并结果 |
| `downloaded.bib` | 仅抓取成功条目，使用相同引用键和格式选项 |
| `export-summary.json` | 输入数、导出数、抓取数、保留数、遗漏数及每条 `downloaded`／`input`／`omitted` 来源 |
| `entries/*.bib` | 每条下载原文，来源引用键也保持不变 |
| `original.bib` | 原始输入全文 |
| `failed.bib` | 失败或尚未处理的输入条目；输入字符串宏展开，便于单独使用 |
| `process.jsonl` | 完整过程事件，每行一个 JSON 对象 |
| `responses/*.txt` | 接收到的搜索、下载、跳转和失败响应正文 |
| `report.csv` | 每条输入的状态、来源 URL 与结果 |
| `key-map.csv` | 输入键、来源键、导出键之间的对应关系 |
| `results.json` | 任务、设置、条目原文与结果 |
| `formatting.json` | 当前格式选项、URL 删除、缩写替换及 LaTeX 兼容处理的字段修改前后记录 |
| `manual-review.md` | TPAMI 模式下的格式缺口与未识别名称清单，供人工精修；不自动补写字段 |
| `abbreviations.bib` | 启用缩写时附带的 107 个参考定义 |
| `README.txt` | 此次导出包内容说明 |

导出选项不会改写 `entries/`、`responses/` 与已有过程日志。URL／缩写选项可随时调整；合并文件始终执行 LaTeX 兼容处理，未经改动的来源文本在 `entries/` 中。

## 命令行用法

```shell
uv run --frozen --no-dev bibtex-fetch-cli references.bib -o output/paper
uv run --frozen --no-dev bibtex-fetch-cli references.bib -o output/paper --no-url --abbreviate
uv run --frozen --no-dev bibtex-fetch-cli references.bib --sources crossref arxiv
uv run --frozen --no-dev bibtex-fetch-cli references.bib --cache --source-keys
uv run --frozen --no-dev bibtex-fetch-cli references.bib --data-dir ./data
```

已激活虚拟环境时可省略 `uv run --frozen --no-dev`。源码兼容入口为 `python -m bibclean`。

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `input` | 必填 | UTF-8 BibTeX 文件 |
| `-o / --output` | `output/时间戳` | 导出目录；目录内同名导出文件会覆盖 |
| `--sources` | 四个来源全开 | 从 crossref、datacite、arxiv、dblp 中选择，可列多个 |
| `--cache` | 关闭 | 允许使用 24 小时内的成功响应 |
| `--source-keys` | 关闭 | 使用来源引用键，仍处理冲突 |
| `--no-url` | 关闭 | 从合并文件移除 URL 字段 |
| `--abbreviate` | 关闭 | 启用内置缩写表 |
| `--tpami-minimal` | 关闭 | TPAMI 精简格式，优先于 `--no-url` 和 `--abbreviate`，保留在线文献所需链接 |
| `--downloaded-only` | 关闭 | 合并文件只导出抓取成功条目；默认保留并标记未抓取输入 |
| `--mailto` | 空 | Crossref 联系邮箱，可选 |
| `--data-dir` | 本机用户数据目录 | 任务与缓存存储位置 |

标准输出是 JSON Lines 事件流；最终计数与输出路径写入标准错误。CLI 同时写出展开的导出文件和 `bibtex-fetch-results.zip`。退出码 `0` 表示全部成功，`2` 表示存在抓取失败或输入／参数错误，`130` 表示 Ctrl+C 中断。磁盘写入等意外错误可能以其他非零状态退出。

## 数据目录与迁移

目录选择顺序：命令行 `--data-dir` → 环境变量 `BIBTEX_FETCH_DATA_DIR` → 兼容变量 `BIBCLEAN_DATA_DIR` → 系统默认位置。GUI 和 CLI 使用相同规则。

Windows 可临时指定：

```powershell
$env:BIBTEX_FETCH_DATA_DIR = "$PWD\data"
uv run --frozen --no-dev bibtex-fetch
```

macOS / Linux：

```sh
BIBTEX_FETCH_DATA_DIR="$PWD/data" uv run --frozen --no-dev bibtex-fetch
```

### 旧版数据迁移

旧版默认把数据放在源码目录的 `data/`。开源整理版使用用户数据目录，避免安装到只读目录时失败。

继续使用旧任务的方法：

1. 关闭旧版服务。
2. 用新版启动命令的 `--data-dir` 指向旧版 `data` 目录。
3. 打开左侧任务历史，选择已有任务。

```shell
uv run --frozen --no-dev bibtex-fetch --data-dir "/path/to/old-project/data"
```

也可在关闭服务后将旧数据目录整体备份／复制到新位置。数据库名 `cleanroom.sqlite3` 为兼容保留；若目录中存在 `-wal`、`-shm` 文件，请把整个目录一起备份。不要让两个服务同时操作同一数据目录。

## 常见问题

**下载失败或出现 HTML 页面**

来源可能限流、要求登录或暂时不可用。在日志中查看实际响应，稍后重试或切换已支持来源。程序不会绕过访问限制。

**标题不一致、没有同名结果或有同名歧义**

被拒绝的下载响应不会进入合并文件。默认保留对应的原始输入条目并标记来源；日志保留搜索候选、下载响应及标题差异，其他来源会继续尝试。可根据原论文修正输入标题或补充 DOI／arXiv 编号后新建任务；不要为了通过匹配随意改标题。严格匹配可能减少成功条数，特别是副标题、公式写法或发表版本不同的情况。标题一致仅表示满足匹配规则，不代表文献全部字段已核验。

**输入包含未定义的字符串宏**

将相应 `@String` 定义加入输入。来源返回的外部宏原文会保留；若来源本身依赖外部宏，需要由使用该 BibTeX 的文档提供定义。

**缩写没有改变**

名称必须匹配内置全称、别名或会议命名规则；未知名称不猜测。可查看界面的缩写表，或按[开发方式](ABBREVIATIONS.md#添加或修改缩写)增加别名。

**端口已占用**

使用 `--port 8877`。如果该端口已有本工具，会复用现有实例；新传入的数据目录不会改变已运行实例。

**找不到 Python、uv 或命令入口**

先安装 Python 3.11+ 或 uv，并重开终端。没有激活虚拟环境时，使用 README 中的完整路径或 `uv run`。本项目无需安装 Node.js 来运行界面。

**出现第三方 DeprecationWarning**

当前 BibTeX 解析库使用了一些已弃用的 pyparsing 接口，可能显示警告。测试结果以通过／失败状态为准；升级解析库时需重新测试原文与宏处理行为。

**输入与抓取记录保存在哪里**

启动终端会打印数据路径。SQLite 保存本机任务、响应正文与日志；浏览器仅保存界面偏好。公开问题反馈时优先使用删去个人信息的最小示例。
