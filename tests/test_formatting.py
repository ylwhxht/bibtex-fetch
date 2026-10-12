import copy
import io
import json
import zipfile

import pytest

from bibclean.abbreviations import abbreviation, string_definitions
from bibclean.bibliography import parse_bib
from bibclean.exports import export_files
from bibclean.formatting import format_bibtex
from bibclean.runner import new_job
from bibclean.storage import Store

# Synthetic fixtures for export formatting only; never displayed as crawl data.
RAW = (
    "@inproceedings{source,\r\n"
    "  title = {{A {Nested} Title}},\r\n"
    "  booktitle = {2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)},\r\n"
    "  URL = {https://example.org/a,b?x={q}%20},\r\n"
    "  doi = {10.1234/test},\r\n"
    "  note = {Keep url={literal}, IEEE Conference on Computer Vision and Pattern Recognition},\r\n"
    "  month = June\r\n}\r\n"
)


def completed_job():
    job = new_job("@misc{input,title={Synthetic input}}", "test.bib", {"keep_keys": True})
    job["rows"][0].update(status="success", source_key="source", raw_bibtex=RAW, source="test")
    return job


@pytest.mark.parametrize(
    "include_url,abbreviate", [(True, False), (False, False), (True, True), (False, True)]
)
def test_four_export_combinations_preserve_all_other_text(include_url, abbreviate):
    output, changes = format_bibtex(RAW, include_url=include_url, abbreviate=abbreviate)
    expected = RAW.replace("month = June", "month = {June}")
    if not include_url:
        expected = expected.replace("\r\n  URL = {https://example.org/a,b?x={q}%20},", "")
    if abbreviate:
        expected = expected.replace(
            "{2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)}", "{CVPR}"
        )
    assert output == expected
    entry = parse_bib(output)[0]["original"]
    assert ("url" in entry) == include_url
    assert entry["doi"] == "10.1234/test"
    assert len(changes) == (not include_url) + abbreviate + 1


@pytest.mark.parametrize(
    "raw",
    [
        '@misc{k,URL="https://example.org/a,b"}',
        "@misc{k,URL={https://example.org/},}",
        "@misc(k,URL={https://example.org/},title={Keep})",
        "@misc{k,title={Keep},Url={https://example.org/}}",
        "@misc{k,url={one},URL={two},title={Keep}}",
    ],
)
def test_url_removal_handles_any_position_and_empty_entries(raw):
    output, _ = format_bibtex(raw, include_url=False)
    entry = parse_bib(output)[0]["original"]
    assert "url" not in entry
    if "Keep" in raw:
        assert entry["title"] == "Keep"


def test_macros_latex_and_comments_keep_unrelated_text():
    raw = (
        "@String{venue={IEEE Transactions on Pattern Analysis and Machine Intelligence}}\n"
        "@comment{url={not a field}}\n"
        "@article{k, journal=venue, title={Keep {\\LaTeX}},\n"
        '  booktitle="Proceedings of the 36th AAAI Conference on Artificial Intelligence",\n'
        "  note={Nested {commas, braces} and \\url{https://example.org}}}"
    )
    output, changes = format_bibtex(raw, abbreviate=True)
    assert output == raw.replace(
        "journal=venue", "journal={IEEE Trans. Pattern Anal. Mach. Intell.}"
    ).replace(
        'booktitle="Proceedings of the 36th AAAI Conference on Artificial Intelligence"',
        "booktitle={AAAI}",
    )
    assert len(changes) == 2
    unknown = "@article{k,journal=UnknownMacro,title={Keep},year={2024}}"
    assert format_bibtex(unknown, abbreviate=True) == (unknown, [])
    bare = "@article{k,journal=TPAMI,title={Keep}}"
    assert (
        parse_bib(format_bibtex(bare, abbreviate=True)[0])[0]["original"]["journal"]
        == "IEEE Trans. Pattern Anal. Mach. Intell."
    )


def test_url_removal_retains_comments_next_to_field():
    raw = "@misc{k,\n% Keep https://comment.example/\n url={https://remove.example/} % Keep trailing comment\n,\n title={Keep}}"
    output, _ = format_bibtex(raw, include_url=False)
    assert (
        output
        == "@misc{k,\n% Keep https://comment.example/\n  % Keep trailing comment\n\n title={Keep}}"
    )


@pytest.mark.parametrize(
    "full,key,short",
    [
        (
            "2025 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)",
            "CVPR",
            "CVPR",
        ),
        (
            "2025 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)",
            "CVPRW",
            "CVPRW",
        ),
        ("Proceedings of the IEEE/CVF International Conference on Computer Vision", "ICCV", "ICCV"),
        ("IEEE International Conference on Computer Vision Workshops", "ICCVW", "ICCVW"),
        ("Computer Vision -- ECCV 2024", "ECCV", "ECCV"),
        ("Advances in Neural Information Processing Systems 37", "NIPS", "NeurIPS"),
        ("Proceedings of the 32nd ACM International Conference on Multimedia", "ACMMM", "ACM MM"),
        ("ACM Trans. Graph.", "TOG", "ACM TOG"),
        ("The Visual Computer", "TVCOMP", "Vis. Comput."),
        (
            "IEEE Transactions on Circuits and Systems for Video Technology",
            "TCSVT",
            "IEEE Trans. Circuit Syst. Video Technol.",
        ),
    ],
)
def test_known_venue_variants_follow_supplied_spelling(full, key, short):
    assert abbreviation(full) == (key, short)


@pytest.mark.parametrize(
    "name",
    [
        "CVPR and Other Events",
        "International Conference on Computer Vision Workshops and Tutorials",
        "Pattern Recognition and Image Analysis",
        "Unknown Journal of Vision",
        "IEEE Signal Processing Magazine Special Issue Collection",
    ],
)
def test_unlisted_or_joint_venues_are_not_guessed(name):
    raw = "@article{k,journal={" + name + "}}"
    assert format_bibtex(raw, abbreviate=True) == (raw, [])


def test_exports_change_only_merged_and_record_exact_edits(tmp_path):
    job = completed_job()
    original = copy.deepcopy(job)
    store = Store(tmp_path)
    files = export_files(job, store, include_url=False, abbreviate=True)
    entry = parse_bib(files["merged.bib"])[0]["original"]
    assert entry["booktitle"] == "CVPR" and "url" not in entry
    assert entry["ID"] == "input"
    assert files["entries/0001-input.bib"] == RAW
    assert files["original.bib"] == job["original_text"]
    assert files["process.jsonl"] == ""
    report = json.loads(files["formatting.json"])
    assert {c["field"] for c in report["changes"]} == {"booktitle", "url", "month"}
    assert report["latex_compatibility"] is True
    assert files["abbreviations.bib"].count("@String(TOG ") == 1
    assert "@String(TOG = {ACM TOG})" in files["abbreviations.bib"]
    assert "@String(RAL = {IEEE RA-L})" in string_definitions()
    assert job == original
    reverted = export_files(job, store, include_url=True, abbreviate=False)
    assert reverted["merged.bib"] == RAW.replace("{source,", "{input,").replace(
        "month = June", "month = {June}"
    )
    assert "abbreviations.bib" not in reverted


def test_api_existing_job_export_options_and_saved_cli_defaults(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import bibclean.app as api

    job = completed_job()
    job["settings"].update(include_url=False, abbreviate=True)
    monkeypatch.setattr(api, "STORE", Store(tmp_path))
    monkeypatch.setattr(api, "JOBS", {job["id"]: job})
    path = f"/api/jobs/{job['id']}/export"
    with TestClient(api.app) as client:
        entry = parse_bib(client.get(path).text)[0]["original"]
        assert entry["booktitle"] == "CVPR" and "url" not in entry
        unchanged = client.get(path + "?include_url=true&abbreviate=false").text
        assert unchanged == RAW.replace("{source,", "{input,").replace(
            "month = June", "month = {June}"
        )
        bundle = client.get(path + "?format=zip&include_url=false&abbreviate=true")
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            assert archive.read("merged.bib") == client.get(path).content
            assert archive.read("entries/0001-input.bib").decode() == RAW
        assert client.get(path + "?abbreviate=unknown").status_code == 422
        assert "@String(NIPS = {NeurIPS})" in client.get("/api/abbreviations").json()["bibtex"]
