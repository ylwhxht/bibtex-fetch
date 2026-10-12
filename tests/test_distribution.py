"""Installation resources, writable paths and launcher behavior."""

import json
from pathlib import Path

import pytest

from bibclean import __version__, config, launcher


def test_explicit_data_directory_and_legacy_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BIBCLEAN_DATA_DIR", "old")
    monkeypatch.setenv("BIBTEX_FETCH_DATA_DIR", "new")
    assert config.data_directory() == tmp_path / "new"
    monkeypatch.delenv("BIBTEX_FETCH_DATA_DIR")
    assert config.data_directory() == tmp_path / "old"
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize(
    "platform,environment,suffix",
    [
        ("win32", "LOCALAPPDATA", "BibTeXFetch"),
        ("linux", "XDG_DATA_HOME", "bibtex-fetch"),
        ("darwin", None, "Library/Application Support/BibTeXFetch"),
    ],
)
def test_platform_data_paths_are_outside_package(
    tmp_path, monkeypatch, platform, environment, suffix
):
    monkeypatch.delenv("BIBTEX_FETCH_DATA_DIR", raising=False)
    monkeypatch.delenv("BIBCLEAN_DATA_DIR", raising=False)
    monkeypatch.setattr(config.sys, "platform", platform)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    if environment:
        monkeypatch.setenv(environment, str(tmp_path))
    assert config.data_directory() == tmp_path / suffix
    assert not config.data_directory().exists()


def test_package_assets_served_independent_of_current_directory(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import bibclean.app as api
    from bibclean.bibliography import parse_bib
    from bibclean.storage import Store

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, "STORE", Store(tmp_path / "db"))
    monkeypatch.setattr(api, "JOBS", {})
    with TestClient(api.app) as client:
        assert client.get("/api/health").json()["version"] == __version__
        assert client.get("/api/health").json()["title_matching"] == "strict-v2"
        assert client.get("/api/health").json()["retrieval_diagnostics"] == "v1"
        assert client.get("/api/health").json()["export_formatting"] == "v2"
        assert client.get("/").status_code == 200
        for asset in ("app.js", "styles.css", "favicon.svg"):
            assert client.get("/static/" + asset).status_code == 200
        sample = client.get("/api/sample").json()["text"]
        assert len(parse_bib(sample)) == 3
        assert client.get("/api/jobs").json() == []
    public_example = Path(__file__).resolve().parent.parent / "examples" / "sample.bib"
    assert sample == public_example.read_text(encoding="utf-8")


def test_launcher_passes_data_directory_before_starting_server(tmp_path, monkeypatch):
    class FreeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def settimeout(self, value):
            pass

        def connect_ex(self, address):
            return 1

    calls = []
    monkeypatch.setattr(launcher.socket, "socket", FreeSocket)
    monkeypatch.setattr(
        launcher.uvicorn,
        "run",
        lambda app, **kwargs: calls.append((app, kwargs, config.data_directory())),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["bibtex-fetch", "--no-browser", "--port", "8877", "--data-dir", str(tmp_path)],
    )
    assert launcher.main() == 0
    assert calls == [
        ("bibclean.app:app", {"host": "127.0.0.1", "port": 8877, "log_level": "info"}, tmp_path)
    ]


def test_launcher_does_not_open_unrelated_occupied_service(monkeypatch):
    import io

    class OccupiedSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def settimeout(self, value):
            pass

        def connect_ex(self, address):
            return 0

    monkeypatch.setattr(launcher.socket, "socket", OccupiedSocket)
    monkeypatch.setattr(
        launcher,
        "urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps({"app": "other"}).encode()),
    )
    monkeypatch.setattr("sys.argv", ["bibtex-fetch", "--no-browser"])
    assert launcher.main() == 1
