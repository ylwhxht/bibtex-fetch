import asyncio
import io
import zipfile

import httpx
import pytest

from bibclean import transport
from bibclean.bibliography import BibError, fingerprint, parse_bib
from bibclean.crawler import Crawler, rewrite_key
from bibclean.exports import export_files, zip_bytes
from bibclean.runner import Runner, new_job
from bibclean.storage import Store
from bibclean.transport import Fetcher, FetchError

# Deliberately synthetic fixtures. They are used only in tests, never in the UI.
RAW = " @article{SourceKey,\r\n  title = {{A Test Title}},\r\n  author = {Doe, Jane},\r\n  year = {2024},\r\n  doi = {10.1234/test}\r\n}\r\n"
SETTINGS = {"sources": ["crossref"], "cache": False, "keep_keys": True, "mailto": ""}


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    transport.LAST_REQUEST.clear()
    real_sleep = asyncio.sleep

    async def sleep(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(transport.asyncio, "sleep", sleep)


def client_for(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


def logger():
    events = []

    def emit(kind, message, **fields):
        events.append({"kind": kind, "message": message, **fields})

    return events, emit


@pytest.mark.parametrize(
    "bad",
    [
        "@article{ok,title={Good}}\n@article{broken,title={Missing}",
        "@article{ok,title={Good}}\n@article{broken,title={Bad} year={2020}}",
        "@article{x,title=undefined_macro}",
    ],
)
def test_malformed_input_never_silently_loses_rows(bad):
    with pytest.raises(BibError):
        parse_bib(bad)


def test_macros_duplicate_keys_and_nested_latex_are_preserved():
    text = '@string{venue="A Journal"}\n@article{Same,title={{Nested {Title}}},journal=venue}\n@misc{same,title={Second}}'
    rows = parse_bib(text)
    assert len(rows) == 2
    assert rows[0]["original"]["journal"] == "A Journal"
    assert rows[1]["key"] == "same_2"
    assert rows[1]["original_key"] == "same"
    assert rows[0]["raw"].startswith("@article{Same,")


def test_key_rewrite_leaves_comments_fields_and_line_endings_untouched():
    raw = "@comment{Example @article{SourceKey,title={Not a record}}}\r\n" + RAW
    actual = rewrite_key(raw, "InputKey")
    assert actual == "@comment{Example @article{SourceKey,title={Not a record}}}\r\n" + RAW.replace(
        "@article{SourceKey,", "@article{InputKey,", 1
    )
    assert parse_bib(actual)[0]["original_key"] == "InputKey"


def test_crossref_full_month_and_source_external_macros_do_not_rewrite_text():
    raw = "@article{k,title={An article},month=June,year={2024}}"
    assert parse_bib(raw)[0]["original"]["month"] == "June"
    assert parse_bib(raw)[0]["raw"] == raw
    with_external_macro = raw.replace("month=June", "journal=external_journal_name")
    rows = parse_bib(with_external_macro, raw_strings=True)
    assert rows[0]["raw"] == with_external_macro
    assert rewrite_key(with_external_macro, "newkey") == with_external_macro.replace(
        "{k,", "{newkey,"
    )


def test_identifier_download_matches_title_without_rewriting_source_fields(tmp_path):
    events, emit = logger()
    seen = []

    def handler(request):
        seen.append(str(request.url))
        assert request.headers["accept"].startswith("application/x-bibtex")
        return httpx.Response(200, text=RAW)

    async def run():
        fetcher = Fetcher(Store(tmp_path), emit, client=client_for(handler))
        entry = {
            "ID": "input",
            "doi": "10.1234/test",
            "title": "a test title.",
            "year": "1901",
        }
        result = await Crawler(fetcher, emit, SETTINGS).crawl(entry)
        await fetcher.close()
        assert result["status"] == "success"
        assert result["raw_bibtex"] == RAW
        assert result["source_key"] == "SourceKey"
        assert result["sha256"] == fingerprint(RAW)
        assert result["title_match"] == "matched"

    asyncio.run(run())
    assert len(seen) == 1
    assert [e["kind"] for e in events if e["kind"] in {"request", "response", "bibtex"}] == [
        "request",
        "response",
        "bibtex",
    ]
    assert not any("score" in e for e in events)


@pytest.mark.parametrize(
    "query,expected_status,request_count",
    [
        ("Second Title", "success", 2),
        ("Unknown Title", "failed", 1),
    ],
)
def test_title_search_shows_actual_results_and_selection(
    tmp_path, query, expected_status, request_count
):
    events, emit = logger()

    def handler(request):
        if request.url.path == "/works":
            assert request.url.params["query.bibliographic"] == query
            return httpx.Response(
                200,
                json={
                    "message": {
                        "items": [
                            {"DOI": "10.1234/first", "title": ["First Title"]},
                            {"DOI": "10.1234/second", "title": ["Second Title"]},
                        ]
                    }
                },
            )
        assert "10.1234/second" in request.url.path
        return httpx.Response(200, text=RAW.replace("A Test Title", "Second Title"))

    async def run():
        fetcher = Fetcher(Store(tmp_path), emit, client=client_for(handler))
        result = await Crawler(fetcher, emit, SETTINGS).crawl({"ID": "x", "title": query})
        await fetcher.close()
        assert result["status"] == expected_status

    asyncio.run(run())
    assert sum(e["kind"] == "request" for e in events) == request_count
    if expected_status == "success":
        assert next(e for e in events if e["kind"] == "selection")["rule"] == "same_title"
        assert any(e["kind"] == "title_match" for e in events)
    else:
        assert not any(e["kind"] == "selection" for e in events)
        assert any(e["kind"] == "no_title_match" for e in events)
    assert len(next(e for e in events if e["kind"] == "search_results")["hits"]) == 2


def test_html_block_page_is_saved_but_never_merged(tmp_path):
    events, emit = logger()
    store = Store(tmp_path)
    html = "<div>Access restricted</div><!-- @article{x,title={Bogus}} -->"

    async def run():
        fetcher = Fetcher(
            store,
            emit,
            client=client_for(
                lambda r: httpx.Response(200, text=html, headers={"content-type": "text/html"})
            ),
        )
        result = await Crawler(fetcher, emit, SETTINGS).crawl({"ID": "x", "doi": "10.1234/test"})
        await fetcher.close()
        assert result["status"] == "failed"
        assert result["raw_bibtex"] is None
        assert "HTML" in result["errors"][0]["message"]

    asyncio.run(run())
    assert store.evidence(fingerprint(html))["body"] == html
    assert not any(e["kind"] == "bibtex" for e in events)


def test_doi_fallback_and_real_redirect_events(tmp_path):
    events, emit = logger()
    seen = []

    def handler(request):
        seen.append(request.url.host)
        if request.url.host == "api.crossref.org":
            return httpx.Response(404, text="Not found")
        if request.url.host == "data.datacite.org":
            return httpx.Response(
                302,
                headers={
                    "location": "https://data.crosscite.org:443/application/x-bibtex/10.1234/test"
                },
            )
        return httpx.Response(200, text=RAW)

    async def run():
        fetcher = Fetcher(Store(tmp_path), emit, client=client_for(handler))
        result = await Crawler(
            fetcher, emit, {**SETTINGS, "sources": ["crossref", "datacite"]}
        ).crawl({"ID": "x", "doi": "10.1234/test"})
        await fetcher.close()
        assert result["status"] == "success"
        assert result["source"] == "DataCite"
        assert result["source_url"].startswith("https://data.crosscite.org")

    asyncio.run(run())
    assert seen == ["api.crossref.org", "data.datacite.org", "data.crosscite.org"]
    assert [e["status"] for e in events if e["kind"] == "response"] == [404, 302, 200]
    assert sum(e["kind"] == "redirect" for e in events) == 1


def test_retry_emits_both_requests_and_preserves_failure_response(tmp_path):
    events, emit = logger()
    seen = []
    store = Store(tmp_path)

    def handler(request):
        seen.append(request)
        return (
            httpx.Response(429, text="Rate limited", headers={"Retry-After": "1"})
            if len(seen) == 1
            else httpx.Response(200, text=RAW)
        )

    async def run():
        fetcher = Fetcher(store, emit, client=client_for(handler))
        result = await fetcher.get("https://api.crossref.org/works/x")
        assert result["body"] == RAW
        await fetcher.close()

    asyncio.run(run())
    assert len(seen) == 2
    assert sum(e["kind"] == "retry" for e in events) == 1
    assert [e["status"] for e in events if e["kind"] == "response"] == [429, 200]
    assert store.evidence(fingerprint("Rate limited"))["body"] == "Rate limited"


def test_timeout_is_not_reported_as_empty_search(tmp_path):
    events, emit = logger()

    def handler(request):
        raise httpx.ReadTimeout("test timeout", request=request)

    async def run():
        fetcher = Fetcher(Store(tmp_path), emit, client=client_for(handler))
        with pytest.raises(FetchError, match="连接失败"):
            await fetcher.get("https://api.crossref.org/works")
        await fetcher.close()

    asyncio.run(run())
    assert sum(e["kind"] == "request" for e in events) == 2
    assert sum(e["kind"] == "network_error" for e in events) == 2
    assert not any(e["kind"] == "response" for e in events)


def test_cache_events_never_pretend_to_make_http_requests(tmp_path):
    events, emit = logger()
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, text=RAW)

    async def run():
        fetcher = Fetcher(Store(tmp_path), emit, cache=True, client=client_for(handler))
        first = await fetcher.get("https://api.crossref.org/works/x")
        second = await fetcher.get("https://api.crossref.org/works/x")
        await fetcher.close()
        assert not first["cached"] and second["cached"]
        assert first["retrieved_at"] == second["retrieved_at"]

    asyncio.run(run())
    assert len(seen) == 1
    assert sum(e["kind"] == "request" for e in events) == 1
    assert events[-1]["kind"] == "cache"


def test_redirect_outside_sources_is_not_followed(tmp_path):
    events, emit = logger()
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1:22/"})

    async def run():
        fetcher = Fetcher(Store(tmp_path), emit, client=client_for(handler))
        with pytest.raises(FetchError, match="不在已支持来源"):
            await fetcher.get("https://api.crossref.org/works/x")
        await fetcher.close()

    asyncio.run(run())
    assert len(seen) == 1


def test_runner_export_preserves_order_raw_text_and_failed_inputs(tmp_path):
    store = Store(tmp_path)
    text = "@article{one,doi={10.1234/test}}\n@article{two,doi={10.1234/test}}\n@misc{three,note={No title or identifier}}"
    job = new_job(text, "input.bib", SETTINGS)
    runner = Runner(store, job)

    async def run():
        fetcher = Fetcher(
            store, runner.emit, client=client_for(lambda r: httpx.Response(200, text=RAW))
        )
        await runner.run(fetcher)

    asyncio.run(run())
    assert job["state"] == "done"
    assert [r["status"] for r in job["rows"]] == ["success", "success", "failed"]
    assert job["request_count"] == 2
    events = store.events(job["id"])
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    files = export_files(job, store)
    assert files["merged.bib"] == rewrite_key(RAW, "one") + "\n\n" + rewrite_key(RAW, "two")
    assert files["entries/0001-one.bib"] == RAW
    assert files["original.bib"] == text
    assert parse_bib(files["failed.bib"])[0]["original_key"] == "three"
    assert [r["original_key"] for r in parse_bib(files["merged.bib"])] == ["one", "two"]
    with zipfile.ZipFile(io.BytesIO(zip_bytes(files))) as z:
        assert z.read("entries/0001-one.bib").decode("utf-8") == RAW
        assert z.read(f"responses/{fingerprint(RAW)}.txt").decode("utf-8") == RAW
    # Source-key mode keeps raw text intact until a duplicate key requires a suffix.
    job["settings"] = {**SETTINGS, "keep_keys": False}
    files = export_files(job, store)
    assert files["merged.bib"] == RAW + "\n\n" + rewrite_key(RAW, "SourceKey_2")


def test_cancel_retains_completed_entries_and_allows_resume(tmp_path):
    store = Store(tmp_path)
    job = new_job(
        "@misc{one,doi={10.1234/one}}\n@misc{two,doi={10.1234/two}}", "input.bib", SETTINGS
    )
    runner = Runner(store, job)

    async def run():
        second_started = asyncio.Event()
        wait_forever = asyncio.Event()

        async def handler(request):
            if "two" in request.url.path:
                second_started.set()
                await wait_forever.wait()
            return httpx.Response(200, text=RAW)

        fetcher = Fetcher(store, runner.emit, client=client_for(handler))
        task = asyncio.create_task(runner.run(fetcher))
        await second_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert job["state"] == "cancelled"
        assert [r["status"] for r in job["rows"]] == ["success", "pending"]
        fresh = Runner(store, job)
        fetcher = Fetcher(
            store, fresh.emit, client=client_for(lambda r: httpx.Response(200, text=RAW))
        )
        await fresh.run(fetcher)

    asyncio.run(run())
    assert job["state"] == "done"
    assert all(r["status"] == "success" for r in job["rows"])
    assert sum(e["kind"] == "job_cancelled" for e in store.events(job["id"])) == 1


def test_api_import_errors_exports_and_origin(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import bibclean.app as api

    monkeypatch.setattr(api, "STORE", Store(tmp_path))
    monkeypatch.setattr(api, "JOBS", {})
    with TestClient(api.app) as client:
        assert client.get("/api/health").json()["app"] == "bibtex-fetch"
        assert client.post("/api/jobs", json={"text": "bad"}).status_code == 422
        assert (
            client.post(
                "/api/jobs", json={"text": RAW}, headers={"Origin": "https://outside.example"}
            ).status_code
            == 403
        )
        response = client.post("/api/jobs", json={"text": RAW})
        assert response.status_code == 200
        job = response.json()
        assert job["total"] == 1
        assert client.get(f"/api/jobs/{job['id']}/export").status_code == 409
        bundle = client.get(f"/api/jobs/{job['id']}/export?format=zip")
        assert bundle.status_code == 200
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as z:
            assert z.read("merged.bib") == b""
            assert z.read("original.bib").decode("utf-8") == RAW
        assert client.get(f"/api/jobs/{job['id']}/events?stream=false").json() == []
