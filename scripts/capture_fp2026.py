#!/usr/bin/env python3
"""Capture a full artifact dump for one live research item.

Usage: python scripts/capture_fp2026.py <research_id> <outdir>
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
TERMINAL = {"complete", "completed", "failed", "error", "cancelled"}


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            body = r.read()
            try:
                return r.status, json.loads(body)
            except Exception:
                return r.status, body.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"


def main():
    rid = int(sys.argv[1])
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    log = (outdir / "timeline.log").open("w")

    t0 = time.time()
    last = None
    while True:
        code, item = get(f"/research/{rid}")
        status = item.get("status") if isinstance(item, dict) else f"HTTP {code}"
        elapsed = time.time() - t0
        _, steps = get(f"/research/{rid}/steps")
        if isinstance(steps, dict):
            steps = steps.get("steps", [])
        nsteps = len(steps) if isinstance(steps, list) else -1
        _, plan = get(f"/research/{rid}/plan")
        progress = plan.get("progress") if isinstance(plan, dict) else None
        if isinstance(progress, dict):
            done = sum(1 for v in progress.values()
                       if str((v or {}).get("status")) in {"complete", "completed"})
            progress = f"{done}/{len(progress)}"
        line = f"{elapsed:7.1f}s status={status} steps={nsteps} subq_done={progress}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
        if isinstance(item, dict) and status in TERMINAL:
            break
        if elapsed > 1800:
            print("TIMEOUT", flush=True)
            break
        last = line
        time.sleep(5)

    log.close()

    # Full dump of every read endpoint.
    endpoints = {
        "item": f"/research/{rid}",
        "document": f"/research/{rid}/document",
        "sources": f"/research/{rid}/sources",
        "findings": f"/research/{rid}/findings",
        "notes": f"/research/{rid}/notes",
        "plan": f"/research/{rid}/plan",
        "knowledge_base": f"/research/{rid}/knowledge-base",
        "entities": f"/research/{rid}/entities",
        "state": f"/research/{rid}/state",
        "steps": f"/research/{rid}/steps",
    }
    index = {}
    for name, path in endpoints.items():
        code, payload = get(path)
        target = outdir / f"{name}.json"
        target.write_text(
            payload if isinstance(payload, str) else json.dumps(payload, indent=2, default=str)
        )
        size = target.stat().st_size
        n = len(payload) if isinstance(payload, list) else (
            len(payload.get("result") or "") if isinstance(payload, dict) and name == "item" else "")
        index[name] = {"http": code, "file": target.name, "bytes": size, "n": n}
        print(f"  {name:15s} HTTP {code} {size:>8} bytes", flush=True)

    for name, path in {
        "export_markdown": f"/research/{rid}/export/markdown",
        "export_html": f"/research/{rid}/export/html",
        "export_sources_bibtex": f"/research/{rid}/export/sources/bibtex",
        "export_findings_csv": f"/research/{rid}/export/findings/csv",
        "export_data": f"/research/{rid}/export/data",
    }.items():
        code, payload = get(path)
        ext = {"export_markdown": "md", "export_html": "html",
               "export_sources_bibtex": "bib", "export_findings_csv": "csv",
               "export_data": "json"}[name]
        target = outdir / f"{name}.{ext}"
        target.write_text(payload if isinstance(payload, str) else json.dumps(payload, indent=2, default=str))
        index[name] = {"http": code, "file": target.name, "bytes": target.stat().st_size}
        print(f"  {name:15s} HTTP {code} {target.stat().st_size:>8} bytes", flush=True)

    (outdir / "index.json").write_text(json.dumps(index, indent=2))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
