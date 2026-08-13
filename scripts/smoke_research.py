#!/usr/bin/env python3
"""End-to-end smoke test for llm-researcher.

Drives the full research lifecycle (create -> poll -> verify -> export)
against either:

* an in-process FastAPI app (default; no server or ports needed), or
* a running llm-researcher server over HTTP (``--live --base-url ...``).

Designed for humans AND automated LLM agents: it prints a machine-readable
JSON summary, writes artifacts (``summary.json``, the document, and the
markdown export) into ``--outdir``, and exits non-zero on any failure.

Usage:
    # In-process (recommended — boots the app on an in-memory SQLite DB and
    # uses the provider/search keys from .env):
    python scripts/smoke_research.py "What is citizen reporting in smart cities?"

    # Against a live server (e.g. `make local-dev` or `docker compose up`):
    python scripts/smoke_research.py --live --base-url http://localhost:8000 \\
        "What is citizen reporting in smart cities?"

    # Custom output directory and time budget:
    python scripts/smoke_research.py --outdir /tmp/out --timeout 900 "query"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 600  # seconds
DEFAULT_POLL_INTERVAL = 5  # seconds

TERMINAL_SUCCESS = {"complete", "completed"}
TERMINAL_FAILURE = {"failed", "error", "cancelled"}


class SmokeTestError(RuntimeError):
    """Raised when the smoke test cannot proceed or fails."""


# ---------------------------------------------------------------------------
# In-process app bootstrapping (TestClient + in-memory SQLite)
# ---------------------------------------------------------------------------


@contextmanager
def make_test_client():
    """Boot the real app in-process on a shared in-memory SQLite database.

    Mirrors ``tests/conftest.py`` + ``tests/test_main.py``: the engine is the
    app's own (StaticPool for ``:memory:``), so endpoints, the background
    worker, and the settings proxy all see the same database.
    """
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from app.database import Base, engine
    import app.models  # noqa: F401  (import registers all tables)

    Base.metadata.create_all(bind=engine)

    from app.main import app
    from fastapi.testclient import TestClient

    # Entering the context runs the lifespan (plugin registration + background
    # worker), which the research pipeline depends on.
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only, so the script runs without extra installs)
# ---------------------------------------------------------------------------


def _http_json(method: str, url: str, payload: dict | None) -> dict:
    import urllib.error
    import urllib.request

    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise SmokeTestError(f"HTTP {e.code} {method} {url}: {detail}") from e
    except urllib.error.URLError as e:
        raise SmokeTestError(
            f"Network error {method} {url}: {e}\n"
            f"Is the server running? Try `make local-dev` or `docker compose up -d`."
        ) from e


def _http_raw(url: str) -> bytes:
    import urllib.request

    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=60) as resp:
        return resp.read()


class Api:
    """Thin API client that works against TestClient or a live server."""

    def __init__(self, base_url: str | None = None, client=None):
        self.base_url = base_url.rstrip("/") if base_url else None
        self._client = client

    def _check_status(self, resp):
        if resp.status_code >= 400:
            raise SmokeTestError(
                f"HTTP {resp.status_code} {resp.request.method} "
                f"{resp.request.url}: {resp.text[:500]}"
            )
        return resp

    def get(self, path: str):
        if self._client is not None:
            return self._check_status(self._client.get(path)).json()
        return _http_json("GET", f"{self.base_url}{path}", None)

    def post(self, path: str, payload: dict):
        if self._client is not None:
            return self._check_status(self._client.post(path, json=payload)).json()
        return _http_json("POST", f"{self.base_url}{path}", payload)

    def get_raw(self, path: str) -> bytes:
        if self._client is not None:
            return self._check_status(self._client.get(path)).content
        return _http_raw(f"{self.base_url}{path}")


# ---------------------------------------------------------------------------
# Smoke test flow
# ---------------------------------------------------------------------------


def run_smoke(
    query: str,
    *,
    outdir: str,
    timeout: int,
    poll_interval: int,
    live: bool,
    base_url: str,
    verbose: bool,
) -> int:
    out_dir = Path(outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if live:
        api = Api(base_url=base_url)
        print(f"[smoke] live mode -> {base_url}")
        return _run_smoke(api, query, out_dir, timeout, poll_interval, verbose)

    with make_test_client() as client:
        api = Api(client=client)
        print("[smoke] in-process mode (in-memory SQLite, provider from .env)")
        return _run_smoke(api, query, out_dir, timeout, poll_interval, verbose)


def _run_smoke(api: Api, query: str, out_dir: Path, timeout: int,
               poll_interval: int, verbose: bool) -> int:
    # 1. Health check
    health = api.get("/")
    if health.get("status") != "ok":
        raise SmokeTestError(f"Unexpected health response: {health}")

    # 2. Create the research item
    created = api.post(
        "/research",
        {
            "query": query,
            "user_notes": "smoke test via scripts/smoke_research.py",
        },
    )
    research_id = created["id"]
    print(f"[smoke] created research id={research_id} status={created['status']}")

    # 3. Poll until a terminal status
    deadline = time.monotonic() + timeout
    status = created["status"]
    while status not in TERMINAL_SUCCESS | TERMINAL_FAILURE:
        if time.monotonic() > deadline:
            raise SmokeTestError(
                f"research {research_id} did not reach a terminal status within "
                f"{timeout}s (last status: {status})"
            )
        time.sleep(poll_interval)
        item = api.get(f"/research/{research_id}")
        status = item["status"]
        if verbose:
            print(
                f"[smoke] poll: status={status} "
                f"result_len={len(item.get('result') or '')}"
            )
    print(f"[smoke] terminal status: {status}")

    summary = {
        "research_id": research_id,
        "query": query,
        "status": status,
        "mode": "live" if api.base_url else "in-process",
    }

    if status not in TERMINAL_SUCCESS:
        summary["error"] = f"research finished with status '{status}'"
        _write_summary(out_dir, summary)
        print(json.dumps(summary, indent=2))
        return 1

    # 4. Verify and capture outputs
    item = api.get(f"/research/{research_id}")
    summary["result_length"] = len(item.get("result") or "")

    document = api.get(f"/research/{research_id}/document")
    doc_path = out_dir / f"research_{research_id}_document.json"
    doc_path.write_text(json.dumps(document, indent=2))
    summary["document_length"] = len(document.get("document") or "")
    summary["document_json"] = str(doc_path)

    markdown = api.get_raw(f"/research/{research_id}/export/markdown")
    md_path = out_dir / f"research_{research_id}.md"
    md_path.write_bytes(markdown)
    summary["markdown_export"] = str(md_path)

    sources = api.get(f"/research/{research_id}/sources")
    findings = api.get(f"/research/{research_id}/findings")
    summary["sources_count"] = len(sources) if isinstance(sources, list) else None
    summary["findings_count"] = len(findings) if isinstance(findings, list) else None

    if summary["sources_count"] in (None, 0):
        raise SmokeTestError(
            f"research {research_id} completed with no sources — check the "
            f"search provider keys in .env (TAVILY_API_KEY) and the server log"
        )

    _write_summary(out_dir, summary)
    print(json.dumps(summary, indent=2))
    print("[smoke] PASS")
    return 0


def _write_summary(out_dir: Path, summary: dict) -> None:
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Research question to run end-to-end")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Test against a running server instead of in-process",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Live server base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--outdir",
        default="smoke_artifacts",
        help="Directory for exported artifacts and summary.json",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Max seconds to wait for completion (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Seconds between status polls (default: {DEFAULT_POLL_INTERVAL})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print each poll")
    args = parser.parse_args(argv)

    try:
        return run_smoke(
            args.query,
            outdir=args.outdir,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
            live=args.live,
            base_url=args.base_url,
            verbose=args.verbose,
        )
    except SmokeTestError as e:
        print(f"[smoke] FAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — surface anything for agents
        print(f"[smoke] FAIL (unexpected): {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

