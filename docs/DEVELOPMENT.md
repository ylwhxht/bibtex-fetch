# 开发说明

[返回首页](../README.md) · [架构说明](ARCHITECTURE.md)

## 环境

建议使用 Python 3.12 和 uv。运行界面只需 Python；HTML、CSS、JavaScript 随安装包分发，没有前端编译步骤。

```shell
uv sync --frozen
uv run --frozen bibtex-fetch --data-dir ./data
```

为方便保留原有导入路径，Python 包仍叫 `bibclean`。用户入口为 `bibtex-fetch`、`bibtex-fetch-cli`，旧的 `python run.py` 与 `python -m bibclean` 同样可用。

## 仓库结构

```text
bibtex-fetch/
├── bibclean/              # 可安装的 Python 包
│   ├── static/           # 中文界面资源
│   └── resources/        # 随包示例
├── examples/             # 可直接运行的公开输入
├── tests/                # 离线测试与模拟响应
├── scripts/              # 发布包安装检查
├── docs/                 # 使用、架构、API、发布文档
├── .github/              # CI、依赖更新、Issue / PR 模板
├── pyproject.toml        # 元信息、依赖、入口、构建和代码规范
├── uv.lock               # 锁定运行与开发依赖
├── requirements.txt      # 从锁文件导出的运行依赖及哈希
├── run.py / start.bat    # 源码目录启动捷径
└── LICENSE               # MIT
```

`examples/sample.bib` 与随包的 `bibclean/resources/sample.bib` 同步维护；测试会比较它们。两者只有输入文献，不附带模拟检索结果。

## 测试与格式

```shell
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest -q
```

修改代码后可用 `uv run --frozen ruff format .` 统一 Python 格式。前端使用两空格缩进，保持可读源码；可选用 Prettier 格式化，不需要将 Node.js 加入运行依赖。

测试通过 httpx MockTransport 使用明确标注的合成响应，禁止真正的外部 HTTP。API 测试将数据库放在临时目录，不读取个人任务。覆盖范围包括解析、选取与回退、HTTP 日志、缓存／重试、停止恢复、原文保持、URL／缩写组合以及安装资源位置。

`tests/test_title_matching.py` 覆盖搜索与下载两阶段的标题限制、同名歧义、标识符和缓存路径、缺少标题的记录，以及被拒绝响应的保留。匹配规则见[标题匹配](TITLE_MATCHING.md)；这些测试检查代码行为，不代表文献字段的准确率。

`tests/test_latex_compat.py` 覆盖模拟 HTTP 抓取 → Runner → API／ZIP／CLI 默认导出，确认无需附加参数即可获得兼容语法，并且原文与响应保持不变。若本机已安装 `bibtex`、`pdflatex` 和 `kpsewhich`，还会使用 `plain`、`abbrv`、`IEEEtran` 实际编译四种 URL／缩写组合；缺失 TeX 工具或样式时该部分显示跳过。独立的 CI `latex` 任务安装 TeX 后运行编译回归；用户运行本工具不需要安装 TeX。

CI 在 Windows / Linux 的 Python 3.11、3.12、3.13 和 macOS 的 Python 3.12 上运行同一套检查及安装包冒烟检查。CI 只有仓库读取权限，不含自动发布步骤。它只有在仓库上传到 GitHub 并触发工作流后才实际执行。

## 构建与安装检查

```shell
uv build
uv run --frozen python scripts/check_distribution.py
```

Hatchling 按 [pyproject.toml](../pyproject.toml) 的包含规则生成 wheel 与 sdist。静态页面和示例位于 Python 包内部，可以从安装后的环境访问；用户数据写入独立的可写目录。

检查脚本会创建临时虚拟环境，按 `requirements.txt` 安装运行依赖，再安装生成的 wheel。在源码目录以外检查版本、界面资源、示例、缩写 API、两个命令入口，以及缺少标识时的 CLI 失败导出。构建与安装依赖可能联网；冒烟检查不检索文献。临时目录自动清理。

脚本默认从 PATH 调用 `uv`；也可用 `--uv /path/to/uv` 指定位置。默认检查 `dist/` 中最后修改的 wheel，也可用 `--wheel /path/to/package.whl` 指定本次构建的文件。

## 依赖与版本

运行依赖以 `pyproject.toml` 为来源，锁定结果保存在 `uv.lock`。`requirements.txt` 是生成文件，不手工修改：

```shell
uv lock
uv export --locked --no-dev --no-emit-project --output-file requirements.txt
uv sync --frozen
```

仅需要升级某个库时可用 `uv lock --upgrade-package PACKAGE_NAME`。提交依赖变化时同时提交 `pyproject.toml`、`uv.lock` 和重新导出的 `requirements.txt`。Dependabot 依赖更新后也需要运行导出命令，锁文件一致性检查会提示漏更新。

版本号唯一来源是 `bibclean/__init__.py`；构建元信息、API 和两个命令入口读取它。发布新版本时还需同步界面中的展示文案和 CHANGELOG。

## 增加来源

1. 在 `crawler.py` 中新增下载／搜索路径，并遵循已有的选取与错误事件格式。
2. 将官方 HTTPS 域名加入 `transport.py` 的域名集合。
3. 更新 API、CLI、前端的来源选项与文档。
4. 用模拟响应测试成功、空结果、返回非 BibTeX、限流和回退。
5. 实际联网调试时使用公开最小输入，不把个人抓取结果加入测试或仓库。

新来源必须返回真正的 BibTeX；搜索返回的 JSON/XML 可用于定位下载链接，不用于拼接作者、标题、年份等 BibTeX 字段。新来源如需不同节流策略，应在 HTTP 层明确实现。

## 维护资料

- [Hatch 构建配置](https://hatch.pypa.io/latest/config/build/)
- [uv 项目管理](https://docs.astral.sh/uv/guides/projects/)
- [GitHub Actions checkout](https://github.com/actions/checkout)
- [setup-uv](https://github.com/astral-sh/setup-uv)
- [Dependabot 支持的生态](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
