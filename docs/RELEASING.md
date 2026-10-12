# 仓库发布与版本打包

[返回首页](../README.md)

本文面向仓库维护者。代码和工作流可以直接放入 GitHub、GitLab 或其他 Git 托管平台；`.github/` 中的自动化仅在 GitHub 生效。

本项目的仓库地址为 [ylwhxht/bibtex-fetch](https://github.com/ylwhxht/bibtex-fetch)。以下首次上传步骤也可供创建其他托管副本时参考。

## 首次上传

1. 在自己的账号下创建空仓库，例如 `bibtex-fetch`。
2. 在本地检查待提交文件，应只包括代码、文档、测试和公开示例。
3. 提交并关联自己创建的仓库，再推送。

下面地址中的 `YOUR_ACCOUNT` 是占位符，请替换为真实账号：

```shell
git init -b main
git add .
git status --short
git commit -m "Prepare BibTeX Fetch open-source repository"
git remote add origin "https://github.com/YOUR_ACCOUNT/bibtex-fetch.git"
git push -u origin main
```

若目录已是 Git 仓库、已有提交或已配置 origin，只执行尚未完成的步骤。提交身份使用自己的 Git 配置。建议仓库描述：

> Fetch source BibTeX entry by entry with a live HTTP console, optional URL removal and venue abbreviations. No AI required.

可用主题：`bibtex`、`bibliography`、`crossref`、`arxiv`、`dblp`、`python`。

`.gitignore` 排除数据库、日志、缓存、导出目录和一般 `.bib` 输入，仅对公开示例目录放行。它不能阻止强制添加文件；发布时应检查 `git status` 和 `git ls-files` 中的内容。

## 构建一个版本

```shell
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest -q
uv build
uv run --frozen python scripts/check_distribution.py
```

产物位于 `dist/`：

- `bibtex_fetch-VERSION-py3-none-any.whl`：可安装的 Python wheel，包含界面资源。
- `bibtex_fetch-VERSION.tar.gz`：源码分发包，含文档和测试。

安装下载到本机的 wheel 时：

```shell
python -m pip install /path/to/bibtex_fetch-VERSION-py3-none-any.whl
bibtex-fetch
```

将 VERSION 替换为实际文件中的版本号。pip 会从配置的包索引安装所需依赖。

## 创建源码 ZIP

提交代码后可执行：

```shell
git archive --format=zip --prefix=bibtex-fetch/ --output=dist/bibtex-fetch-source.zip HEAD
```

该命令只打包已提交的文件，不包含 Git 内部目录、虚拟环境或被忽略的个人数据。执行前确认 `git status --short`，未提交修改不会进入 ZIP。从源码 ZIP 使用时不需要 Git 历史。

## 上传版本产物

在自己的托管仓库创建版本标签和 Release，上传构建出的文件，并写明本次实际测试环境。当前 CI 负责测试和构建，不会自动创建 Release、推送标签或上传 PyPI。

`pyproject.toml` 的 `[project.urls]` 与中英文 README 指向本项目仓库。创建其他托管副本时，按实际用途更新这些链接。推送源码不会自动将项目发布到 PyPI。

## 版本变更

- 修改 `bibclean/__init__.py` 的 `__version__`。
- 更新 CHANGELOG，并运行 `uv lock` 与依赖导出。
- 同步界面版本展示。
- 按上述顺序重新测试、构建和检查 wheel。

源代码使用 MIT；抓取的文献元数据与第三方依赖仍各自适用其原有条款。发布包中不附带本机任务数据库或个人抓取记录。
