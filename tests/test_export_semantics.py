"""Export-only corrections; fixtures below are fictional, never crawl results."""

import copy
import json

import pytest

from bibclean.abbreviations import CONFERENCE_TITLES, abbreviation
from bibclean.bibliography import parse_bib
from bibclean.exports import export_files
from bibclean.formatting import format_bibtex
from bibclean.runner import new_job
from bibclean.storage import Store


@pytest.mark.parametrize(
    "full,short",
    [
        ("2024 IEEE Intelligent Vehicles Symposium (IV)", "IV"),
        (
            "2025 IEEE 28th International Conference on Intelligent Transportation Systems (ITSC)",
            "ITSC",
        ),
        ("2019 10th International Conference on Pattern Recognition Systems (ICPRS)", "ICPRS"),
        ("2018 IEEE International Conference on Vehicular Electronics and Safety (ICVES)", "ICVES"),
        ("2019 IEEE/CVF International Conference on Computer Vision Workshop (ICCVW)", "ICCVW"),
        (
            "Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV) Workshops",
            "ICCVW",
        ),
        (
            "IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) Workshops",
            "CVPRW",
        ),
        ("2022 IEEE 95th Vehicular Technology Conference: (VTC2022-Spring)", "VTC2022-Spring"),
        ("2023 IEEE 98th Vehicular Technology Conference (VTC2023-Fall)", "VTC2023-Fall"),
        ("2024 IEEE International Conference on Development and Learning (ICDL)", "ICDL"),
        (
            "2024 International Conference on Information and Communication Technology Convergence (ICTC)",
            "ICTC",
        ),
        (
            "2021 International Conference on Electrical, Computer and Energy Technologies (ICECET)",
            "ICECET",
        ),
        (
            "2025 5th International Conference on Neural Networks, Information and Communication Engineering (NNICE)",
            "NNICE",
        ),
        ("2025 IEEE Radar Conference (RadarConf25)", "RadarConf"),
        ("2025 IEEE Radar Conference (RadarConf2025)", "RadarConf"),
        ("2024 IEEE 22nd International Conference on Industrial Informatics (INDIN)", "INDIN"),
        (
            "Proceedings of the Thirty-ThirdInternational Joint Conference on Artificial Intelligence",
            "IJCAI",
        ),
        (
            "2021 18th Annual IEEE International Conference on Sensing, Communication, and Networking (SECON)",
            "SECON",
        ),
        ("2024 7th International Symposium on Autonomous Systems (ISAS)", "ISAS"),
        ("2024 43rd Chinese Control Conference (CCC)", "CCC"),
        ("Computer Vision -- ECCV 2024 Workshops", "ECCVW"),
        ("Neural Information Processing", "ICONIP"),
        ("Procedings of the British Machine Vision Conference 2013", "BMVC"),
        ("2024 German Microwave Conference (GeMiC)", "GeMiC"),
        ("2019 16th Conference on Computer and Robot Vision (CRV)", "CRV"),
        (
            "2022 IEEE 15th International Symposium on Embedded Multicore/Many-core Systems-on-Chip (MCSoC)",
            "MCSoC",
        ),
        ("2024 IEEE International Conference on Robotics and Biomimetics (ROBIO)", "ROBIO"),
        (
            "2024 IEEE International Conference on Visual Communications and Image Processing (VCIP)",
            "VCIP",
        ),
        (
            "The International Archives of the Photogrammetry, Remote Sensing and Spatial Information Sciences",
            "ISPRS Archives",
        ),
        ("Expert Systems with Applications", "Expert Syst. Appl."),
        ("Neural Networks", "Neural Netw."),
        (
            "IEEE Transactions on Neural Networks and Learning Systems",
            "IEEE Trans. Neural Netw. Learn. Syst.",
        ),
    ],
)
def test_extended_venue_spellings(full, short):
    expected = CONFERENCE_TITLES.get(short, short)
    if short.startswith("VTC20"):
        expected = "Proc. IEEE Veh. Technol. Conf. (" + short + ")"
    assert abbreviation(full)[1] == expected
    assert abbreviation(short)[1] == expected
    assert abbreviation(expected)[1] == expected


@pytest.mark.parametrize(
    "name",
    [
        "IEEE Intelligent Vehicles Symposium Workshops",
        "International Conference on Development and Learning and Epigenetic Robotics",
        "Neural Networks and Applications",
        "IEEE Radar Conference and Joint Symposium",
        "IEEE Vehicular Technology Conference (VTC2024-Spring) Workshops",
        "Computer Vision -- ECCV 2024 Workshops and Tutorials",
        "Proceedings of an Unknown Symposium",
    ],
)
def test_extended_aliases_do_not_swallow_distinct_events(name):
    assert abbreviation(name) is None


@pytest.mark.parametrize("typ", ["inbook", "incollection"])
@pytest.mark.parametrize("abbreviate", [False, True])
def test_chapters_retain_type_and_publisher(typ, abbreviate):
    raw = (
        "@"
        + typ
        + """{input,
      title={Synthetic proceedings fixture}, author={Example, Ada and Example, Bob},
      booktitle={Computer Vision -- ECCV 2024}, year={2024}, month={October},
      publisher={Example Publisher}, address={Example City}, series={Example Series},
      volume={123}, pages={1--9}, editor={Example, Chris}, isbn={0000}
    }"""
    )
    output, changes = format_bibtex(raw, abbreviate=abbreviate)
    before, after = (parse_bib(value)[0]["original"] for value in (raw, output))
    if abbreviate:
        before["booktitle"] = CONFERENCE_TITLES["ECCV"]
    assert after == before
    assert not any(change["action"] == "entry_type" for change in changes)
    assert format_bibtex(output, abbreviate=abbreviate) == (output, [])


@pytest.mark.parametrize(
    "identifier",
    [
        "doi={10.2139/ssrn.0000001}",
        "doi={10.36227/techrxiv.000001.000001/v1}",
        "url={https://doi.org/10.36227/techrxiv.000001.v2}",
        "doi={10.48550/arXiv.2401.00001}",
        "archivePrefix={arXiv}, eprint={2401.00001}",
        "url={https://arxiv.org/abs/2401.00001}",
    ],
)
def test_known_repository_article_without_journal_becomes_misc(identifier):
    raw = (
        "@article{keep_key,title={Synthetic preprint},author={Example, Ada},year={2024},"
        + identifier
        + "}"
    )
    output, changes = format_bibtex(raw)
    after = parse_bib(output)[0]["original"]
    before = parse_bib(raw)[0]["original"]
    before["ENTRYTYPE"] = "misc"
    if "arxiv" in identifier.casefold():
        before["note"] = "{arXiv}:2401.00001"
    assert after == before
    assert changes[0]["field"] == "ENTRYTYPE"
    assert format_bibtex(output) == (output, [])


@pytest.mark.parametrize(
    "fields",
    [
        "doi={10.1234/unclassified}",
        "eprint={2401.00001}",
        "publisher={Preprint publisher}",
        "doi={10.2139/ssrn.0000001},journal={Example Journal}",
        "doi={10.2139/ssrn.0000001},journaltitle={Example Journal}",
        "doi={10.2139/ssrn.0000001},booktitle={Example Proceedings}",
        "doi={10.2139/ssrn.0000001},crossref={parent}",
        "doi={10.2139/ssrn.0000001},xdata={shared}",
    ],
)
def test_missing_journal_is_not_filled_or_type_guessed(fields):
    raw = "@article{k,title={Synthetic fixture}," + fields + "}"
    assert format_bibtex(raw) == (raw, [])


@pytest.mark.parametrize(
    "raw",
    [
        "@string{venue={Computer Vision -- ECCV 2024}}",
        "% No entries\n@comment{Keep me}",
        "@inbook{k,title={Synthetic chapter},booktitle={Unknown Book}}",
    ],
)
def test_non_entries_and_unknown_books_are_unchanged(raw):
    assert format_bibtex(raw) == (raw, [])


TYPED_SOURCES = [
    "@article{source,title={Synthetic SSRN fixture},author={Example, Ada},year={2024},doi={10.2139/ssrn.0000001}}",
    "@article{source,title={Synthetic TechRxiv fixture},author={Example, Bob},year={2024},month=June,doi={10.36227/techrxiv.000001.000001/v1}}",
    "@article{source,title={Synthetic arXiv fixture},author={Example, Chris},year={2024},eprint={2401.00001},archivePrefix={arXiv}}",
    "@inbook{source,title={Synthetic conference fixture},author={Example, Dana},year={2024},booktitle={Computer Vision -- ECCV 2024},pages={1--9},publisher={Example Publisher}}",
]


def typed_job():
    job = new_job(
        "\n".join(
            raw.replace("{source,", "{input" + str(i) + ",") for i, raw in enumerate(TYPED_SOURCES)
        ),
        "fixture.bib",
        {"keep_keys": True},
    )
    for row, raw in zip(job["rows"], TYPED_SOURCES):
        row.update(status="success", source="test", source_key="source", raw_bibtex=raw)
    return job


@pytest.mark.parametrize(
    "include_url,abbreviate", [(True, False), (False, False), (True, True), (False, True)]
)
def test_export_type_fixes_are_logged_and_raw_is_untouched(tmp_path, include_url, abbreviate):
    job = typed_job()
    original = copy.deepcopy(job)
    files = export_files(job, Store(tmp_path), include_url=include_url, abbreviate=abbreviate)
    rows = parse_bib(files["merged.bib"])
    assert [row["original_key"] for row in rows] == ["input0", "input1", "input2", "input3"]
    assert [row["original"]["ENTRYTYPE"] for row in rows] == [
        "misc",
        "misc",
        "misc",
        "inbook",
    ]
    assert files["original.bib"] == job["original_text"]
    for i, raw in enumerate(TYPED_SOURCES):
        assert files[f"entries/{i + 1:04d}-input{i}.bib"] == raw
    changes = json.loads(files["formatting.json"])["changes"]
    types = [change for change in changes if change["action"] == "entry_type"]
    assert len(types) == 3 and all(change["reason"] for change in types)
    assert job == original
