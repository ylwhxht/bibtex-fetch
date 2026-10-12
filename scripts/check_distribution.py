"""Build first with uv build, then smoke-test the wheel outside the checkout."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SMOKE = r"""
from pathlib import Path
from importlib.metadata import version
from fastapi.testclient import TestClient
import bibclean
from bibclean.app import app
from bibclean.bibliography import parse_bib
from bibclean.matching import same_title

assert version("bibtex-fetch") == bibclean.__version__
assert Path(bibclean.__file__).is_relative_to(Path.cwd() / "venv")
assert same_title("{{A Test Title}}", "a test title.")
assert not same_title("C++ for Vision", "C for Vision")
with TestClient(app) as client:
    assert client.get("/api/health").json()["ai"] is False
    assert client.get("/api/health").json()["title_matching"] == "strict-v1"
    assert client.get("/api/jobs").json() == []
    assert client.get("/").status_code == 200
    for asset in ("app.js", "styles.css", "favicon.svg"):
        assert client.get("/static/" + asset).status_code == 200
    assert len(parse_bib(client.get("/api/sample").json()["text"])) == 3
    assert client.get("/api/abbreviations").json()["count"] == 107
    assert client.get("/api/health").json()["complete_export"] == "v1"
    assert client.get("/api/health").json()["export_formatting"] == "v2"
print("Installed wheel: UI, sample, abbreviations, version and empty local store OK")
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv", help="Path to the uv executable")
    parser.add_argument(
        "--wheel", type=Path, help="Check this exact wheel instead of the latest in dist/"
    )
    args = parser.parse_args()
    wheels = sorted((ROOT / "dist").glob("*.whl"), key=lambda path: path.stat().st_mtime)
    if args.wheel:
        wheel = args.wheel.resolve()
        if not wheel.is_file():
            parser.error("The specified wheel does not exist")
    elif wheels:
        wheel = wheels[-1]
    else:
        parser.error("No wheel found in dist/. Run uv build first.")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        for expected in (
            "bibclean/static/index.html",
            "bibclean/static/app.js",
            "bibclean/static/styles.css",
            "bibclean/static/favicon.svg",
            "bibclean/resources/sample.bib",
        ):
            assert expected in names, f"Missing wheel resource: {expected}"
        assert not any(".sqlite" in name or name.startswith("data/") for name in names)

    with tempfile.TemporaryDirectory(prefix="bibtex-fetch-wheel-") as directory:
        temp = Path(directory)
        environment = os.environ.copy()
        environment["BIBTEX_FETCH_DATA_DIR"] = str(temp / "data")
        python = temp / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [args.uv, "venv", "--python", sys.executable, str(temp / "venv")], check=True
        )
        subprocess.run(
            [
                args.uv,
                "pip",
                "install",
                "--python",
                str(python),
                "--require-hashes",
                "-r",
                str(ROOT / "requirements.txt"),
            ],
            check=True,
        )
        subprocess.run(
            [args.uv, "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
            check=True,
        )
        subprocess.run([str(python), "-I", "-c", SMOKE], cwd=temp, env=environment, check=True)
        for command in ("bibtex-fetch", "bibtex-fetch-cli"):
            entrypoint = python.parent / (command + (".exe" if os.name == "nt" else ""))
            subprocess.run([str(entrypoint), "--version"], cwd=temp, env=environment, check=True)
        # A missing-identifier input exercises the installed CLI and export path
        # without making any external requests or inventing downloaded content.
        source = temp / "no-identifier.bib"
        source.write_text("@misc{missing, note={No title or identifier}}", encoding="utf-8")
        result = subprocess.run(
            [str(python), "-I", "-m", "bibclean", str(source), "-o", str(temp / "output")],
            cwd=temp,
            env=environment,
            capture_output=True,
            encoding="utf-8",
        )
        assert result.returncode == 2, result.stderr
        assert result.stderr and "0/1" in result.stderr
        assert "@misc{missing," in (temp / "output" / "merged.bib").read_text(encoding="utf-8")
        assert (temp / "output" / "downloaded.bib").read_text(encoding="utf-8") == ""
        assert "@misc{missing," in (temp / "output" / "failed.bib").read_text(encoding="utf-8")
        assert '"kind": "request"' not in result.stdout
        assert (temp / "output" / "bibtex-fetch-results.zip").is_file()
        print("Installed CLI: offline failure reporting and export bundle OK")


if __name__ == "__main__":
    main()
