"""Fictional fixtures for the optional IEEE/TPAMI formatting policy."""

import copy
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from bibclean.abbreviations import CONFERENCES
from bibclean.bibliography import parse_bib
from bibclean.exports import export_files
from bibclean.formatting import format_bibtex
from bibclean.runner import new_job
from bibclean.storage import Store
from bibclean.tpami import CONFERENCE_NAMES, IEEE_NAMES, compact_author, venue_name

AUTHORS = " and ".join(
    f"Example, {name}" for name in ("Ada", "Bob", "Chris", "Dana", "Eve", "Finn", "Gia")
)
SOURCE = (
    "@inproceedings{source, title={Synthetic_fixture}, author={" + AUTHORS + "},"
    "booktitle={2025 IEEE/CVF International Conference on Computer Vision (ICCV)},"
    "year={2025}, month=June, pages={1--9}, doi={10.1234/synthetic},"
    "url={https://example.org/synthetic}, publisher={Example Publisher}, address={Example City}}"
)


def entry(text):
    return parse_bib(text)[0]["original"]


def example_job():
    job = new_job("@misc{input,doi={10.1234/synthetic}}", "synthetic.bib", {"keep_keys": True})
    job["rows"][0].update(status="success", raw_bibtex=SOURCE, source_key="source")
    job["state"] = "completed"
    return job


@pytest.mark.parametrize("include_url", [False, True])
@pytest.mark.parametrize("abbreviate", [False, True])
def test_preset_has_explicit_precedence_and_preserves_core_fields(include_url, abbreviate):
    formatted, changes = format_bibtex(
        SOURCE, tpami_minimal=True, include_url=include_url, abbreviate=abbreviate
    )
    values = entry(formatted)
    assert values["author"] == "Example, Ada and others"
    assert values["booktitle"] == "Proc. IEEE/CVF Int. Conf. Comput. Vis."
    assert not {"url", "publisher", "address", "month"} & values.keys()
    assert values["pages"] == "1--9" and values["year"] == "2025"
    assert values["doi"] == "10.1234/synthetic" and values["title"] == r"Synthetic\_fixture"
    assert {c["action"] for c in changes} == {
        "tpami_authors",
        "tpami_abbreviate",
        "tpami_remove",
        "latex_compatibility",
    }
    assert format_bibtex(formatted, tpami_minimal=True) == (formatted, [])
    normal, _ = format_bibtex(SOURCE)
    assert entry(normal)["author"] == AUTHORS
    assert entry(normal)["publisher"] == "Example Publisher"


def test_all_known_venues_have_idempotent_word_abbreviations():
    assert CONFERENCES == set(CONFERENCE_NAMES)
    for key, short in IEEE_NAMES.items():
        assert venue_name(key) is not None
        assert venue_name(short)[1] == short
    assert venue_name("ICCV")[1] == "Proc. Int. Conf. Comput. Vis."
    assert venue_name("2017 IEEE International Conference on Computer Vision (ICCV)")[1] == (
        "Proc. IEEE Int. Conf. Comput. Vis."
    )
    assert venue_name(
        "ICASSP 2025 - 2025 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)"
    )[1] == ("Proc. IEEE Int. Conf. Acoust., Speech Signal Process.")
    assert venue_name("IROS")[1] == "Proc. IEEE/RSJ Int. Conf. Intell. Robots Syst."
    assert venue_name("ICCV and Tutorials") is None


@pytest.mark.parametrize("count", [1, 5, 6, 7, 15])
def test_author_threshold_and_grouped_corporate_names(count):
    names = [r"{Research and Development Group}"] + [
        f"Example, Person{i}" for i in range(count - 1)
    ]
    value = " and ".join(names)
    assert compact_author(value) == (names[0] + " and others" if count > 6 else value)
    assert compact_author("Example, Ada and others") == "Example, Ada and others"
    assert (
        compact_author(r"Example, {\'A}da and Example, Bob") == r"Example, {\'A}da and Example, Bob"
    )


def test_journal_core_information_and_book_series_are_retained():
    raw = """@article{journal, author={Example, Ada}, title={Synthetic}, year=2025,
      journal={IEEE Transactions on Pattern Analysis and Machine Intelligence},
      volume=47, number=1, pages={1--9}, month=June, doi={10.1234/test},
      url={https://example.org/test}}"""
    values = entry(format_bibtex(raw, tpami_minimal=True)[0])
    assert values["journal"] == "IEEE Trans. Pattern Anal. Mach. Intell."
    assert values["month"] == "June" and values["number"] == "1" and values["volume"] == "47"
    assert "url" not in values
    series = SOURCE.replace("publisher=", "series={Synthetic Series},volume={1},publisher=")
    assert entry(format_bibtex(series, tpami_minimal=True)[0])["publisher"] == "Example Publisher"
    no_doi = SOURCE.replace("doi={10.1234/synthetic},", "")
    assert entry(format_bibtex(no_doi, tpami_minimal=True)[0])["month"] == "June"


def test_only_publication_year_is_not_erased_from_venue():
    raw = SOURCE.replace("year={2025},", "")
    formatted, changes = format_bibtex(raw, tpami_minimal=True)
    assert entry(formatted)["booktitle"] == entry(raw)["booktitle"]
    assert any(c["field"] == "year" and c["action"] == "manual_review" for c in changes)


def test_existing_partial_authors_are_not_guessed():
    six = " and ".join(AUTHORS.split(" and ")[:6])
    assert compact_author(six + " and others") == "Example, Ada and others"
    partial = "Example, Ada and Example, Bob and others"
    assert compact_author(partial) == partial
    raw = "@misc{k,title={Synthetic},year=2025,author={" + partial + "}}"
    _, changes = format_bibtex(raw, tpami_minimal=True)
    assert any(c["field"] == "author" and c["action"] == "manual_review" for c in changes)


@pytest.mark.parametrize(
    "raw",
    [
        "@misc{k,title={Synthetic},author={Example, Ada},year={2025},url={https://example.org/data_a}}",
        "@article{k,title={Synthetic},author={Example, Ada},year={2025},journal={IEEE Access},doi={10.1234/test},url={https://example.org/a}}",
        "@article{k,title={Synthetic},author={Example, Ada},year={2025},journal={IEEE Access},volume=1,pages={1--9},note={Early access},url={https://example.org/a}}",
    ],
)
def test_online_or_incomplete_references_retain_locator_even_with_no_url(raw):
    values = entry(format_bibtex(raw, tpami_minimal=True, include_url=False)[0])
    assert values["url"] == entry(raw)["url"]


def test_unknown_venue_and_missing_metadata_reported_without_invention(tmp_path):
    raw = "@article{unresolved,title={Synthetic},journal={Unlisted Journal and Workshop}}"
    job = new_job(raw, "synthetic.bib", {})
    files = export_files(job, Store(tmp_path), tpami_minimal=True)
    assert entry(files["merged.bib"]) == entry(raw)
    notes = files["manual-review.md"]
    assert "unresolved" in notes and "author" in notes and "year" in notes and "journal" in notes
    assert files["original.bib"] == raw
    assert "abbreviations.bib" not in files


def test_api_zip_and_existing_jobs_toggle_without_mutation(tmp_path, monkeypatch):
    import bibclean.app as api

    job = example_job()
    original = copy.deepcopy(job)
    store = Store(tmp_path)
    monkeypatch.setattr(api, "STORE", store)
    monkeypatch.setattr(api, "JOBS", {job["id"]: job})
    path = f"/api/jobs/{job['id']}/export"
    with TestClient(api.app) as client:
        assert client.get("/api/health").json()["tpami_minimal"] == "v1"
        normal = client.get(path).text
        preset = client.get(path, params={"tpami_minimal": "true"})
        assert preset.status_code == 200 and entry(preset.text)["ID"] == "input"
        assert preset.text != normal
        bundle = client.get(path, params={"tpami_minimal": "true", "format": "zip"})
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            assert archive.read("merged.bib") == preset.content
            assert archive.read("entries/0001-input.bib").decode() == SOURCE
            assert archive.read("original.bib").decode() == job["original_text"]
            assert "manual-review.md" in archive.namelist()
            assert json.loads(archive.read("formatting.json"))["options"]["tpami_minimal"] is True
        assert client.get(path + "?tpami_minimal=false").text == normal
        assert client.get(path + "?tpami_minimal=bad").status_code == 422
    assert job == original
    job["settings"]["tpami_minimal"] = True
    assert export_files(job, store)["merged.bib"] == preset.text


def test_top_level_comments_survive_optional_field_removal():
    raw = SOURCE.replace("publisher=", "% keep comment\n publisher=")
    formatted = format_bibtex(raw, tpami_minimal=True)[0]
    assert "% keep comment" in formatted
    assert "pages={1--9}" in formatted
    assert format_bibtex(formatted, tpami_minimal=True) == (formatted, [])
