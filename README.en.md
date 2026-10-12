# BibTeX Fetch

**Read a BibTeX list, retrieve each entry's source BibTeX through deterministic code, show the actual HTTP process, and export the results.**

[中文](README.md) · [Usage guide (Chinese)](docs/USAGE.md) · [Architecture](docs/ARCHITECTURE.md) · [Contributing](CONTRIBUTING.md) · [Issues](https://github.com/ylwhxht/bibtex-fetch/issues)

A local bibliography tool with a Chinese browser interface and a CLI. No language model, AI service, or API key is required.

## Features

- DOI, arXiv ID and DBLP record retrieval, with title-search fallback.
- Crossref, DataCite, arXiv and DBLP source support.
- Live query, request, status, timing, redirect, retry and response logs.
- Original downloaded BibTeX and HTTP responses retained separately.
- Optional URL-field removal and 70 predefined venue abbreviations.
- Automatic LaTeX compatibility in every merged export: month tokens, accented names, Unicode punctuation and special text characters.
- Preview, ZIP export, citation-key mapping, history, cancellation and retry.
- Shared retrieval logic between the GUI and CLI.

The tool does not verify bibliographic truth or reconstruct references from search metadata. Title search requires a unique matching record; there is no first-result fallback. When the input supplies a title, the downloaded BibTeX must also match it, including downloads through identifiers. Missing or different titles are rejected and the next source is tried. Identifier-only inputs remain supported and explicitly log that no title comparison was possible. Multiple distinct same-title hits are treated as ambiguous. See [title matching](docs/TITLE_MATCHING.md) for normalization, logs and migration of old jobs.

## Quick start

Python 3.11+ is required. Download the [source ZIP](https://github.com/ylwhxht/bibtex-fetch/archive/refs/heads/main.zip), or clone the repository:

```shell
git clone https://github.com/ylwhxht/bibtex-fetch.git
cd bibtex-fetch
```

From the checkout directory:

```shell
uv sync --frozen --no-dev
uv run --frozen --no-dev bibtex-fetch
```

The browser opens [http://127.0.0.1:8765](http://127.0.0.1:8765). Install uv using its [official instructions](https://docs.astral.sh/uv/getting-started/installation/). On Windows, you can also double-click `start.bat` after installing Python 3.11+ or uv.

Without uv, on macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.txt
.venv/bin/python -m pip install --no-deps .
.venv/bin/python run.py
```

On Windows, use `python` and `.venv\Scripts\python.exe` instead. These instructions install the local checkout; they do not assume a PyPI publication exists.

In the UI, load or paste a UTF-8 `.bib` file, click **读取文章列表**, then **开始抓取**. Inspect source responses, choose the URL / abbreviation options, preview, and export. The sample contains three inputs demonstrating three retrieval paths; the first and third intentionally reference the same paper. It has no preloaded retrieval results.

## CLI

```shell
uv run --frozen --no-dev bibtex-fetch-cli examples/sample.bib -o output/demo
uv run --frozen --no-dev bibtex-fetch-cli references.bib -o output/paper --no-url --abbreviate
uv run --frozen --no-dev bibtex-fetch-cli --help
```

JSON Lines events go to stdout; the final summary goes to stderr. Exit codes are 0 for complete success, 2 for incomplete retrieval or invalid input / arguments, and 130 for interruption.

Use `--sources`, `--cache`, `--source-keys`, `--mailto`, and `--data-dir` as needed. Input keys are preserved by default; duplicate keys gain suffixes. Each input remains independent: there is no paper deduplication. Cache reads are off by default.

## Export behavior

The merged file uses input citation keys and automatically normalizes source field syntax for BibTeX/LaTeX. For example, `month=June` becomes `month={June}`, accented letters become protected TeX commands, and a literal underscore in a title becomes `\_`. Existing math and URL/DOI identifiers are retained. This applies to GUI previews, BibTeX downloads, ZIP files and CLI output without another option. `--no-url` removes only the top-level URL field. `--abbreviate` applies deterministic mappings to journal, journaltitle and booktitle; unknown names remain unchanged.

Abbreviations are braced text values, such as `{CVPR}`, not external macro references. Repeated definitions in the original mapping use the last value: TOG is ACM TOG. The Visual Computer uses TVCOMP / Vis. Comput.

The bundle includes merged and original BibTeX, individual raw entries, failed inputs, process logs, source responses, CSV reports, key mappings, and formatting changes. Downloaded raw content is retained independently of export formatting. Unknown Unicode and custom external TeX macros are not guessed and may require template support; see the [LaTeX guide](docs/LATEX.md). Replace the `.bib` and rebuild generated `.bbl` files when upgrading an old export.

## Local data

Default locations:

- Windows: `%LOCALAPPDATA%\BibTeXFetch`
- macOS: `~/Library/Application Support/BibTeXFetch`
- Linux: `$XDG_DATA_HOME/bibtex-fetch`, defaulting to `~/.local/share/bibtex-fetch`

Override with `--data-dir` or `BIBTEX_FETCH_DATA_DIR`. The legacy `BIBCLEAN_DATA_DIR` variable is supported. To use an old checkout's database, stop its service and point the new launcher at its `data` directory. Do not run multiple processes against the same data directory.

The service binds to localhost. Queries send identifiers or titles to enabled sources; an optional contact email is sent to Crossref. Local databases and downloaded material are excluded from source distributions.

## Development

```shell
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest -q
uv build
uv run --frozen python scripts/check_distribution.py
```

Tests use explicit mock responses and temporary storage. The wheel check installs the built artifact outside the checkout, checks bundled resources and entry points, and exercises an offline CLI failure/export case. Build and dependency installation can require network access.

See the [developer guide](docs/DEVELOPMENT.md) and [release guide](docs/RELEASING.md). GitHub Actions is configured for Windows/Linux Python 3.11–3.13 and macOS Python 3.12. There is no automatic publishing workflow.

## License

[MIT](LICENSE) for the source code. Retrieved content remains subject to its original source's terms.
