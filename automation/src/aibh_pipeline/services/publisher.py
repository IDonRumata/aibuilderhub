"""Write the finished post into the Astro content collection.

Publication is the last thing that happens and it is atomic: the markdown file
and the updated state files are written together, only after every critic has
passed. Committing and pushing is the workflow's job, not this module's - if
the Astro build rejects the new post, nothing has been committed yet.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ..logging_setup import get_logger
from ..models import DraftPost, PublishResult, ScoredTopic
from ..settings import Settings
from . import hygiene

log = get_logger(__name__)

REQUIRED_FRONTMATTER = ("title", "description", "pubDate", "tags", "author", "draft")


def build_frontmatter(draft: DraftPost, *, publish_date: datetime, is_draft: bool) -> str:
    """Frontmatter that satisfies src/content.config.ts.

    pubDate is written because the collection schema requires it for sorting,
    the sitemap and the RSS feed. It is not rendered anywhere in the UI.
    """
    data = {
        "title": draft.title,
        "description": draft.description,
        "pubDate": publish_date.date().isoformat(),
        "tags": list(draft.tags),
        "author": "AIBuilderHub",
        "draft": is_draft,
    }
    rendered = yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False, width=10_000
    )
    return f"---\n{rendered}---\n"


def validate_frontmatter(text: str) -> None:
    """Fail loudly rather than committing a post Astro will reject."""
    if not text.startswith("---\n"):
        raise ValueError("frontmatter block is missing")
    _, block, _ = text.split("---\n", 2)
    data = yaml.safe_load(block)
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    missing = [key for key in REQUIRED_FRONTMATTER if key not in data]
    if missing:
        raise ValueError(f"frontmatter is missing: {', '.join(missing)}")
    if not isinstance(data["tags"], list) or not data["tags"]:
        raise ValueError("tags must be a non-empty list")
    if data["tags"][0] != "news":
        raise ValueError('the first tag must be "news"')
    if not isinstance(data["draft"], bool):
        raise ValueError("draft must be a boolean")
    datetime.fromisoformat(str(data["pubDate"]))


def publish(
    draft: DraftPost,
    topic: ScoredTopic,
    settings: Settings,
    *,
    as_draft: bool = False,
    critic_rounds: int = 0,
    llm_calls: int = 0,
) -> PublishResult:
    settings.content_dir.mkdir(parents=True, exist_ok=True)
    path = settings.content_dir / f"{draft.slug}.md"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")

    frontmatter = build_frontmatter(
        draft, publish_date=datetime.now(UTC), is_draft=as_draft
    )
    document = f"{frontmatter}\n{draft.body.strip()}\n"
    # Scrub before validating, so the frontmatter that gets checked is byte for
    # byte the one that lands on disk. Covers the body and the metadata alike:
    # a non-breaking space inside a title reaches Astro otherwise.
    scrubbed = hygiene.scrub(document, settings)
    document = scrubbed.text
    validate_frontmatter(document)
    path.write_text(document, encoding="utf-8", newline="\n")

    result = PublishResult(
        path=str(path.relative_to(settings.repo_root)).replace("\\", "/"),
        slug=draft.slug,
        title=draft.title,
        word_count=draft.word_count,
        source_urls=draft.source_urls,
        critic_rounds=critic_rounds,
        llm_calls=llm_calls,
        unicode_removed=scrubbed.removed_count,
        unicode_replaced=scrubbed.replaced_count,
        unicode_checked=scrubbed.ran,
    )
    log.info("post_published", **json.loads(result.model_dump_json()), draft=as_draft)
    return result


def write_run_summary(settings: Settings, payload: dict[str, object]) -> Path:
    """Persist a machine-readable record of the run for the workflow to read."""
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    path = settings.state_dir / "last_run.json"
    payload = {"finished_at": datetime.now(UTC).isoformat(), **payload}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def append_step_summary(lines: list[str]) -> None:
    """Append to the GitHub Actions job summary when running in CI."""
    target = os.getenv("GITHUB_STEP_SUMMARY")
    if not target:
        return
    try:
        with Path(target).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError as exc:
        log.warning("step_summary_failed", error=str(exc))


def set_output(name: str, value: str) -> None:
    """Expose a value to later workflow steps via GITHUB_OUTPUT."""
    target = os.getenv("GITHUB_OUTPUT")
    if not target:
        return
    try:
        with Path(target).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    except OSError as exc:
        log.warning("set_output_failed", name=name, error=str(exc))
