"""Synthetic offline cases for rejection, fallback and source provenance."""

import asyncio

import httpx
import pytest

from bibclean import transport
from bibclean.bibliography import fingerprint, parse_bib
from bibclean.crawler import Crawler
from bibclean.exports import export_files
from bibclean.matching import same_title
from bibclean.runner import Runner, new_job
from bibclean.storage import Store
from bibclean.transport import Fetcher

RAW = "@article{source,title={A Test Title},author={Doe, Jane},year={2024}}"
WRONG = RAW.replace("A Test Title", "A Different Title")
SETTINGS = {"sources": ["crossref", "dblp"], "keep_keys": True, "cache": False}


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    transport.LAST_REQUEST.clear()
    real_sleep = asyncio.sleep

    async def sleep(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(transport.asyncio, "sleep", sleep)


@pytest.mark.parametrize(
    "left,right",
    [
        ("{{A Test Title}}", "a  test\n title."),
        (r"\textit{A}~Test Title", "<i>A</i> Test Title"),
        (r"A \& B", "A &amp; B"),
        ("Caf\u00e9", "Cafe\u0301"),
        (r"A $x^2$ Test", r"A $x^2$ Test"),
    ],
)
def test_display_only_differences_match(left, right):
    assert same_title(left, right)


@pytest.mark.parametrize(
    "left,right",
    [
        ("C++ for Vision", "C for Vision"),
        ("Model 2", "Model 3"),
        ("A-B Model", "A B Model"),
        ("A & B", "A B"),
        ("A Title: Part 1", "A Title: Part 2"),
        (r"A $x+2$ Test", r"A $x-2$ Test"),
        (r"A $x_2$ Test", r"A $x^2$ Test"),
        (r"A $X$ Test", r"A $x$ Test"),
        ("Model x\u00b2", "Model x2"),
        ("Model x<sup>2</sup>", "Model x2"),
        (r"A \unknown{Test}", "A Test"),
        ("Caf\u00e9", "Cafe"),
        ("", ""),
        ("{}", " "),
    ],
)
def test_meaningful_differences_and_empty_titles_never_match(left, right):
    assert not same_title(left, right)


def run_job(tmp_path, text, handler, sources=None):
    store = Store(tmp_path)
    settings = {**SETTINGS, "sources": sources or SETTINGS["sources"]}
    job = new_job(text, "synthetic-test.bib", settings)
    runner = Runner(store, job)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    asyncio.run(runner.run(Fetcher(store, runner.emit, client=client)))
    return job, store, store.events(job["id"])


def empty_search(request):
    if request.url.host == "export.arxiv.org":
        return httpx.Response(200, text='<feed xmlns="http://www.w3.org/2005/Atom"/>')
    if request.url.host == "dblp.org":
        return httpx.Response(200, json={"result": {"hits": {"hit": []}}})
    return httpx.Response(200, json={"message": {"items": []}})


@pytest.mark.parametrize(
    "field,source,download_path",
    [
        ("doi={10.1234/test}", "crossref", "/works/10.1234/test/transform/application/x-bibtex"),
        ("doi={10.1234/test}", "datacite", "/application/x-bibtex/10.1234/test"),
        ("eprint={2401.12345}", "arxiv", "/bibtex/2401.12345"),
        ("url={https://dblp.org/rec/test/record}", "dblp", "/rec/test/record.bib"),
    ],
)
def test_identifier_routes_reject_wrong_downloaded_title(tmp_path, field, source, download_path):
    def handler(request):
        if request.url.path == download_path:
            return httpx.Response(200, text=WRONG)
        return empty_search(request)

    job, store, events = run_job(
        tmp_path, "@misc{input,title={A Test Title}," + field + "}", handler, [source]
    )
    assert job["rows"][0]["status"] == "failed"
    mismatch = next(e for e in events if e["kind"] == "title_mismatch")
    assert mismatch["input_title"] == "A Test Title"
    assert mismatch["downloaded_title"] == "A Different Title"
    assert mismatch["sha256"] == fingerprint(WRONG)
    assert not any(e["kind"] == "bibtex" for e in events)
    files = export_files(job, store)
    assert files["merged.bib"] == ""
    assert files[f"responses/{fingerprint(WRONG)}.txt"] == WRONG
    assert parse_bib(files["failed.bib"])[0]["original_key"] == "input"


@pytest.mark.parametrize("downloaded", [WRONG, "@misc{source,year={2024}}"])
def test_same_search_title_does_not_allow_mismatching_or_missing_download_title(
    tmp_path, downloaded
):
    def handler(request):
        if request.url.path == "/works":
            return httpx.Response(
                200,
                json={"message": {"items": [{"title": ["A Test Title"], "DOI": "10.1234/test"}]}},
            )
        return httpx.Response(200, text=downloaded)

    job, store, events = run_job(
        tmp_path, "@misc{input,title={A Test Title}}", handler, ["crossref"]
    )
    assert job["rows"][0]["status"] == "failed"
    assert any(e["kind"] == "selection" for e in events)
    assert any(e["kind"] == "title_mismatch" for e in events)
    assert export_files(job, store)["merged.bib"] == ""


@pytest.mark.parametrize("stage", ["search", "download"])
def test_title_rejection_continues_to_next_source_and_keeps_rejected_evidence(tmp_path, stage):
    def handler(request):
        if request.url.host == "api.crossref.org":
            if request.url.path == "/works":
                return httpx.Response(
                    200,
                    json={
                        "message": {
                            "items": [
                                {
                                    "title": [
                                        "Different Title" if stage == "search" else "A Test Title"
                                    ],
                                    "DOI": "10.1234/wrong",
                                }
                            ]
                        }
                    },
                )
            assert stage == "download", "A nonmatching search result must never be downloaded"
            return httpx.Response(200, text=WRONG)
        if request.url.path == "/search/publ/api":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "hits": {
                            "hit": [
                                {
                                    "info": {
                                        "title": "A Test Title.",
                                        "key": "test/matched",
                                    }
                                }
                            ]
                        }
                    }
                },
            )
        assert request.url.path == "/rec/test/matched.bib"
        return httpx.Response(200, text=RAW)

    job, store, events = run_job(tmp_path, "@misc{input,title={A Test Title}}", handler)
    row = job["rows"][0]
    assert row["status"] == "success" and row["source"] == "DBLP"
    assert row["title_match"] == "matched" and row["raw_bibtex"] == RAW
    files = export_files(job, store)
    assert "A Different Title" not in files["merged.bib"]
    assert files["entries/0001-input.bib"] == RAW
    assert any(e["kind"] == "title_match" for e in events)
    if stage == "download":
        assert files[f"responses/{fingerprint(WRONG)}.txt"] == WRONG


def test_multiple_distinct_same_title_hits_are_not_arbitrarily_selected():
    events = []
    crawler = Crawler(
        None, lambda kind, message, **kw: events.append({"kind": kind, **kw}), SETTINGS
    )
    hits = [
        {"title": "A Test Title", "id": key, "bib_url": f"https://dblp.org/rec/{key}.bib"}
        for key in ("one", "two")
    ]
    assert crawler.select(hits, "A Test Title", "DBLP") is None
    assert events[-1]["kind"] == "ambiguous_title"
    # Duplicate copies of the same source URL do not introduce a second identity.
    assert crawler.select([hits[0], hits[0]], "A Test Title", "DBLP") == hits[0]


def test_identifier_only_inputs_explicitly_log_that_title_was_not_compared(tmp_path):
    job, _store, events = run_job(
        tmp_path,
        "@misc{input,doi={10.1234/test}}",
        lambda request: httpx.Response(200, text=RAW),
        ["crossref"],
    )
    row = job["rows"][0]
    assert row["status"] == "success" and row["title_match"] == "not_checked"
    assert any(e["kind"] == "title_unavailable" for e in events)
    assert not any(e["kind"] == "title_match" for e in events)


def test_cached_response_must_pass_the_same_title_gate(tmp_path):
    store, events = Store(tmp_path), []

    def emit(kind, message, **fields):
        events.append({"kind": kind, **fields})

    async def run():
        url = "https://data.datacite.org/application/x-bibtex/10.1234%2Ftest"
        accept = "application/x-bibtex, text/plain;q=0.9"
        warm = Fetcher(
            store,
            emit,
            client=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, text=WRONG))
            ),
        )
        await warm.get(url, accept=accept)
        await warm.close()
        events.clear()

        def unexpected_network(request):
            raise AssertionError("A cached response should not issue a new HTTP request")

        fetcher = Fetcher(
            store,
            emit,
            cache=True,
            client=httpx.AsyncClient(transport=httpx.MockTransport(unexpected_network)),
        )
        result = await Crawler(fetcher, emit, {"sources": ["datacite"]}).crawl(
            {"ID": "input", "title": "A Test Title", "doi": "10.1234/test"}
        )
        await fetcher.close()
        assert result["status"] == "failed" and result["raw_bibtex"] is None

    asyncio.run(run())
    assert any(e["kind"] == "cache" for e in events)
    assert any(e["kind"] == "title_mismatch" for e in events)
    assert not any(e["kind"] in {"request", "bibtex"} for e in events)
