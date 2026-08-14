"""Layer A Unicode hygiene: scrub invisible codepoints before publication.

Model output and quoted upstream text both carry characters that nothing in
the pipeline can see - zero-width spaces, non-breaking spaces, bidi controls,
exotic space homoglyphs. They survive every critic because they render as
nothing, then break site search, git diffs and reader copy-paste once
published. RSS and Reddit summaries are the usual source; the writer just
carries them through into the body.

The scrub is delegated to the vendored `remove-ai-marks` skill rather than
reimplemented here, so this step and the CI guard in
`scripts/check-content-hygiene.py` share a single definition of "clean".

Failure policy: this never raises. A missing or broken cleaner degrades to
passing the text through untouched and logging a warning, because losing a
day's post to a hygiene tool is worse than publishing a stray zero-width
space - and CI fails on main straight after, so it stays visible.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..logging_setup import get_logger
from ..settings import Settings

log = get_logger(__name__)

# Relative to the repository root; the skill is vendored under version control.
SCRIPT_RELPATH = Path(".claude") / "skills" / "remove-ai-marks" / "scripts" / "clean_text.py"

TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class ScrubResult:
    """What the cleaner did to one document."""

    text: str
    removed_count: int = 0
    replaced_count: int = 0
    removed: dict[str, int] = field(default_factory=dict)
    replaced: dict[str, int] = field(default_factory=dict)
    # False when the cleaner could not run at all, so callers can tell
    # "nothing to clean" apart from "did not check".
    ran: bool = True

    @property
    def touched(self) -> bool:
        return bool(self.removed_count or self.replaced_count)

    def summary(self) -> str:
        if not self.ran:
            return "not checked"
        if not self.touched:
            return "clean"
        parts = sorted(self.removed) + sorted(self.replaced)
        return f"removed {self.removed_count}, replaced {self.replaced_count} ({', '.join(parts)})"


def script_path(settings: Settings) -> Path:
    return settings.repo_root / SCRIPT_RELPATH


def scrub(text: str, settings: Settings) -> ScrubResult:
    """Strip invisible Unicode from `text` via the remove-ai-marks cleaner.

    Text goes in on stdin and comes back on stdout; `--stats` puts a JSON
    report on stderr. Bytes rather than text mode throughout, so no newline
    translation can touch a document that is about to be written with an
    explicit LF ending.
    """
    script = script_path(settings)
    if not script.is_file():
        log.warning("unicode_scrub_unavailable", script=str(script))
        return ScrubResult(text=text, ran=False)

    try:
        # S603: argv is fixed - this interpreter plus a version-controlled
        # script path. No shell, and the document travels on stdin, never argv.
        proc = subprocess.run(  # noqa: S603
            [sys.executable, str(script), "-", "--stats"],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("unicode_scrub_failed", error=str(exc))
        return ScrubResult(text=text, ran=False)

    if proc.returncode != 0:
        log.warning(
            "unicode_scrub_failed",
            returncode=proc.returncode,
            stderr=proc.stderr.decode("utf-8", "replace")[:500],
        )
        return ScrubResult(text=text, ran=False)

    cleaned = proc.stdout.decode("utf-8")
    # Writing to stdout appends a trailing newline when the text lacks one.
    # Harmless for a post, which always ends in one, but scrub() promises to
    # touch nothing except invisible codepoints, so undo it.
    if cleaned.endswith("\n") and not text.endswith("\n"):
        cleaned = cleaned[:-1]

    try:
        stats = json.loads(proc.stderr.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        # The text is still trustworthy - only the report is unreadable.
        log.warning("unicode_scrub_stats_unreadable")
        return ScrubResult(text=cleaned)

    result = ScrubResult(
        text=cleaned,
        removed_count=int(stats.get("removed_count", 0)),
        replaced_count=int(stats.get("replaced_count", 0)),
        removed=dict(stats.get("removed", {})),
        replaced=dict(stats.get("replaced", {})),
    )
    if result.touched:
        log.info(
            "unicode_scrubbed",
            removed=result.removed_count,
            replaced=result.replaced_count,
            codepoints=sorted({**result.removed, **result.replaced}),
        )
    return result
