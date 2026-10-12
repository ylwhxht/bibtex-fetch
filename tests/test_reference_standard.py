"""Requested export standard: synthetic records, never fetched bibliography."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from bibclean.bibliography import parse_bib
from bibclean.exports import export_files
from bibclean.formatting import format_bibtex
from bibclean.publication_versions import PUBLICATION_VERSIONS
from bibclean.runner import new_job
from bibclean.storage import Store


def entry(raw):
    return parse_bib(raw)[0]["original"]


@pytest.mark.parametrize("include_url", [True, False])
def test_conference_standard_keeps_author_title_year_month_and_pages(include_url):
    raw = """@inproceedings{keep_key,author={Example, Ada and Example, Bob},
    title={Synthetic conference paper},year={2020},month={June},pages={2443--2451},
    booktitle={CVPR},publisher={IEEE},doi={10.1234/synthetic},url={https://example.org}}"""
    output, changes = format_bibtex(raw, include_url=include_url, abbreviate=True)
    before, after = entry(raw), entry(output)
    assert after["booktitle"] == "Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit. (CVPR)"
    assert "publisher" not in after
    for field in ("ID", "author", "title", "year", "month", "pages", "doi"):
        assert after[field] == before[field]
    assert any(c["field"] == "publisher" and c["action"] == "remove" for c in changes)
    assert format_bibtex(output, include_url=include_url, abbreviate=True) == (output, [])
    assert entry(format_bibtex(raw, abbreviate=False)[0])["publisher"] == "IEEE"


@pytest.mark.parametrize("typ", ["book", "inbook", "incollection", "techreport", "misc"])
def test_non_conference_publishers_are_preserved_even_with_conference_booktitle(typ):
    raw = "@" + typ + "{k,title={Synthetic},booktitle={CVPR},publisher={Keep},month=June}"
    after = entry(format_bibtex(raw, abbreviate=True)[0])
    assert after["publisher"] == "Keep" and after["ENTRYTYPE"] == typ
    assert after["month"] == "June"


@pytest.mark.parametrize(
    "venue", ["SAE Technical Paper Series", "Unknown Conference", "ICCV and Other Events"]
)
def test_unlisted_and_sae_conference_publishers_are_preserved(venue):
    raw = "@inproceedings{k,title={Synthetic},booktitle={" + venue + "},publisher={Keep}}"
    assert format_bibtex(raw, abbreviate=True) == (raw, [])


@pytest.mark.parametrize(
    "key,journal,expected",
    [
        ("RAL", "IEEE RA-L", "IEEE Robot. Autom. Lett."),
        (
            "TCSVT",
            "IEEE Trans. Circuit Syst. Video Technol.",
            "IEEE Trans. Circuits Syst. Video Technol.",
        ),
    ],
)
def test_journal_spelling_corrections(key, journal, expected):
    for expression in ("{" + journal + "}", key):
        output, _ = format_bibtex("@article{k,journal=" + expression + "}", abbreviate=True)
        assert entry(output)["journal"] == expected


def publication_fixtures():
    # Titles identify the three user-requested rules. Authors and IDs here are
    # intentionally synthetic and must be preserved, not replaced from rules.
    return [
        "@misc{" + key + ",title={" + record["title"] + "},author={Example, Ada},"
        "year={2000},archivePrefix={arXiv},eprint={2401.00001},"
        "note={{arXiv}:2401.00001},publisher={Example Publisher}}"
        for key, record in PUBLICATION_VERSIONS.items()
    ]


@pytest.mark.parametrize("abbreviate", [True, False])
def test_explicit_publication_versions_preserve_identity_and_eprint(abbreviate):
    for raw in publication_fixtures():
        before = entry(raw)
        output, changes = format_bibtex(raw, abbreviate=abbreviate)
        after = entry(output)
        assert after["ENTRYTYPE"] == "inproceedings"
        for field in ("ID", "title", "author", "archiveprefix", "eprint"):
            assert after[field] == before[field]
        assert "note" not in after and "howpublished" not in after
        for field, value in PUBLICATION_VERSIONS[before["ID"]]["fields"].items():
            assert after[field] == value
        if before["ID"] == "tent":
            assert "pages" not in after and "month" not in after
        assert ("publisher" in after) != abbreviate
        assert any(c["action"] == "published_version" and c["source"] for c in changes)
        assert format_bibtex(output, abbreviate=abbreviate) == (output, [])


def test_publication_rules_do_not_guess_from_title_or_key_alone():
    raw = "@misc{tent,title={Different paper},year={2024}}"
    output, changes = format_bibtex(raw)
    assert output == raw and changes[0]["action"] == "manual_review"
    raw = "@misc{different_key,title={Segment Anything},year={2023}}"
    assert format_bibtex(raw) == (raw, [])


def test_saved_job_api_uses_input_key_without_mutating_source(tmp_path, monkeypatch):
    import bibclean.app as api

    job = new_job(publication_fixtures()[0], "synthetic.bib", {"keep_keys": True})
    raw = publication_fixtures()[0].replace("{segment_anything,", "{remote_source_key,")
    job["rows"][0].update(status="success", source_key="remote_source_key", raw_bibtex=raw)
    before = copy.deepcopy(job)
    store = Store(tmp_path)
    monkeypatch.setattr(api, "JOBS", {job["id"]: job})
    monkeypatch.setattr(api, "STORE", store)
    files = export_files(job, store, abbreviate=True)
    with TestClient(api.app) as client:
        response = client.get(f"/api/jobs/{job['id']}/export", params={"abbreviate": "true"})
        assert response.text == files["merged.bib"]
        after = entry(response.text)
        assert after["ID"] == "segment_anything" and after["pages"] == "4015--4026"
        assert after["ENTRYTYPE"] == "inproceedings"
    assert files["entries/0001-segment_anything.bib"] == raw
    assert files["original.bib"] == job["original_text"]
    assert job == before
    changes = json.loads(files["formatting.json"])["changes"]
    assert all(c["exported_key"] == "segment_anything" for c in changes)


@pytest.mark.parametrize("style", ["IEEEtran", "IEEEtranN"])
def test_requested_standard_compiles_and_prints_arxiv_note(tmp_path, style):
    from test_latex_compat import assert_compiles

    raw = "\n".join(
        [
            *publication_fixtures(),
            "@misc{preprint,title={Synthetic preprint},author={Example, Bob},year={2024},"
            "archivePrefix={arXiv},eprint={2405.08816}}",
            "@inproceedings{conference,title={Synthetic conference},author={Example, Chris},"
            "year={2020},month={June},pages={1--9},booktitle={CVPR},publisher={IEEE}}",
        ]
    )
    output, _ = format_bibtex(raw, include_url=False, abbreviate=True)
    bbl = assert_compiles(output, tmp_path, style, 5)
    visible = bbl.replace("{", "").replace("}", "")
    assert visible.count("arXiv:2405.08816") == 1
    assert "arXiv:2401.00001" not in visible
    assert "Proc. IEEE/CVF" in visible and "ICLR" in visible
    assert "Example Publisher" not in visible
