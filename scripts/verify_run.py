#!/usr/bin/env python3
"""Check a captured research run against the invariants the P0 fixes promise.

Usage:
    python scripts/verify_run.py smoke_artifacts/<run-dir>

Reads the artifact dump written by ``scripts/capture_fp2026.py`` and reports
pass/fail for:

1. **Citation numbering** — the report's reference list is a contiguous
   ``1..N`` with no gaps, and every marker used in the body resolves to
   exactly one source row whose ``citation_marker`` matches and whose URL is
   the one the reference entry names.
2. **Sub-query coverage** — every sub-query search reported at least one
   source (the relevance filter must not starve a question).
3. **Search-plugin health** — which source types actually contributed, so a
   silently dead plugin (arXiv) is visible.

Exits non-zero when any check fails.
"""

import json
import re
import sys
from pathlib import Path

REFERENCE_RE = re.compile(
    r"^\[(\d+)\]\s+(.*?)(?=\n\s*\n|\Z)", re.MULTILINE | re.DOTALL
)
URL_RE = re.compile(r"Retrieved from (\S+)")


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def reference_entries(document: str) -> dict[int, str]:
    if "## References" not in document:
        return {}
    block = document.split("## References", 1)[1]
    entries: dict[int, str] = {}
    for match in REFERENCE_RE.finditer(block):
        url = URL_RE.search(match.group(2))
        entries[int(match.group(1))] = url.group(1) if url else ""
    return entries


def check_citation_numbering(outdir: Path) -> tuple[bool, list[str]]:
    notes: list[str] = []
    document = load(outdir / "document.json", {}).get("document") or ""
    sources = load(outdir / "sources.json", [])
    if not document:
        return False, ["document.json has no document"]

    body, _, references = document.partition("## References")
    body_markers = sorted({int(m) for m in re.findall(r"\[(\d+)\]", body)})
    entries = reference_entries(document)

    ok = True
    if sorted(entries) != list(range(1, len(entries) + 1)):
        ok = False
        notes.append(f"reference list is not contiguous 1..N: {sorted(entries)}")
    if body_markers and body_markers[-1] > len(entries):
        ok = False
        notes.append(
            f"body cites [{body_markers[-1]}] but only {len(entries)} "
            "references exist"
        )

    by_marker = {
        s["citation_marker"]: s
        for s in sources
        if s.get("citation_marker") is not None
    }
    unresolved = [m for m in entries if m not in by_marker]
    if unresolved:
        ok = False
        notes.append(f"markers with no source row: {unresolved}")

    mismatched = [
        m for m in entries
        if m in by_marker and entries[m] and entries[m] != by_marker[m]["url"]
    ]
    if mismatched:
        ok = False
        notes.append(f"markers pointing at the wrong URL: {mismatched}")

    orphan_rows = sorted(set(by_marker) - set(entries))
    if orphan_rows:
        notes.append(
            f"note: source rows with a marker the report never uses: "
            f"{orphan_rows}"
        )

    notes.append(
        f"{len(entries)} references, {len(by_marker)} marked source rows, "
        f"{len(sources)} sources total"
    )
    return ok, notes


def check_subquery_coverage(outdir: Path) -> tuple[bool, list[str]]:
    steps = load(outdir / "steps.json", {}).get("steps", [])
    searches = [
        s for s in steps
        if s.get("step_type") == "searching"
        and (s.get("metadata") or {}).get("sub_query")
    ]
    if not searches:
        return True, ["no per-sub-query search steps found"]

    empty = [
        (s["metadata"]["sub_query"][:60])
        for s in searches
        if s["metadata"].get("citations_found", 0) == 0
    ]
    notes = [
        f"{len(searches) - len(empty)}/{len(searches)} sub-queries got sources"
    ]
    if empty:
        notes += [f"  no sources: {q}" for q in empty]
    return not empty, notes


def check_source_types(outdir: Path) -> list[str]:
    sources = load(outdir / "sources.json", [])
    counts: dict[str, int] = {}
    for source in sources:
        counts[source.get("source_type", "?")] = (
            counts.get(source.get("source_type", "?"), 0) + 1
        )
    return [
        f"{kind}: {count}" for kind, count in sorted(counts.items())
    ] or ["no sources"]


def main() -> int:
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "smoke_artifacts/fp2026")
    if not outdir.is_dir():
        print(f"not a directory: {outdir}")
        return 2

    failures = 0
    for title, (ok, notes) in [
        ("citation numbering", check_citation_numbering(outdir)),
        ("sub-query coverage", check_subquery_coverage(outdir)),
    ]:
        print(f"[{'PASS' if ok else 'FAIL'}] {title}")
        for note in notes:
            print(f"        {note}")
        failures += 0 if ok else 1

    print("[info] contributing source types")
    for line in check_source_types(outdir):
        print(f"        {line}")

    print()
    print("ALL CHECKS PASSED" if not failures else f"{failures} CHECK(S) FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
