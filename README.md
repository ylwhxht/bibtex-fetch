# BibTeX Fetch

**读取 BibTeX 文章列表，逐条检索并下载来源返回的 BibTeX，展示真实请求过程，再按需汇总导出。**

[English](README.en.md) · [使用手册](docs/USAGE.md) · [开发文档](docs/DEVELOPMENT.md) · [贡献指南](CONTRIBUTING.md) · [问题反馈](https://github.com/ylwhxht/bibtex-fetch/issues)

BibTeX Fetch 是本机运行的开源文献工具，提供中文可视化界面与命令行。抓取由普通 Python 代码执行，无需语言模型、AI 服务或 API Key。

## 能做什么

- **逐条抓取**：优先使用 DOI、arXiv 编号或 DBLP 记录链接，随后按标题检索。
- **过程可见**：实时查看查询词、完整请求地址、状态码、响应耗时、跳转、重试与来源正文。
- **来源原文留存**：每条下载内容、HTTP 响应、输入文件与过程日志可打包导出。
- **格式可选**：勾选是否保留 URL、是否使用期刊／会议缩写，即时预览合并结果。
- **TPAMI 精简格式**：可选 IEEE 规范词语缩写、超过 6 位作者使用首位加 et al.、省略可选会议信息，保留必要出版字段及在线链接。[规则与边界](docs/TPAMI.md)
- **自动兼容 LaTeX**：合并导出自动处理月份宏、重音字母和普通文本特殊字符；无需额外勾选或手动修补。[处理规则](docs/LATEX.md)
- **类型兼容**：修正可由现有字段确定的会议／预印本类型，记录每处调整；普通模式保留全部作者、月份、出版社及其他来源字段。
- **任务可恢复**：停止、继续、失败重试、本地历史、条目搜索与日志筛选。
- **两种入口**：浏览器界面和命令行共用同一套抓取逻辑。

程序执行固定检索规则，不核验文献真实性、不评分，也不补写标题、作者、年份等字段。标题搜索只选择标题一致的唯一记录，不再使用首条兜底。只要输入提供了标题，下载后的 BibTeX 也必须标题一致才能汇总；不一致就继续下一来源，并展示两个标题与拒绝原因。没有输入标题时仅走标识符／记录链接路径，明确记录未比较标题。完整规则见[标题匹配](docs/TITLE_MATCHING.md)与[抓取流程](docs/ARCHITECTURE.md#抓取与选取规则)。

## 快速开始

需要 **Python 3.11+**。首次安装依赖与实际抓取需要联网。界面仅监听本机 `127.0.0.1`。

### 使用 uv（推荐）

下载[源码 ZIP](https://github.com/ylwhxht/bibtex-fetch/archive/refs/heads/main.zip)并进入解压目录，或克隆仓库：

```shell
git clone https://github.com/ylwhxht/bibtex-fetch.git
cd bibtex-fetch
```

在仓库目录启动：

```shell
uv sync --frozen --no-dev
uv run --frozen --no-dev bibtex-fetch
```

浏览器会打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)。没有 Python 时，uv 可自动安装兼容版本；uv 的安装方法见[官方文档](https://docs.astral.sh/uv/getting-started/installation/)。

### Windows 一键启动

安装 Python 3.11+ 或 uv 后，解压源码并双击 **`start.bat`**。首次运行会创建环境、安装依赖并打开浏览器。源码路径可以包含中文或空格。

### 使用 Python / pip

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.txt
.venv\Scripts\python.exe -m pip install --no-deps .
.venv\Scripts\python.exe run.py
```

macOS / Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python -m pip install --no-deps .
.venv/bin/python run.py
```

这里的 `pip install .` 安装本地仓库；本说明不假定项目已经发布到 PyPI。

## 第一次使用

1. 拖入 `.bib` 文件或粘贴文本，也可点击 **试用示例**。
2. 点击 **读取文章列表** → **开始抓取**。
3. 查看 **真实抓取过程**，点击条目或日志查看来源原文。
4. 选择 **保留 URL 字段**、**使用期刊／会议缩写**。
5. 点击 **预览合并结果**，然后下载 **合并 BibTeX** 或 **完整抓取包**。

示例含 3 个输入条目，演示 DOI 直取、arXiv 直取和标题搜索；第一条与第三条故意引用同一篇文章，以展示两条检索路径。示例不附带预制抓取结果，开始后才发送真实请求。

### 导出选项

| 选项 | 默认 | 效果 |
| --- | --- | --- |
| 保留 URL 字段 | 开启 | 关闭后只从合并文件移除 `url`，保留 DOI、eprint 等字段 |
| 使用期刊／会议缩写 | 关闭 | 根据内置的 107 个缩写键处理 `journal`、`journaltitle`、`booktitle` |
| TPAMI 精简格式 | 关闭 | 接管 URL 与缩写选项，按 IEEE 写法精简导出副本；完整包附手动调整清单 |
| 保留未抓取条目的输入内容 | 开启 | 失败／待处理条目保留输入内容并标记来源，避免缺失引用键；关闭则只导出抓取成功条目 |
| 保留输入引用键 | 开启 | 延续原来的 `\cite{key}`；重复键添加后缀，并输出映射表 |
| 使用响应缓存 | 关闭 | 可选复用 24 小时内响应，缓存命中单独记录 |

URL 与缩写选项可用于已有任务，无需重新抓取。缩写直接写为 `booktitle = {CVPR}` 等文本，不依赖外部宏。未匹配的名称保留原样；完整规则见[缩写说明](docs/ABBREVIATIONS.md)。

TPAMI 精简格式也可用于已有任务，原始文献和来源响应不变。请配合期刊的 IEEE 模板使用；缺失字段或未识别名称会列入 `manual-review.md`，供自行精修。[详细规则](docs/TPAMI.md)

默认 `merged.bib` 保留全部输入条目，未抓取条目不会伪装成抓取成功，也不会使用被拒绝的响应。完整包另含仅成功条目的 `downloaded.bib`、记录每条来源与数量的 `export-summary.json`，以及原文、输入、日志、响应、CSV 报告和格式修改记录。各文件含义见[导出内容](docs/USAGE.md#导出文件)。

## 命令行

```shell
uv run --frozen --no-dev bibtex-fetch-cli examples/sample.bib -o output/demo
uv run --frozen --no-dev bibtex-fetch-cli references.bib -o output/paper --no-url --abbreviate
uv run --frozen --no-dev bibtex-fetch-cli references.bib -o output/tpami --tpami-minimal
uv run --frozen --no-dev bibtex-fetch-cli --help
```

过程日志逐行写入标准输出，结束提示写入标准错误。仍支持 `python -m bibclean`。退出码：`0` 全部成功、`2` 有失败或输入／参数错误、`130` 用户中断。

## 本机数据

默认数据目录：

| 系统 | 路径 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\BibTeXFetch` |
| macOS | `~/Library/Application Support/BibTeXFetch` |
| Linux | `$XDG_DATA_HOME/bibtex-fetch`，未设置时为 `~/.local/share/bibtex-fetch` |

启动窗口会打印实际路径。可用 `--data-dir ./data` 或 `BIBTEX_FETCH_DATA_DIR` 指定目录。旧版的 `BIBCLEAN_DATA_DIR` 仍可使用。[旧版数据迁移](docs/USAGE.md#旧版数据迁移)说明了如何继续使用已有任务。

检索时会向启用的来源发送文章标识或标题；可选联系邮箱随 Crossref 请求发送。本地数据库、输入文献、响应日志和导出结果均不属于公开仓库内容。

## 开发与文档

```shell
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest -q
uv build
```

测试采用明确标注的模拟 HTTP 响应，不请求外部文献来源。CI 配置覆盖 Windows、Linux 的 Python 3.11–3.13，以及 macOS 的 Python 3.12；另检查安装后的界面资源与命令入口。

| 文档 | 内容 |
| --- | --- |
| [使用手册](docs/USAGE.md) | 安装、界面、CLI、导出、迁移、常见问题 |
| [缩写说明](docs/ABBREVIATIONS.md) | 107 个缩写、重复定义约定、扩展方式 |
| [架构说明](docs/ARCHITECTURE.md) | 来源路由、日志、存储和模块分工 |
| [API 说明](docs/API.md) | 本机接口、事件流、导出参数 |
| [开发说明](docs/DEVELOPMENT.md) | 环境、测试、打包与维护 |
| [发布说明](docs/RELEASING.md) | 首次上传仓库及构建发布包 |
| [变更记录](CHANGELOG.md) | 当前版本整理内容 |

## 来源接口与许可证

来源接口资料：[Crossref](https://www.crossref.org/documentation/retrieve-metadata/content-negotiation/)、[DataCite](https://support.datacite.org/docs/datacite-content-resolver)、[arXiv](https://info.arxiv.org/help/api/user-manual.html)、[DBLP](https://dblp.org/faq/How%2Bto%2Buse%2Bthe%2Bdblp%2Bsearch%2BAPI.html)。

源代码使用 [MIT License](LICENSE)。下载内容的权利与使用条件由原始来源决定。
