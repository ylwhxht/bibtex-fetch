"""All fixtures are synthetic; unfetched input is never called downloaded data."""

import copy
import io
import json
import sys
import zipfile

import pytest
from fastapi.testclient import TestClient

from bibclean.bibliography import parse_bib
from bibclean.exports import export_files
from bibclean.formatting import format_bibtex
from bibclean.runner import new_job
from bibclean.storage import Store

INPUT = r"""@string{venue={2022 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)}}
@misc{downloaded, title={Fixture}, doi={10.1234/test}}
@inproceedings{unfetched_key,
  title={Original_input & 50%}, author={Example, Émile}, year={2022},
  booktitle=venue, month=June, pages={1–5}, note={Keep this input field},
  url={https://example.org/original_a}
}
"""
SOURCE = """@inproceedings{source, title={Fixture}, author={Example, Ada}, year={2025},
 booktitle={ICASSP 2025 - 2025 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)},
 pages={1--5}, url={https://example.org/source}}
"""


def mixed_job():
    job = new_job(INPUT, "fixture.bib", {"keep_keys": True})
    job["rows"][0].update(status="success", raw_bibtex=SOURCE, source_key="source")
    job["rows"][1].update(status="failed", reason="Synthetic unavailable source")
    return job


@pytest.mark.parametrize("status", ["failed", "pending", "processing"])
@pytest.mark.parametrize(
    "include_url,abbreviate", [(True, False), (False, False), (True, True), (False, True)]
)
def test_complete_export_preserves_every_key_and_input_field(
    tmp_path, status, include_url, abbreviate
):
    job = mixed_job()
    job["rows"][1]["status"] = status
    original = copy.deepcopy(job)
    store = Store(tmp_path)
    files = export_files(job, store, include_url=include_url, abbreviate=abbreviate)
    rows = parse_bib(files["merged.bib"])
    assert [row["original_key"] for row in rows] == ["downloaded", "unfetched_key"]
    assert rows[1]["original"]["note"] == "Keep this input field"
    assert rows[1]["original"]["author"] == r"Example, {\'E}mile"
    assert rows[1]["original"]["month"] == "June"
    assert all(("url" in row["original"]) == include_url for row in rows)
    if abbreviate:
        assert [row["original"]["booktitle"] for row in rows] == ["ICASSP", "IROS"]
    assert (
        format_bibtex(files["merged.bib"], include_url=include_url, abbreviate=abbreviate)[0]
        == files["merged.bib"]
    )
    assert "original input retained; not downloaded" in files["merged.bib"]
    assert files["entries/0001-downloaded.bib"] == SOURCE
    assert files["original.bib"] == INPUT
    assert files["process.jsonl"] == ""
    summary = json.loads(files["export-summary.json"])
    assert summary["input_count"] == summary["exported_count"] == 2
    assert summary["downloaded_count"] == summary["retained_input_count"] == 1
    assert summary["omitted_count"] == 0
    assert summary["rows"][1]["origin"] == "input"
    assert summary["rows"][1]["retrieval_status"] == status
    changes = json.loads(files["formatting.json"])["changes"]
    assert any(c["origin"] == "input" for c in changes)
    assert job == original
    partial = export_files(
        job, store, include_unfetched=False, include_url=include_url, abbreviate=abbreviate
    )
    assert partial["merged.bib"] == files["downloaded.bib"]
    assert json.loads(partial["export-summary.json"])["omitted_count"] == 1


def test_existing_jobs_api_preview_and_zip_share_complete_default(tmp_path, monkeypatch):
    import bibclean.app as api

    job = mixed_job()  # No include_unfetched setting, as in pre-upgrade saved jobs.
    monkeypatch.setattr(api, "JOBS", {job["id"]: job})
    monkeypatch.setattr(api, "STORE", Store(tmp_path))
    path = f"/api/jobs/{job['id']}/export"
    with TestClient(api.app) as client:
        response = client.get(path, params={"abbreviate": "true", "include_url": "false"})
        assert response.status_code == 200
        assert len(parse_bib(response.text)) == 2
        bundle = client.get(
            path, params={"format": "zip", "abbreviate": "true", "include_url": "false"}
        )
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            assert archive.read("merged.bib") == response.content
            assert len(parse_bib(archive.read("downloaded.bib").decode())) == 1
        assert len(parse_bib(client.get(path + "?include_unfetched=false").text)) == 1
        assert client.get(path + "?include_unfetched=invalid").status_code == 422


@pytest.mark.parametrize("downloaded_only", [False, True])
def test_cli_offline_failure_keeps_input_by_default(tmp_path, monkeypatch, downloaded_only):
    import bibclean.__main__ as cli

    source = tmp_path / "input.bib"
    source.write_text("@misc{original_key,note={No title or identifier}}", encoding="utf-8")
    output = tmp_path / "output"
    args = ["bibtex-fetch-cli", str(source), "-o", str(output), "--data-dir", str(tmp_path / "db")]
    if downloaded_only:
        args.append("--downloaded-only")
    monkeypatch.setattr(sys, "argv", args)
    assert cli.main() == 2  # Exporting the original must not report retrieval success.
    merged = (output / "merged.bib").read_text(encoding="utf-8")
    assert ("@misc{original_key," in merged) == (not downloaded_only)
    assert (output / "downloaded.bib").read_text(encoding="utf-8") == ""
