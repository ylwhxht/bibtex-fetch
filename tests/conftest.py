"""Tests stay offline and never load a user's saved bibliography database."""

import httpx
import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_app_data(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("BIBTEX_FETCH_DATA_DIR", str(tmp_path_factory.mktemp("app-data")))
        yield


@pytest.fixture(autouse=True)
def block_external_http(monkeypatch):
    async def blocked(*args, **kwargs):
        raise AssertionError("Tests must use MockTransport, not external HTTP")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)
