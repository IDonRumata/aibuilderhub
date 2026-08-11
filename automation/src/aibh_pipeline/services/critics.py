"""Four independent reviewers, each a separate LLM call returning strict JSON.

Every critic sees the same draft but a different brief, and none of them sees
the others' verdicts. A single REJECT that survives the revision loop stops
the post from being published at all.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from ..clients.anthropic_client import AnthropicClient
from ..clients.http import url_is_alive
from ..logging_setup import get_logger
from ..models import CritiqueIssue, CritiqueReport, DraftPost, ScoredTopic, Verdict
from ..settings import Settings

log = get_logger(__name__)

TITLE_MAX = 60
# Google truncates a description around 160 characters. A tight 20
# character window made this the most-failed rule in live runs for no
# SEO benefit, so the band is wider and the ceiling is what matters.
DESCRIPTION_MIN = 120
DESCRIPTION_MAX = 165

MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
INTERNAL_LINK_RE = re.compile(r"\[[^\]]*\]\((/blog/[a-z0-9-]+)\)")

CRITIQUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "REVISE", "REJECT"]},
        "notes": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "requirement": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["minor", "major", "blocking"],
                    },
                },
                "required": ["quote", "requirement", "severity"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "notes", "issues"],
    "additionalProperties": False,
}

VERDICT_RULES = """\
Return one of three verdicts:
- PASS: the post is publishable as it stands for your area. You do not have to
  think it is perfect. If the only things left are improvements you would make
  given more time, that is a PASS.
- REVISE: something is actually wrong and can be fixed. List each problem as an
  issue with the exact quote and a concrete requirement.
- REJECT: the post cannot be salvaged for your area - for example the central
  factual claim is unsupported, or the piece has nothing to say. Use this
  sparingly. It stops publication entirely.

Set severity honestly, because it decides what happens:
- blocking: the post must not be published while this is true. Invented facts,
  a claim no source supports, a dead or wrong link, a broken rule you were
  given as mandatory.
- major: a real weakness worth fixing, but the post is still honest and useful
  with it present.
- minor: polish. Wording, rhythm, a better example.

Do not inflate severity to force a rewrite. A post carrying only minor issues
after the final round is published, and blocking issues stop it entirely, so
mislabelling either way does real damage.

Every issue must name the specific text and a specific fix. "Improve the flow"
is not an issue. "Cut the second paragraph of the pricing section, it repeats
the TL;DR" is.
"""

FACT_CHECKER = f"""\
You are the fact-checker. You will be given a draft post and the complete list
of sources it was written from. Those sources are the only permitted evidence.

Flag, as an issue:
- Any number, price, model name, capability, date, or company statement that
  does not appear in the sources.
- Any invented benchmark, adoption statistic, or appeal to "studies" or
  "experts" with no cited source.
- Anything a company claimed about its own product that the post states as
  established fact rather than as a claim.
- Any factual assertion that overstates what the source supports.

Unverifiable material must be cut or softened to an explicitly labelled
opinion. Do not flag the author's own judgements and predictions - those are
allowed as long as they are clearly opinion.

REJECT if the central claim the whole post rests on is not supported by any
source.

{VERDICT_RULES}
"""

AI_PATTERN_CRITIC = f"""\
You are the style reviewer looking for machine-writing tells.

Flag, as an issue:
- Any banned word, phrase, or construction from the style rules you were given.
- Em dashes, en dashes, curly quotes, emoji.
- Uniform rhythm: paragraphs that are all roughly the same length, sentences
  that are all roughly the same length, no short blunt sentences anywhere.
- Every paragraph opening the same way, or the same three-item comma list
  pattern repeating.
- Bulleted lists where prose would read better.
- Formal register: missing contractions, "one might consider", "it is
  important to".
- Headings in Title Case Every Word, or an Introduction or Conclusion heading.
- Language that ties the post to a moment in time: today, this week, recently,
  just announced, a month and year.

Also check the required qualities are present: contractions, concrete numbers
instead of "many" or "several", at least one first-person or subjective
judgement, and varied paragraph shape.

{VERDICT_RULES}
"""

EDITOR_CRITIC = f"""\
You are the editor. Your question is simple: what does this mean for a solo
builder, and what should they do about it?

Flag, as an issue:
- Any passage that restates the announcement without saying what it changes
  for the reader.
- Padding: sentences that add words and no information.
- Missing "so what": if the post never says whether to switch tools, adopt,
  wait, or ignore, that is an issue.
- Vague advice that would fit any tool or any news item.
- A missing downside. Every post must name at least one limitation, risk, or
  reason for scepticism.
- Praise with no reason attached.

REJECT if the post is a rewrite of a press release with no independent point
of view, or if it has no discernible takeaway for the audience.

{VERDICT_RULES}
"""

SEO_CRITIC = f"""\
You are the SEO and integrity reviewer. You check mechanics, not prose.

Requirements, all mandatory:
- title is at most {TITLE_MAX} characters and is not clickbait.
- description is between {DESCRIPTION_MIN} and {DESCRIPTION_MAX} characters.
- slug is lowercase kebab-case, contains no year and no date, and is 3 to 7
  words long.
- tags: 3 to 5 tags, all lowercase, first tag is "news".
- The body contains one or two external links, and they point at the supplied
  source URLs. You will be given the result of a liveness check on each link;
  treat any link reported as dead as a blocking issue.
- The body contains one or two internal links of the form /blog/<slug>, and
  every one of them is in the catalogue of existing posts you were given. A
  link to a slug that is not in the catalogue is a blocking issue.
- Nothing anywhere in the body refers to when the news happened.

{VERDICT_RULES}
"""


def mechanical_issues(
    draft: DraftPost,
    *,
    known_slugs: set[str],
    dead_links: list[str],
    allowed_urls: set[str],
) -> list[CritiqueIssue]:
    """Deterministic checks. The model is not asked to count characters."""
    issues: list[CritiqueIssue] = []

    if len(draft.title) > TITLE_MAX:
        issues.append(
            CritiqueIssue(
                quote=draft.title,
                requirement=(
                    f"Title is {len(draft.title)} characters. "
                    f"Cut it to {TITLE_MAX} or fewer."
                ),
                severity="blocking",
            )
        )
    length = len(draft.description)
    if not DESCRIPTION_MIN <= length <= DESCRIPTION_MAX:
        issues.append(
            CritiqueIssue(
                quote=draft.description,
                requirement=(
                    f"Description is {length} characters. Rewrite it to between "
                    f"{DESCRIPTION_MIN} and {DESCRIPTION_MAX}."
                ),
                severity="blocking",
            )
        )
    if re.search(r"(?:19|20)\d{2}", draft.slug):
        issues.append(
            CritiqueIssue(
                quote=draft.slug,
                requirement="Remove the year from the slug.",
                severity="blocking",
            )
        )
    words = draft.slug.split("-")
    if not 3 <= len(words) <= 7:
        issues.append(
            CritiqueIssue(
                quote=draft.slug,
                requirement=f"Slug has {len(words)} words. Use between 3 and 7.",
                severity="major",
            )
        )
    if not draft.tags or draft.tags[0] != "news":
        issues.append(
            CritiqueIssue(
                quote=", ".join(draft.tags),
                requirement='The first tag must be "news".',
                severity="blocking",
            )
        )
    if not 3 <= len(draft.tags) <= 5:
        issues.append(
            CritiqueIssue(
                quote=", ".join(draft.tags),
                requirement=f"There are {len(draft.tags)} tags. Use between 3 and 5.",
                severity="major",
            )
        )

    external = MD_LINK_RE.findall(draft.body)
    if not 1 <= len(external) <= 3:
        issues.append(
            CritiqueIssue(
                quote=", ".join(external) or "(none)",
                requirement="Include one or two links to the primary sources in the body.",
                severity="blocking",
            )
        )
    for url in external:
        if url.rstrip("/") not in {u.rstrip("/") for u in allowed_urls}:
            issues.append(
                CritiqueIssue(
                    quote=url,
                    requirement=(
                        "This URL was not among the supplied sources. "
                        "Use only the source URLs."
                    ),
                    severity="blocking",
                )
            )
    for url in dead_links:
        issues.append(
            CritiqueIssue(
                quote=url,
                requirement="This link does not resolve. Replace it with a working source URL.",
                severity="blocking",
            )
        )

    internal = INTERNAL_LINK_RE.findall(draft.body)
    if not 1 <= len(internal) <= 3:
        issues.append(
            CritiqueIssue(
                quote=", ".join(internal) or "(none)",
                requirement="Include one or two internal links to existing posts.",
                severity="major",
            )
        )
    for path in internal:
        slug = path.removeprefix("/blog/")
        if slug not in known_slugs:
            issues.append(
                CritiqueIssue(
                    quote=path,
                    requirement=(
                        "No such post exists. "
                        "Link only to slugs from the supplied catalogue."
                    ),
                    severity="blocking",
                )
            )

    word_count = draft.word_count
    if word_count < 450:
        issues.append(
            CritiqueIssue(
                quote=f"{word_count} words",
                requirement=(
                    "The post is too short. Expand it to at least 500 words, "
                    "but only with material the sources actually support."
                ),
                severity="major",
            )
        )
    return issues


async def check_links(urls: list[str], settings: Settings) -> list[str]:
    """Return the subset of ``urls`` that does not resolve."""
    if not urls:
        return []
    from ..clients.http import http_client

    async with http_client(settings) as client:
        results = await asyncio.gather(
            *(url_is_alive(client, url) for url in urls), return_exceptions=True
        )
    dead = [
        url
        for url, alive in zip(urls, results, strict=True)
        if isinstance(alive, BaseException) or not alive
    ]
    if dead:
        log.warning("dead_links", urls=dead)
    return dead


def _post_payload(draft: DraftPost) -> str:
    return (
        f"title: {draft.title}\n"
        f"description: {draft.description}\n"
        f"slug: {draft.slug}\n"
        f"tags: {', '.join(draft.tags)}\n\n"
        f"body:\n{draft.body}"
    )


async def _run_critic(
    name: str,
    system_specific: str,
    user: str,
    *,
    client: AnthropicClient,
    settings: Settings,
    voice: str,
) -> CritiqueReport:
    payload = await client.complete_json(
        system_shared=voice,
        system_specific=system_specific,
        user=user,
        max_tokens=settings.max_tokens_critic,
        label=f"critic-{name}",
        json_schema=CRITIQUE_SCHEMA,
        effort="medium",
    )
    report = CritiqueReport(
        critic=name,
        verdict=Verdict(payload["verdict"]),
        issues=[CritiqueIssue(**issue) for issue in payload.get("issues", [])],
        notes=payload.get("notes", ""),
    )
    log.info(
        "critic_verdict",
        critic=name,
        verdict=report.verdict.value,
        issues=len(report.issues),
    )
    return report


async def review(
    draft: DraftPost,
    topic: ScoredTopic,
    *,
    client: AnthropicClient,
    settings: Settings,
    voice: str,
    style_rules: str,
    internal_links: str,
    known_slugs: set[str],
) -> list[CritiqueReport]:
    """Run all four critics. Sequential, so the call budget stays predictable."""
    post = _post_payload(draft)
    sources = "\n".join(
        f"- {item.source} | {item.title} | {item.canonical_url}\n  {item.summary[:600]}"
        for item in topic.items[:4]
    )

    external_urls = MD_LINK_RE.findall(draft.body)
    dead = await check_links(external_urls, settings)
    mechanical = mechanical_issues(
        draft,
        known_slugs=known_slugs,
        dead_links=dead,
        allowed_urls=set(topic.source_urls),
    )

    briefs: list[tuple[str, str, str]] = [
        ("fact-checker", FACT_CHECKER, f"Sources:\n{sources}\n\n---\n\nPost:\n{post}"),
        (
            "ai-pattern",
            AI_PATTERN_CRITIC,
            f"Style rules:\n{style_rules}\n\n---\n\nPost:\n{post}",
        ),
        ("editor", EDITOR_CRITIC, f"Post:\n{post}"),
        (
            "seo-integrity",
            SEO_CRITIC,
            f"Existing posts catalogue:\n{internal_links}\n\n"
            f"Permitted source URLs:\n" + "\n".join(topic.source_urls) + "\n\n"
            f"Link liveness check: {'all links resolve' if not dead else f'DEAD: {dead}'}\n\n"
            f"---\n\nPost:\n{post}",
        ),
    ]

    reports: list[CritiqueReport] = []
    for name, system_specific, user in briefs:
        reports.append(
            await _run_critic(
                name,
                system_specific,
                user,
                client=client,
                settings=settings,
                voice=voice,
            )
        )

    # Deterministic findings are attached to the SEO reviewer so the writer
    # sees them in the same revision pass.
    if mechanical:
        seo = next(r for r in reports if r.critic == "seo-integrity")
        seo.issues.extend(mechanical)
        if seo.verdict is Verdict.PASS:
            seo.verdict = Verdict.REVISE
        log.info("mechanical_issues", count=len(mechanical))

    return reports


def verdict_of(reports: list[CritiqueReport]) -> Verdict:
    if any(r.verdict is Verdict.REJECT for r in reports):
        return Verdict.REJECT
    if any(r.verdict is Verdict.REVISE for r in reports):
        return Verdict.REVISE
    return Verdict.PASS
