"""Synthetic HTTP -> runner -> GUI/CLI export -> real BibTeX/pdfLaTeX regression."""

import asyncio
import io
import json
import shutil
import subprocess
import sys
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from bibclean import transport
from bibclean.bibliography import parse_bib
from bibclean.exports import export_files
from bibclean.formatting import format_bibtex
from bibclean.latex_compat import compatible_expression, latex_text
from bibclean.runner import Runner, new_job
from bibclean.storage import Store
from bibclean.transport import Fetcher

# Fictional test data only, never part of a user's crawl results.
SOURCE = r"""@inproceedings{source,
  author = {Example, Álvaro and Example, Émile and Müller, Ada},
  title = {Fixture_supp1.pdf: A&B, 50% and #1; $x_i^2$},
  booktitle = {IEEE Conference on Computer Vision and Pattern Recognition},
  year = {2024}, month = June, pages = {1–9},
  doi = {10.1234/fixture_1},
  url = {https://example.org/file_a?x=1&y=2#part}
}"""
INPUT = "@misc{input,doi={10.1234/fixture_1}}"


@pytest.mark.parametrize("month", ["June", "July", "SEPT", "September", "January"])
def test_source_month_tokens_are_self_contained(month):
    raw = "@misc{k,month=" + month + ' # " 1--3", title={Fixture}}'
    output, _ = format_bibtex(raw)
    assert "month={" in output
    assert ' # " 1--3"' in output
    assert parse_bib(output)[0]["original"]["month"].endswith(" 1--3")
    assert format_bibtex(output) == (output, [])


def test_defined_month_macros_and_unknown_macros_are_not_guessed():
    raw = '@string{June="Custom month"}\n@misc{k,month=June,journal=unknown}'
    assert format_bibtex(raw) == (raw, [])
    assert compatible_expression("month", "jun") == "jun"


@pytest.mark.parametrize(
    "text",
    [
        r"$x_i^2 + \alpha$ and $$y_j$$",
        r"\(x_i^2\) and \[y_j\] and \ensuremath{x_i^2}",
        r"\url{https://example.org/a_b?x=1&y=2#part}",
        r"\path{dir_a/file_b} \nolinkurl{a_b} \detokenize{a_b}",
        r"\verb|a_b&c| \verb*+a_b+",
        r"{\'A}lvaro, M{\"u}ller; \_ \& \% \# \$ {\LaTeX}",
    ],
)
def test_existing_latex_and_identifiers_are_not_double_escaped(text):
    assert latex_text(text) == text


def test_text_escapes_keep_grouping_math_and_link_targets():
    text = r"A_B & 50% #1 $5; \href{https://example.org/a_b}{A_B}"
    assert latex_text(text) == (r"A\_B \& 50\% \#1 \$5; \href{https://example.org/a_b}{A\_B}")
    expression = r'"A_B" # suffix # {Émile & {Nested_title}}'
    assert compatible_expression("title", expression) == (
        r'"A\_B" # suffix # {{\'E}mile \& {Nested\_title}}'
    )
    for field in ("url", "doi", "eprint", "crossref"):
        assert compatible_expression(field, "{a_b&c#d%20}") == "{a_b&c#d%20}"
    assert latex_text("E\u0301mile") == latex_text("Émile") == r"{\'E}mile"
    assert latex_text("中文") == "中文"  # No invented transliteration or dropped characters.


@pytest.fixture
def downloaded(tmp_path):
    transport.LAST_REQUEST.clear()
    store = Store(tmp_path / "store")
    job = new_job(INPUT, "fixture.bib", {"sources": ["crossref"], "keep_keys": True})
    runner = Runner(store, job)

    async def crawl():
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, text=SOURCE))
        )
        await runner.run(Fetcher(store, runner.emit, client=client))

    asyncio.run(crawl())
    assert job["rows"][0]["status"] == "success"
    assert job["request_count"] == 1
    return job, store


@pytest.mark.parametrize(
    "include_url,abbreviate", [(True, False), (False, False), (True, True), (False, True)]
)
def test_download_to_api_and_zip_export_is_always_compatible(
    downloaded, monkeypatch, include_url, abbreviate
):
    import bibclean.app as api

    job, store = downloaded
    monkeypatch.setattr(api, "JOBS", {job["id"]: job})
    monkeypatch.setattr(api, "STORE", store)
    params = {"include_url": str(include_url).lower(), "abbreviate": str(abbreviate).lower()}
    path = f"/api/jobs/{job['id']}/export"
    with TestClient(api.app) as client:
        response = client.get(path, params=params)
        assert response.status_code == 200
        merged = response.text
        assert r"{\'A}lvaro" in merged
        assert "month = {June}" in merged
        assert r"Fixture\_supp1.pdf" in merged
        assert "pages = {1--9}" in merged
        assert r"$x_i^2$" in merged
        assert ("url =" in merged) == include_url
        assert format_bibtex(merged) == (merged, [])
        bundle = client.get(path, params={**params, "format": "zip"})
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            assert archive.read("merged.bib") == response.content
            assert archive.read("entries/0001-input.bib").decode() == SOURCE
            assert archive.read("original.bib").decode() == INPUT
            assert archive.read(f"responses/{job['rows'][0]['sha256']}.txt").decode() == SOURCE
            changes = json.loads(archive.read("formatting.json"))
            assert changes["latex_compatibility"] is True
            assert any(c["action"] == "latex_compatibility" for c in changes["changes"])


@pytest.mark.parametrize("minimal", [False, True])
def test_cli_default_export_uses_same_compatibility(tmp_path, monkeypatch, capsys, minimal):
    import bibclean.__main__ as cli
    import bibclean.runner as runner

    transport.LAST_REQUEST.clear()

    def fixture_fetcher(store, emit, **kwargs):
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, text=SOURCE))
        )
        return Fetcher(store, emit, client=client, **kwargs)

    monkeypatch.setattr(runner, "Fetcher", fixture_fetcher)
    source, output = tmp_path / "input.bib", tmp_path / "output"
    source.write_text(INPUT, encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["bibtex-fetch-cli", str(source), "-o", str(output), "--data-dir", str(tmp_path / "data")]
        + (["--tpami-minimal"] if minimal else []),
    )
    assert cli.main() == 0
    merged = (output / "merged.bib").read_text(encoding="utf-8")
    assert merged == format_bibtex(SOURCE, tpami_minimal=minimal)[0].replace("{source,", "{input,")
    assert (output / "entries/0001-input.bib").read_text(encoding="utf-8") == SOURCE


@pytest.mark.parametrize("style", ["plain", "abbrv", "IEEEtran"])
@pytest.mark.parametrize("include_fallback", [False, True])
@pytest.mark.parametrize(
    "include_url,abbreviate", [(True, False), (False, False), (True, True), (False, True)]
)
def test_downloaded_export_compiles_with_real_bibtex(
    downloaded, tmp_path, style, include_url, abbreviate, include_fallback
):
    job, store = downloaded
    if include_fallback:
        row = parse_bib(
            "@inproceedings{unfetched_key, title={Original_input & 50%}, "
            "author={Example, Émile}, year={2022}, month=June, pages={1–5}, "
            "booktitle={2022 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)}}"
        )[0]
        row.update(id=1, status="failed", reason="Synthetic unavailable source")
        job["rows"].append(row)
    files = export_files(job, store, include_url=include_url, abbreviate=abbreviate)
    bbl = assert_compiles(files["merged.bib"], tmp_path, style, 2 if include_fallback else 1)
    if include_fallback and abbreviate:
        assert "IROS" in bbl
        assert "Intelligent Robots" not in bbl


@pytest.mark.parametrize("style", ["plain", "abbrv", "IEEEtran"])
@pytest.mark.parametrize(
    "include_url,abbreviate", [(True, False), (False, False), (True, True), (False, True)]
)
def test_preprints_and_conference_chapters_compile_without_bibtex_warnings(
    tmp_path, style, include_url, abbreviate
):
    from test_export_semantics import typed_job

    files = export_files(
        typed_job(), Store(tmp_path / "store"), include_url=include_url, abbreviate=abbreviate
    )
    assert_compiles(files["merged.bib"], tmp_path, style, 4)


def test_tpami_export_compiles_and_reduces_rendered_reference(tmp_path):
    from test_tpami import example_job

    store = Store(tmp_path / "store")
    job = example_job()
    # Include an unfetched input with a protected corporate name and an online locator.
    row = parse_bib(
        "@misc{online,title={Synthetic online resource},author={{Research and Development}},"
        "year=2025,url={https://example.org/data_a}}"
    )[0]
    row.update(id=1, status="failed", reason="Synthetic unavailable source")
    job["rows"].append(row)
    normal_dir, minimal_dir = tmp_path / "normal", tmp_path / "minimal"
    normal_dir.mkdir()
    minimal_dir.mkdir()
    normal = assert_compiles(export_files(job, store)["merged.bib"], normal_dir, "IEEEtran", 2)
    minimal = assert_compiles(
        export_files(job, store, tpami_minimal=True)["merged.bib"], minimal_dir, "IEEEtran", 2
    )
    assert "et~al." in minimal
    # BibTeX builds wrap .bbl lines at different widths; rendered spaces agree.
    assert "Proc. IEEE/CVF Int. Conf. Comput. Vis." in " ".join(minimal.split())
    assert "Example Publisher" not in minimal
    assert "https://example.org/data_a" in minimal
    assert len(minimal) < len(normal)


def assert_compiles(bibtex, tmp_path, style, count):
    if not all(shutil.which(name) for name in ("pdflatex", "bibtex", "kpsewhich")):
        pytest.skip("Install a TeX distribution to run the actual compiler regression")
    found = subprocess.run(["kpsewhich", style + ".bst"], capture_output=True, timeout=15)
    if found.returncode:
        pytest.skip(f"The optional {style}.bst is not installed")
    (tmp_path / "refs.bib").write_text(bibtex, encoding="utf-8")
    (tmp_path / "main.tex").write_text(
        r"\documentclass{article}\usepackage[T1]{fontenc}\usepackage{url}"
        r"\begin{document}\nocite{*}\bibliographystyle{" + style + r"}"
        r"\bibliography{refs}\end{document}",
        encoding="utf-8",
    )
    latex = [
        "pdflatex",
        "-no-shell-escape",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "main.tex",
    ]
    for command in (latex, ["bibtex", "main"], latex, latex):
        result = subprocess.run(
            command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45
        )
        log = result.stdout.decode("utf-8", errors="replace")
        assert result.returncode == 0, log
        assert 'string name "' not in log, log
    bbl = (tmp_path / "main.bbl").read_bytes().decode("utf-8", errors="strict")
    assert "\\bibitem" in bbl
    assert bbl.count("\\bibitem") == count
    # BibTeX can exit 0 while emitting warnings (e.g. empty journal).
    blg = (tmp_path / "main.blg").read_text(encoding="utf-8")
    assert not any(line.lower().startswith("warning--") for line in blg.splitlines()), blg
    assert "undefined" not in (tmp_path / "main.log").read_text(encoding="utf-8")
    assert (tmp_path / "main.pdf").is_file()
    return bbl
