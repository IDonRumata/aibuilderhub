#!/usr/bin/env python3
"""Fail the build when published content carries invisible Unicode.

The pipeline already scrubs every post on its way to disk
(`automation/src/aibh_pipeline/services/hygiene.py`). This is the backstop for
everything that path does not cover: hand-edited posts, a post written before
the scrub existed, and any run where the cleaner was unavailable and degraded
to passing the text through.

Only Layer A findings gate the build - invisible and format Unicode, bidi
controls, exotic space homoglyphs. The skill also reports keyword hits in
frontmatter, which on a site whose subject *is* AI fires on ordinary titles
like "The Best UI Generator"; those are printed as notes and never fail.

Usage:
    python3 scripts/check-content-hygiene.py [PATH ...]

PATH may be a directory (audited recursively) or a single file, so the content
pipeline can gate just the post it produced. Defaults to src/content.

Exit codes: 0 clean, 1 invisible Unicode found, 2 the audit could not run.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPO_ROOT / ".claude" / "skills" / "remove-ai-marks" / "scripts"
AUDIT = SKILL_SCRIPTS / "audit_dir.py"
INSPECT = SKILL_SCRIPTS / "inspect_text.py"

DEFAULT_TARGETS = (Path("src") / "content",)
TIMEOUT_SECONDS = 120.0


def audit(target: Path) -> dict:
    """Run the skill's directory audit and return its report.

    audit_dir.py exits 1 to mean "found something actionable" and 2 for a
    usage error, so a report is available for both 0 and 1 - and "actionable"
    there includes the metadata keyword hits this check deliberately ignores.
    Only 2 and above is a real failure to run.
    """
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(AUDIT), str(target), "--json"],
        capture_output=True,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    if proc.returncode > 1:
        raise RuntimeError(
            f"audit_dir.py exited {proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace')[:500]}"
        )
    return json.loads(proc.stdout.decode("utf-8"))


def inspect_one(path: Path) -> dict:
    """Layer A report for a single file, shaped like an audit_dir entry.

    inspect_text.py exits 1 when it finds something, so only 2 and above is a
    real failure to run.
    """
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(INSPECT), "--json", str(path)],
        capture_output=True,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    if proc.returncode > 1:
        raise RuntimeError(
            f"inspect_text.py exited {proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace')[:500]}"
        )
    report = json.loads(proc.stdout.decode("utf-8"))
    return {
        "path": str(path),
        "suspicious_total": report["suspicious_total"],
        "has_ai_metadata": False,
        "findings": [],
    }


def hits(path: Path) -> str:
    """Per-codepoint detail for a file the audit flagged."""
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(INSPECT), str(path)],
        capture_output=True,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    lines = proc.stdout.decode("utf-8", "replace").splitlines()
    return "\n".join(f"    {line}" for line in lines if line.startswith("  ")) or "    (no detail)"


def main(argv: list[str]) -> int:
    if not AUDIT.is_file():
        print(f"error: the remove-ai-marks skill is missing at {SKILL_SCRIPTS}", file=sys.stderr)
        return 2

    targets = [Path(a) for a in argv[1:]] or list(DEFAULT_TARGETS)
    dirty: list[tuple[str, int]] = []
    notes: list[str] = []
    scanned = 0

    for target in targets:
        full = target if target.is_absolute() else REPO_ROOT / target
        if not full.exists():
            print(f"error: no such path: {target}", file=sys.stderr)
            return 2
        try:
            entries = [inspect_one(full)] if full.is_file() else audit(full)["files"]
        except (OSError, subprocess.SubprocessError, RuntimeError, json.JSONDecodeError) as exc:
            print(f"error: audit failed for {target}: {exc}", file=sys.stderr)
            return 2

        scanned += len(entries)
        for entry in entries:
            rel = Path(entry["path"]).resolve()
            shown = rel.relative_to(REPO_ROOT) if rel.is_relative_to(REPO_ROOT) else rel
            if entry["suspicious_total"]:
                dirty.append((str(shown), entry["suspicious_total"]))
            elif entry["has_ai_metadata"]:
                notes.append(f"{shown}: {', '.join(entry['findings']) or 'metadata keyword hit'}")

    if notes:
        print(f"Notes ({len(notes)} keyword hit(s) in metadata, not failing the build):")
        for note in notes:
            print(f"  {note}")
        print()

    if not dirty:
        print(f"Content hygiene: {scanned} file(s) scanned, no invisible Unicode.")
        return 0

    print(f"Content hygiene: invisible Unicode in {len(dirty)} of {scanned} file(s).\n")
    for path, count in dirty:
        print(f"  {path} - {count} suspicious codepoint(s)")
        print(hits(REPO_ROOT / path))
    print(
        "\nFix with:\n"
        "  python3 .claude/skills/remove-ai-marks/scripts/clean_text.py PATH --in-place --stats"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
