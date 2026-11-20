#!/usr/bin/env python3
"""artefact_check.py: does this repository's documentation match what its manifest claims?

Runs in CI on every pull request. Fails (exit 1) when:
  AC-01  manifest.yaml is missing or unreadable
  AC-02  a required core document for the project's grade has no entry
  AC-03  an entry says present/draft but the file is missing
  AC-04  a present document is a stub (fewer than MIN_WORDS words, or still has TODO/TBC template text)
  AC-05  any document contains an email address (contact is by form only)
  AC-06  any document uses the retired directorate name (write Government Data Directorate)
  AC-07  a shared entry does not name the estate document it relies on
  AC-08  a review date has passed

Each rule records the defect that caused it (see DEFECTS). Run with --self-test to prove every rule
still fails when its defect is put back (vaccination, VER-05).
Standard library only. The manifest uses a minimal YAML subset (key: value, two-space nesting).
"""
from __future__ import annotations
import datetime as dt
import pathlib
import re
import sys
import tempfile

CORE = ["toc", "ur", "prd", "ftir", "sad", "hld", "lld"]
MIN_WORDS = 150
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RETIRED = re.compile(r"\bO" + r"CDO\b|Office of the Chief " + r"Data Officer", re.I)  # split so this file passes its own check
STUB = re.compile(r"\b(TODO|TBC|lorem ipsum)\b|\{\{.*?\}\}", re.I)

DEFECTS = {
    "AC-03": "D-EST-01: a register listed documents that did not exist (file-name scan only)",
    "AC-04": "D-EST-02: placeholder documents would pass a presence-only check; "
             "D-EST-03: word count wrongly failed a data file (CSV now needs a header and one row); "
             "D-EST-04: a placeholder quoted as code (`{{REPO}}`) was wrongly read as unfilled template text",
    "AC-05 (source)": "D-EST-05: the self-test fixture held a literal email address, which other repositories' checks rightly flagged",
    "AC-05": "Owner rule 3 Nov 2026: never disclose an email address",
    "AC-06": "Owner rule 15 Nov 2026: the retired directorate name must never appear",
}


def required_for(grade: str) -> list[str]:
    """Which core documents a project must hold at its grade.

    Owner's call (20 Nov 2026 request): the core seven on every active project.
    G1 (sketch or custodial) gets a record card instead, so nothing here is required.
    Change this function if you want G2 to carry fewer documents.
    """
    g = grade.strip().upper()[:2]
    if g == "G1":
        return []
    return list(CORE)


def parse_manifest(text: str) -> dict:
    """Minimal YAML subset: top-level scalars, and one level of mapping under 'artefacts:'."""
    out: dict = {"artefacts": {}}
    current = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        key, _, val = raw.strip().partition(":")
        val = val.strip().strip('"').strip("'")
        if indent == 0:
            current = None
            if key == "artefacts":
                continue
            out[key] = val
        elif indent == 2:
            current = key
            out["artefacts"][key] = {}
        elif indent == 4 and current:
            out["artefacts"][current][key] = val
    return out


def check(root: pathlib.Path, today: dt.date | None = None) -> list[str]:
    today = today or dt.date.today()
    errs: list[str] = []
    mpath = root / "docs" / "artefacts" / "manifest.yaml"
    if not mpath.is_file():
        return [f"AC-01 missing {mpath.relative_to(root)}"]
    try:
        m = parse_manifest(mpath.read_text(encoding="utf-8"))
    except Exception as exc:  # fail closed
        return [f"AC-01 unreadable manifest: {exc}"]
    arts = m["artefacts"]
    for need in required_for(m.get("grade", "")):
        if need not in arts:
            errs.append(f"AC-02 {need}: required at grade {m.get('grade')} but not in manifest")
    for name, a in arts.items():
        status = a.get("status", "missing")
        if status == "shared" and not a.get("shared_ref"):
            errs.append(f"AC-07 {name}: shared but no shared_ref")
        if status in ("present", "draft"):
            p = root / a.get("path", "")
            if not a.get("path") or not p.is_file():
                errs.append(f"AC-03 {name}: status {status} but file missing ({a.get('path')})")
                continue
            body = p.read_text(encoding="utf-8")
            if status == "present":
                if p.suffix == ".csv":  # data file: needs a header and at least one data row (D-EST-03)
                    stub = len([l for l in body.splitlines() if l.strip()]) < 2 or bool(STUB.search(body))
                else:  # prose document; placeholders quoted as code are documentation, not stubs (D-EST-04)
                    prose = re.sub(r"```.*?```", " ", body, flags=re.S)
                    prose = re.sub(r"`[^`\n]*`", " ", prose)
                    stub = len(body.split()) < MIN_WORDS or bool(STUB.search(prose))
                if stub:
                    errs.append(f"AC-04 {name}: marked present but reads as a stub")
        rd = a.get("review_date")
        if rd:
            try:
                if dt.date.fromisoformat(rd) < today:
                    errs.append(f"AC-08 {name}: review date {rd} has passed")
            except ValueError:
                errs.append(f"AC-08 {name}: review date not ISO ({rd})")
    for doc in (root / "docs" / "artefacts").rglob("*"):
        if doc.is_file() and doc.suffix in (".md", ".yaml", ".csv", ".html", ".json"):
            t = doc.read_text(encoding="utf-8", errors="ignore")
            if EMAIL.search(t):
                errs.append(f"AC-05 {doc.relative_to(root)}: contains an email address")
            if RETIRED.search(t):
                errs.append(f"AC-06 {doc.relative_to(root)}: uses the retired directorate name")
    return errs


def _self_test() -> int:
    """Each rule must pass on a good fixture and fail when its defect is put back."""
    good_doc = "word " * 200
    manifest = "grade: G3\nartefacts:\n" + "".join(
        f"  {k}:\n    status: present\n    path: docs/artefacts/{k}.md\n    review_date: 2099-01-01\n" for k in CORE
    ) + "  trace:\n    status: present\n    path: docs/artefacts/trace.csv\n"
    breaks = {
        "AC-01": lambda r: (r / "docs/artefacts/manifest.yaml").unlink(),
        "AC-02": lambda r: (r / "docs/artefacts/manifest.yaml").write_text(manifest.replace("  lld:", "  zzz:")),
        "AC-03": lambda r: (r / "docs/artefacts/prd.md").unlink(),
        "AC-04": lambda r: (r / "docs/artefacts/sad.md").write_text("TODO"),
        "AC-04 (bare placeholder)": lambda r: (r / "docs/artefacts/sad.md").write_text(good_doc + " {{REPO}}"),
        "AC-04 (csv)": lambda r: (r / "docs/artefacts/trace.csv").write_text("a,b\n"),
        # D-EST-05: the fixture address is assembled at run time so this file holds no email address in source
        "AC-05": lambda r: (r / "docs/artefacts/hld.md").write_text(good_doc + " someone" + chr(64) + "example.org"),
        "AC-06": lambda r: (r / "docs/artefacts/lld.md").write_text(good_doc + " O" + "CDO"),
        "AC-07": lambda r: (r / "docs/artefacts/manifest.yaml").write_text(manifest.replace("status: present\n    path: docs/artefacts/ur.md", "status: shared\n    path: x")),
        "AC-08": lambda r: (r / "docs/artefacts/manifest.yaml").write_text(manifest.replace("2099-01-01", "2000-01-01", 1)),
    }
    failures = 0
    for rule, brk in [(None, None), *breaks.items()]:
        with tempfile.TemporaryDirectory() as d:
            r = pathlib.Path(d)
            (r / "docs/artefacts").mkdir(parents=True)
            (r / "docs/artefacts/manifest.yaml").write_text(manifest)
            for k in CORE:
                (r / f"docs/artefacts/{k}.md").write_text(good_doc)
            (r / "docs/artefacts/trace.csv").write_text("a,b\n1,2\n")
            (r / "docs/artefacts/hld.md").write_text(good_doc + " The build replaces `{{REPO}}` in pages.")
            if brk:
                brk(r)
            errs = check(r, dt.date(2026, 11, 20))
            ok = (not errs) if rule is None else any(e.startswith(rule.split()[0]) for e in errs)
            print(f"{'PASS' if ok else 'FAIL'} {'clean fixture' if rule is None else rule + ' catches its break'}")
            failures += not ok
    return failures


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(1 if _self_test() else 0)
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    problems = check(root)
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
