"""Read the Astro content collection: what is already published on the site."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ..logging_setup import get_logger

log = get_logger(__name__)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


@dataclass(frozen=True, slots=True)
class ExistingPost:
    slug: str
    title: str
    description: str
    tags: tuple[str, ...]
    pub_date: datetime
    draft: bool
    body: str


def _parse(path: Path) -> ExistingPost | None:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        log.warning("post_without_frontmatter", path=str(path))
        return None

    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        log.warning("post_frontmatter_invalid", path=str(path), error=str(exc))
        return None

    pub = data.get("pubDate")
    if isinstance(pub, str):
        try:
            pub_date = datetime.fromisoformat(pub)
        except ValueError:
            pub_date = datetime.now(UTC)
    elif isinstance(pub, datetime):
        pub_date = pub
    elif hasattr(pub, "isoformat"):  # datetime.date
        pub_date = datetime.fromisoformat(pub.isoformat())
    else:
        pub_date = datetime.now(UTC)

    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=UTC)

    return ExistingPost(
        slug=path.stem,
        title=str(data.get("title", "")),
        description=str(data.get("description", "")),
        tags=tuple(data.get("tags") or ()),
        pub_date=pub_date,
        draft=bool(data.get("draft", False)),
        body=match.group(2),
    )


def existing_posts(content_dir: Path) -> list[ExistingPost]:
    """Every post currently in src/content/blog, drafts included."""
    if not content_dir.is_dir():
        log.warning("content_dir_missing", path=str(content_dir))
        return []
    posts = [p for path in sorted(content_dir.glob("*.md")) if (p := _parse(path))]
    log.info("existing_posts_loaded", count=len(posts))
    return posts


def link_menu(posts: list[ExistingPost], *, limit: int = 30) -> str:
    """A compact catalogue of internal link targets for the writer prompt."""
    live = [p for p in posts if not p.draft]
    live.sort(key=lambda p: p.pub_date, reverse=True)
    lines = [f"- /blog/{p.slug} - {p.title}" for p in live[:limit]]
    return "\n".join(lines)
