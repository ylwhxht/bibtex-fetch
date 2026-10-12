"""Recovery paths use synthetic HTTP responses, never invented production data."""

import asyncio
import time

import httpx
import pytest

from bibclean import transport
from bibclean.bibliography import fingerprint, input_ids, parse_bib
from bibclean.exports import export_files
from bibclean.runner import Runner, new_job
from bibclean.storage import Store
from bibclean.transport import Fetcher, FetchError, utcnow


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    transport.LAST_REQUEST.clear()
    real_sleep = asyncio.sleep

    async def sleep(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(transport.asyncio, "sleep", sleep)


def run_job(tmp_path, text, handler, sources):
    store = Store(tmp_path)
    job = new_job(text, "synthetic.bib", {"sources": sources, "keep_keys": True})
    runner = Runner(store, job)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    asyncio.run(runner.run(Fetcher(store, runner.emit, client=client)))
    return job, store, store.events(job["id"])


def test_crossref_expands_candidates_and_downloads_exact_response(tmp_path):
    raw = "@article{remote,title={Bird’s-Eye Radar–Camera Fusion},year={2024}}"
    counts = []

    def handler(request):
        if request.url.path == "/works":
            counts.append(int(request.url.params["rows"]))
            items = [
                {"title": [f"Different Title {i}"], "DOI": f"10.1234/other{i}"} for i in range(7)
            ]
            items.append({"title": ["Bird’s-Eye Radar–Camera Fusion"], "DOI": "10.1234/match"})
            return httpx.Response(200, json={"message": {"items": items[: counts[-1]]}})
        assert "/10.1234/match/" in request.url.path
        return httpx.Response(200, text=raw)

    job, store, events = run_job(
        tmp_path, "@misc{input,title={Bird's-Eye Radar-Camera Fusion}}", handler, ["crossref"]
    )
    assert counts == [5, 25]
    assert job["rows"][0]["status"] == "success"
    assert job["rows"][0]["failure_code"] == ""
    assert job["rows"][0]["raw_bibtex"] == raw
    assert any(e["kind"] == "search_fallback" for e in events)
    files = export_files(job, store)
    assert parse_bib(files["merged.bib"])[0]["original_key"] == "input"
    assert files["entries/0001-input.bib"] == raw


@pytest.mark.parametrize(
    "download_title,expected",
    [("DemoFusion: Radar Perception", "success"), ("Other Model", "failed")],
)
def test_arxiv_keyword_fallback_keeps_full_download_title_gate(tmp_path, download_title, expected):
    queries = []

    def handler(request):
        if request.url.host == "export.arxiv.org":
            query = request.url.params["search_query"]
            queries.append(query)
            entry = (
                ""
                if " AND " not in query
                else (
                    "<entry><id>https://arxiv.org/abs/2401.12345</id>"
                    "<title>DemoFusion: Radar Perception</title></entry>"
                )
            )
            return httpx.Response(
                200, text=f'<feed xmlns="http://www.w3.org/2005/Atom">{entry}</feed>'
            )
        return httpx.Response(200, text=f"@misc{{remote,title={{{download_title}}}}}")

    job, _, events = run_job(
        tmp_path, "@misc{input,title={DemoFusion: Radar Perception}}", handler, ["arxiv"]
    )
    assert len(queries) == 2 and " AND " in queries[1]
    assert job["rows"][0]["status"] == expected
    assert any(e["kind"] == "search_fallback" for e in events)
    if expected == "failed":
        assert job["rows"][0]["failure_code"] == "title_mismatch"


def test_antibot_html_is_reported_once_per_run_and_retained_as_evidence(tmp_path):
    requests = []
    html = "<!doctype html><title>Making sure you're not a bot!</title><p>Anubis</p>"

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    text = "@misc{one,title={First}}\n@misc{two,title={Second}}"
    job, store, events = run_job(tmp_path, text, handler, ["dblp"])
    assert len(requests) == 1
    assert all(r["failure_code"] == "access_blocked" for r in job["rows"])
    assert any(e["kind"] == "source_unavailable" for e in events)
    files = export_files(job, store)
    assert files[f"responses/{fingerprint(html)}.txt"] == html
    assert files["original.bib"] == text
    assert len(parse_bib(files["merged.bib"])) == 2
    assert "HTML" in files["retrieval-review.md"]
    cache_key = fingerprint(requests[0] + "\napplication/json")
    assert store.cached(cache_key, 0) is None


def test_two_transient_429_responses_can_recover_without_losing_evidence(tmp_path):
    attempts, events = [], []

    def handler(request):
        attempts.append(request)
        return (
            httpx.Response(429, text="busy", headers={"Retry-After": "1"})
            if len(attempts) < 3
            else httpx.Response(200, text="{}")
        )

    async def run():
        fetcher = Fetcher(
            Store(tmp_path),
            lambda k, m, **kw: events.append({"kind": k, **kw}),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            assert (await fetcher.get("https://api.crossref.org/works"))["status"] == 200
        finally:
            await fetcher.close()

    asyncio.run(run())
    assert len(attempts) == 3
    assert [e["status"] for e in events if e["kind"] == "response"] == [429, 429, 200]


def test_long_retry_after_is_respected_without_repeated_requests(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(429, text="busy", headers={"Retry-After": "600"})

    async def run():
        fetcher = Fetcher(
            Store(tmp_path),
            lambda *a, **kw: None,
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            for _ in range(2):
                with pytest.raises(FetchError) as error:
                    await fetcher.get("https://api.crossref.org/works")
                assert error.value.code == "rate_limited"
        finally:
            await fetcher.close()

    asyncio.run(run())
    assert len(requests) == 1


def test_legacy_html_cache_does_not_prevent_a_fresh_request(tmp_path):
    store, events, requests = Store(tmp_path), [], []
    url = "https://dblp.org/search/publ/api"
    html = "<html>Old Anubis challenge</html>"
    store.put_evidence(
        fingerprint(url + "\napplication/json"),
        {
            "status": 200,
            "url": url,
            "body": html,
            "sha256": fingerprint(html),
            "content_type": "text/html",
            "retrieved_at": utcnow(),
        },
        time.time(),
    )

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"result": {"hits": {"hit": []}}})

    async def run():
        fetcher = Fetcher(
            store,
            lambda k, m, **kw: events.append(k),
            cache=True,
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            assert not (await fetcher.get(url))["cached"]
            assert (await fetcher.get(url))["cached"]
        finally:
            await fetcher.close()

    asyncio.run(run())
    assert len(requests) == 1
    assert "cache_ignored" in events and "cache" in events


def test_ambiguous_candidates_are_exported_for_manual_selection(tmp_path):
    def handler(request):
        assert request.url.path == "/works"
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {"title": ["Same Title"], "DOI": doi}
                        for doi in ("10.1234/preprint", "10.1234/journal")
                    ]
                }
            },
        )

    text = "@article{input,title={Same Title},year={2024}}"
    job, store, _ = run_job(tmp_path, text, handler, ["crossref"])
    row = job["rows"][0]
    assert row["failure_code"] == "ambiguous_title" and row["raw_bibtex"] is None
    files = export_files(job, store)
    assert all(
        doi in files["retrieval-review.md"] for doi in ("10.1234/preprint", "10.1234/journal")
    )
    assert files["original.bib"] == text


@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"journal": "arXiv preprint arXiv:2401.12345"}, "2401.12345"),
        ({"note": "arXiv:hep-th/9901001v2"}, "hep-th/9901001v2"),
        ({"journal": "arXiv:2401.12345", "note": "arXiv:2401.12346"}, ""),
        ({"note": "Reference 2401.12345"}, ""),
        ({"note": "arXiv:2401.123456789"}, ""),
    ],
)
def test_only_explicit_unambiguous_arxiv_ids_are_extracted(entry, expected):
    original = dict(entry)
    assert input_ids(entry)[1] == expected
    assert entry == original
