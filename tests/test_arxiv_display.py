"""Fictional fixtures for source-derived arXiv display and removed-preset migration."""

import asyncio
import copy
import io
import json
import sys
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from bibclean import transport
from bibclean.abbreviations import CONFERENCE_TITLES
from bibclean.bibliography import parse_bib
from bibclean.exports import export_files
from bibclean.formatting import format_bibtex
from bibclean.runner import Runner, new_job
from bibclean.storage import Store
from bibclean.transport import Fetcher

SOURCE = """@misc{source, title={Synthetic preprint}, author={Example, Ada}, year={2024},
  archivePrefix={arXiv}, eprint={2401.00001v2}, primaryClass={cs.CV},
  url={https://arxiv.org/abs/2401.00001v2}}"""


def entry(text):
    return parse_bib(text)[0]["original"]


@pytest.mark.parametrize(
    "fields,ident",
    [
        ("archivePrefix={arXiv},eprint={2401.00001}", "2401.00001"),
        ("eprinttype={arxiv},eprint={2401.00001v2}", "2401.00001v2"),
        ("eprint={arXiv:2401.00001}", "2401.00001"),
        ("doi={10.48550/arXiv.2401.00001}", "2401.00001"),
        ("url={https://arxiv.org/pdf/2401.00001v2.pdf}", "2401.00001v2"),
        ("archivePrefix={arXiv},eprint={cs.AI/0001001v2}", "cs.AI/0001001v2"),
        (
            "archivePrefix={arXiv},eprint={2401.00001v2},doi={10.48550/arXiv.2401.00001}",
            "2401.00001v2",
        ),
        ("journal={arXiv preprint arXiv:2401.00001}", "2401.00001"),
    ],
)
@pytest.mark.parametrize("include_url", [False, True])
@pytest.mark.parametrize("abbreviate", [False, True])
def test_explicit_identifiers_survive_export_options(fields, ident, include_url, abbreviate):
    raw = "@misc{keep_key,title={Synthetic fixture}," + fields + "}"
    output, changes = format_bibtex(raw, include_url=include_url, abbreviate=abbreviate)
    assert entry(output)["note"] == "{arXiv}:" + ident
    assert entry(output)["ID"] == "keep_key"
    assert any(c["action"] == "arxiv_display" for c in changes)
    for field, value in entry(raw).items():
        if field != "url" or include_url:
            assert entry(output)[field] == value
    assert format_bibtex(output, include_url=include_url, abbreviate=abbreviate) == (output, [])


@pytest.mark.parametrize("field", ["note", "howpublished"])
def test_existing_visible_locator_is_not_duplicated(field):
    raw = SOURCE.replace("primaryClass=", field + "={{arXiv}:2401.00001v2},primaryClass=")
    assert format_bibtex(raw) == (raw, [])


def test_existing_notes_macros_comments_and_published_venue_are_preserved():
    raw = (
        "@string{status={Accepted manuscript}}\n"
        "@article(k,title={Synthetic},journal={Example Journal},year=2024,\n"
        "% retain this comment\n note=status # {; A_B},\n"
        "archivePrefix={arXiv},eprint={2401.00001},url={https://arxiv.org/abs/2401.00001})"
    )
    output, _ = format_bibtex(raw, include_url=False, abbreviate=True)
    assert "% retain this comment" in output
    values = entry(output.replace("% retain this comment\n", ""))
    assert values["ENTRYTYPE"] == "article" and values["journal"] == "Example Journal"
    assert values["note"] == r"Accepted manuscript; A\_B; {arXiv}:2401.00001"
    assert format_bibtex(output, include_url=False, abbreviate=True) == (output, [])


@pytest.mark.parametrize("suffix", ["", ",", ", % final comment\n"])
def test_insertion_with_trailing_url_removal_and_empty_existing_field(suffix):
    raw = (
        "@misc{k,howpublished={},eprint={2401.00001},archivePrefix={arXiv},url={https://arxiv.org/abs/2401.00001}"
        + suffix
        + "}"
    )
    output, _ = format_bibtex(raw, include_url=False)
    values = entry(output.replace("% final comment\n", ""))
    assert values["note"] == "{arXiv}:2401.00001"
    assert values["howpublished"] == ""
    assert "url" not in values
    assert format_bibtex(output, include_url=False) == (output, [])


@pytest.mark.parametrize(
    "fields",
    [
        "archivePrefix={arXiv}",
        "archivePrefix={arXiv},eprint={not-an-id}",
        "archivePrefix={arXiv},eprint={2401.00001},url={https://arxiv.org/abs/2401.00002}",
        "archivePrefix={arXiv},eprint={2401.00001v1},url={https://arxiv.org/abs/2401.00001v2}",
    ],
)
def test_missing_or_conflicting_ids_are_reported_without_guessing(tmp_path, fields):
    raw = "@misc{keep_key,title={Synthetic fixture}," + fields + "}"
    output, changes = format_bibtex(raw)
    assert output == raw
    assert len(changes) == 1 and changes[0]["action"] == "manual_review"
    job = new_job(raw, "fixture.bib", {})
    files = export_files(job, Store(tmp_path))
    assert "`keep_key`" in files["formatting-review.md"]
    assert changes[0]["reason"] in files["formatting-review.md"]
    assert files["original.bib"] == raw


@pytest.mark.parametrize(
    "fields", ["eprint={2401.00001}", "archivePrefix={Other},eprint={2401.00001}"]
)
def test_other_or_unknown_archive_is_not_labelled_arxiv(fields):
    raw = "@misc{k,title={Synthetic fixture}," + fields + "}"
    assert format_bibtex(raw) == (raw, [])


@pytest.mark.parametrize("include_url", [False, True])
@pytest.mark.parametrize("abbreviate", [False, True])
def test_download_through_api_and_zip_keeps_source_and_visible_id(
    tmp_path, monkeypatch, include_url, abbreviate
):
    import bibclean.app as api

    transport.LAST_REQUEST.clear()
    raw_input = "@misc{keep_key,doi={10.1234/synthetic}}"
    store = Store(tmp_path / "store")
    job = new_job(raw_input, "fixture.bib", {"sources": ["crossref"], "keep_keys": True})
    runner = Runner(store, job)

    async def crawl():
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, text=SOURCE))
        )
        await runner.run(Fetcher(store, runner.emit, client=client))

    asyncio.run(crawl())
    assert job["rows"][0]["status"] == "success" and job["request_count"] == 1
    before = copy.deepcopy(job)
    monkeypatch.setattr(api, "JOBS", {job["id"]: job})
    monkeypatch.setattr(api, "STORE", store)
    params = {"include_url": include_url, "abbreviate": abbreviate}
    path = f"/api/jobs/{job['id']}/export"
    with TestClient(api.app) as client:
        response = client.get(path, params=params)
        assert response.status_code == 200
        assert entry(response.text)["note"] == "{arXiv}:2401.00001v2"
        assert ("url" in entry(response.text)) == include_url
        bundle = client.get(path, params={**params, "format": "zip"})
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            assert archive.read("merged.bib") == response.content
            assert archive.read("entries/0001-keep_key.bib").decode() == SOURCE
            assert archive.read("original.bib").decode() == raw_input
            assert archive.read(f"responses/{job['rows'][0]['sha256']}.txt").decode() == SOURCE
            changes = json.loads(archive.read("formatting.json"))["changes"]
            assert any(c["action"] == "arxiv_display" for c in changes)
    assert job == before


def test_old_saved_preset_and_old_query_cannot_reenable_minimal_mode(tmp_path, monkeypatch):
    import bibclean.app as api

    authors = " and ".join(f"Example, Person{i}" for i in range(12))
    raw = (
        "@inproceedings{k,title={Synthetic},author={"
        + authors
        + "},booktitle={ICCV},year=2025,month=June,publisher={Example Publisher},url={https://example.org}}"
    )
    job = new_job(
        raw, "fixture.bib", {"tpami_minimal": True, "include_url": True, "abbreviate": True}
    )
    monkeypatch.setattr(api, "JOBS", {job["id"]: job})
    monkeypatch.setattr(api, "STORE", Store(tmp_path))
    with TestClient(api.app) as client:
        path = f"/api/jobs/{job['id']}/export"
        response = client.get(path, params={"tpami_minimal": "true"})
        assert response.content == client.get(path).content
        values = entry(response.text)
        assert values["author"] == authors and values["booktitle"] == CONFERENCE_TITLES["ICCV"]
        assert values["month"] == "June" and "publisher" not in values
        assert values["url"] == "https://example.org"
        full = entry(client.get(path, params={"abbreviate": "false"}).text)
        assert full["publisher"] == "Example Publisher"
        assert "tpami_minimal" not in client.get("/api/health").json()
        assert 'id="tpami-minimal"' not in client.get("/").text


def test_cli_no_longer_offers_minimal_mode(monkeypatch, capsys):
    import bibclean.__main__ as cli

    monkeypatch.setattr(sys, "argv", ["bibtex-fetch-cli", "--help"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == 0
    assert "--tpami-minimal" not in capsys.readouterr().out


@pytest.mark.parametrize("style", ["plain", "abbrv", "IEEEtran", "IEEEtranN"])
@pytest.mark.parametrize("include_url", [False, True])
@pytest.mark.parametrize("abbreviate", [False, True])
def test_arxiv_locator_is_actually_printed_by_bibtex(tmp_path, style, include_url, abbreviate):
    from test_latex_compat import assert_compiles

    fixtures = [
        SOURCE,
        SOURCE.replace("{source,", "{with_note,").replace(
            "primaryClass=",
            "howpublished={Technical report},note={Accepted manuscript},primaryClass=",
        ),
        "@article{journal,title={Synthetic article},author={Example, Bob},year=2024,journal={arXiv preprint arXiv:2401.00002}}",
        "@misc{legacy,title={Synthetic old identifier},author={Example, Chris},year=2000,archivePrefix={arXiv},eprint={cs.AI/0001001}}",
    ]
    job = new_job("\n".join(fixtures), "fixture.bib", {})
    files = export_files(
        job, Store(tmp_path / "store"), include_url=include_url, abbreviate=abbreviate
    )
    bbl = assert_compiles(files["merged.bib"], tmp_path, style, len(fixtures))
    visible = bbl.replace("{", "").replace("}", "")
    assert visible.count("arXiv:2401.00001v2") == 2
    assert visible.count("arXiv:2401.00002") == 1
    assert visible.count("arXiv:cs.AI/0001001") == 1
    words = " ".join(visible.casefold().split())
    assert "accepted manuscript" in words and "technical report" in words
