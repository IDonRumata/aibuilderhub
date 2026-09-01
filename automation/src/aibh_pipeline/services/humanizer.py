"""Anti-AI-tell scanning and the final rewrite pass.

The scanner is pure regex plus a few rhythm statistics, so it runs identically
in the pipeline and in CI. The rewrite pass hands the violations back to the
model and asks for surgical fixes rather than a rewrite of the whole post.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..clients.anthropic_client import AnthropicClient
from ..logging_setup import get_logger
from ..settings import Settings
from ..textutil import drop_orphan_code_fence, strip_markdown

log = get_logger(__name__)

CONTRACTION_RE = re.compile(
    r"\b(?:it's|don't|doesn't|didn't|won't|can't|isn't|aren't|wasn't|weren't|"
    r"you'll|you're|you've|i'm|i've|i'd|they're|there's|that's|here's|"
    r"we're|we've|let's|hasn't|haven't|wouldn't|shouldn't|couldn't)\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"(?<![\w/])(?:\$\d[\d,.]*|\d[\d,.]*\s*(?:%|x\b)|\d[\d,.]*)")
TRIPLET_RE = re.compile(r"\b[\w'-]+,\s+[\w'-]+,\s+(?:and\s+|or\s+)?[\w'-]+\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
CODE_FENCE_RE = re.compile(r"^```")


@dataclass(frozen=True, slots=True)
class Violation:
    rule: str
    message: str
    excerpt: str

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "message": self.message, "excerpt": self.excerpt}


@lru_cache(maxsize=4)
def load_rules(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _excerpt(text: str, start: int, end: int, *, width: int = 45) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    return " ".join(text[left:right].split())


def _prose_blocks(body: str) -> tuple[list[str], list[str]]:
    """Split a markdown body into (paragraphs, bullet lines), skipping code."""
    paragraphs: list[str] = []
    bullets: list[str] = []
    current: list[str] = []
    in_code = False

    for line in body.splitlines():
        if CODE_FENCE_RE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if stripped.startswith(("#", ">", "|", "---")):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if BULLET_RE.match(line):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            bullets.append(stripped)
            continue
        current.append(stripped)

    if current:
        paragraphs.append(" ".join(current))
    return paragraphs, bullets


def _coefficient_of_variation(values: list[int]) -> float:
    if len(values) < 3:
        return 1.0  # too few samples to judge; do not fail the post on this
    mean = statistics.fmean(values)
    if mean == 0:
        return 1.0
    return statistics.pstdev(values) / mean


def _title_case_violations(body: str, proper_nouns: set[str]) -> list[Violation]:
    """Flag headings written in Title Case Every Word."""
    out: list[Violation] = []
    for line in body.splitlines():
        if not line.startswith("#"):
            continue
        heading = line.lstrip("#").strip()
        words = [w for w in re.findall(r"[A-Za-z][\w'-]*", heading)]
        if len(words) < 4:
            continue
        # Skip the first word: every heading capitalises that one.
        candidates = [w for w in words[1:] if w.lower() not in {"a", "an", "the",
                                                               "of", "to", "in",
                                                               "on", "for", "and",
                                                               "or", "vs", "is",
                                                               "it", "at", "by"}]
        if not candidates:
            continue
        capitalised = [
            w for w in candidates if w[0].isupper() and w.rstrip("s") not in proper_nouns
            and w not in proper_nouns
        ]
        if len(capitalised) >= 3 and len(capitalised) >= len(candidates) - 1:
            out.append(
                Violation(
                    rule="title-case-heading",
                    message="Headings use sentence case, not Title Case Every Word.",
                    excerpt=heading,
                )
            )
    return out


def scan(body: str, rules: dict[str, Any]) -> list[Violation]:
    """Return every banned-pattern and rhythm violation found in ``body``."""
    violations: list[Violation] = []
    # Word, phrase and construction rules are about our own prose, so they run
    # against a copy with code spans and link targets blanked out.
    prose = mask_non_prose(body)

    for rule in rules.get("typography") or []:
        for match in re.finditer(rule["pattern"], body):
            violations.append(
                Violation(rule["id"], rule["message"], _excerpt(body, *match.span()))
            )

    for word in rules.get("words") or []:
        pattern = rf"\b{re.escape(word)}\b"
        for match in re.finditer(pattern, prose, re.IGNORECASE):
            violations.append(
                Violation(
                    f"word:{word}",
                    f"Banned word: {word}.",
                    _excerpt(body, *match.span()),
                )
            )

    for phrase in rules.get("phrases") or []:
        pattern = r"\s+".join(re.escape(part) for part in phrase.split())
        for match in re.finditer(pattern, prose, re.IGNORECASE):
            violations.append(
                Violation(
                    f"phrase:{phrase}",
                    f"Banned phrase: {phrase}.",
                    _excerpt(body, *match.span()),
                )
            )

    for rule in rules.get("constructions") or []:
        matches = list(re.finditer(rule["pattern"], prose, re.IGNORECASE))
        allowed = int(rule.get("max_occurrences", 0))
        for match in matches[allowed:]:
            violations.append(
                Violation(rule["id"], rule["message"], _excerpt(body, *match.span()))
            )

    for rule in rules.get("headings") or []:
        for match in re.finditer(rule["pattern"], body, re.IGNORECASE | re.MULTILINE):
            violations.append(
                Violation(rule["id"], rule["message"], _excerpt(body, *match.span()))
            )

    violations.extend(_title_case_violations(body, set(rules.get("proper_nouns") or [])))
    violations.extend(_structure_violations(body, rules.get("structure") or {}))
    return violations


def scan_metadata(title: str, description: str, rules: dict[str, Any]) -> list[Violation]:
    """Apply the hard style rules to the title and description.

    These never reach the humaniser, which only rewrites the body, so without
    this an em dash in the description ships straight to the site's search
    result and social card.
    """
    violations: list[Violation] = []
    for field, text in (("title", title), ("description", description)):
        for rule in rules.get("typography") or []:
            for match in re.finditer(rule["pattern"], text):
                excerpt = text[max(0, match.start() - 30) : match.end() + 30]
                violations.append(
                    Violation(f"{field}:{rule['id']}", rule["message"], excerpt)
                )
        for word in rules.get("words") or []:
            if re.search(rf"{re.escape(word)}", text, re.IGNORECASE):
                violations.append(
                    Violation(f"{field}:word:{word}", f"Banned word in the {field}: {word}.", text)
                )
        for phrase in rules.get("phrases") or []:
            pattern = r"\s+".join(re.escape(part) for part in phrase.split())
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(
                    Violation(
                        f"{field}:phrase:{phrase}",
                        f"Banned phrase in the {field}: {phrase}.",
                        text,
                    )
                )
    return violations


def _structure_violations(body: str, limits: dict[str, Any]) -> list[Violation]:
    out: list[Violation] = []
    paragraphs, bullets = _prose_blocks(body)
    if not paragraphs:
        return [Violation("no-prose", "The post has no prose paragraphs.", "")]

    para_lengths = [len(p.split()) for p in paragraphs]
    if _coefficient_of_variation(para_lengths) < float(limits.get("paragraph_length_cv_min", 0.35)):
        out.append(
            Violation(
                "uniform-paragraphs",
                "Paragraphs are all the same length. Vary them: some short, some long.",
                f"paragraph word counts: {para_lengths}",
            )
        )

    sentences = [s for s in SENTENCE_SPLIT_RE.split(" ".join(paragraphs)) if s.strip()]
    sent_lengths = [len(s.split()) for s in sentences]
    if _coefficient_of_variation(sent_lengths) < float(limits.get("sentence_length_cv_min", 0.30)):
        out.append(
            Violation(
                "uniform-sentences",
                "Sentence length barely varies. Add short, blunt sentences.",
                f"{len(sentences)} sentences, mean {statistics.fmean(sent_lengths):.0f} words",
            )
        )

    total_lines = len(paragraphs) + len(bullets)
    if total_lines and len(bullets) / total_lines > float(limits.get("max_bullet_fraction", 0.30)):
        out.append(
            Violation(
                "too-many-bullets",
                "Too much of the post is bulleted. Write it as prose.",
                f"{len(bullets)} bullets vs {len(paragraphs)} paragraphs",
            )
        )

    triplet_paras = sum(1 for p in paragraphs if TRIPLET_RE.search(p))
    if triplet_paras / len(paragraphs) > float(limits.get("max_triplet_paragraph_fraction", 0.25)):
        out.append(
            Violation(
                "triplet-habit",
                "Too many paragraphs use a three-item comma list. Break the pattern.",
                f"{triplet_paras} of {len(paragraphs)} paragraphs",
            )
        )

    plain = strip_markdown(body)
    contractions = len(CONTRACTION_RE.findall(plain))
    if contractions < int(limits.get("min_contractions", 4)):
        out.append(
            Violation(
                "too-formal",
                "Not enough contractions. Write it's, don't, you'll.",
                f"found {contractions}",
            )
        )

    numbers = len(NUMBER_RE.findall(plain))
    if numbers < int(limits.get("min_concrete_numbers", 3)):
        out.append(
            Violation(
                "too-vague",
                "Not enough concrete figures. Use real numbers from the sources.",
                f"found {numbers}",
            )
        )

    return out


# Rules that cannot be satisfied by editing alone, so they must not stop a
# publication.
#
# "too-vague" wants at least three concrete figures. The only way to add one
# is to take it from a source, and the humanizer is deliberately forbidden
# from introducing statistics: it runs AFTER the fact-checker, so anything it
# invented would reach the site unchecked. That prohibition is a safety
# property and stays. Meanwhile the fact-checker spends the review rounds
# stripping every number the sources do not support, which is how a draft
# arrives here below the threshold with no legal way back above it. Two runs
# died on exactly this - 12 August and 1 September - after passing every
# other check with zero blocking issues.
#
# It still gets scanned and logged, so a pattern of vague posts stays visible.
ADVISORY_RULES = frozenset({"too-vague"})


# Regions where a banned word is somebody else's name, not our prose: fenced
# blocks, inline code, the target half of a markdown link, and bare URLs.
_MASKABLE = re.compile(
    r"```.*?```"           # fenced code
    r"|`[^`]*`"            # inline code
    r"|\]\([^)]*\)"        # the (target) of [text](target)
    r"|https?://\S+",      # bare URL
    re.S,
)


def mask_non_prose(body: str) -> str:
    """Blank out code and link targets, keeping every character position.

    A style rule about word choice applies to what we wrote, not to what a
    vendor called their package. Vercel shipping "@ai-sdk/harness-fx" tripped
    the ban on "harness" twice, once inside a code span and once inside the
    changelog URL, and no rewrite could clear it because renaming someone
    else's package is not an option. The run was skipped on 1 September for
    exactly that.

    Offsets are preserved so the reported excerpt still points at the real
    text in the original body.
    """
    return _MASKABLE.sub(lambda m: " " * (m.end() - m.start()), body)


HUMANIZER_SYSTEM = """\
You are a line editor removing machine-writing tells from a draft blog post.

You will be given a post body in markdown and a list of specific violations.
Fix every violation with the smallest possible edit. Keep the author's
argument, structure, facts, links and headings exactly as they are. Do not
add new claims, new sections, or new statistics. Do not remove the links.

Rules you must respect while editing:
- Never use an em dash or en dash. Hyphens, commas or two sentences instead.
- Straight quotes and apostrophes only.
- Contractions everywhere a person would use them.
- No time-relative wording and no calendar dates anywhere in the body.
- Headings stay in sentence case.

If you are told the paragraphs or sentences are too uniform, this is a
structural edit, not a wording one. Vague instructions to "vary the rhythm"
will not move the measurement. Do this instead:
- Split the two longest paragraphs at their natural break, so a long one
  becomes a long one and a short one.
- Merge two adjacent short paragraphs that make one point between them.
- Add at least one paragraph of a single short sentence, standing alone, at
  a moment that deserves emphasis.
- Inside paragraphs, follow a long sentence with a four-word one.
The target is paragraphs ranging from under 20 words to over 90, not all of
them clustered around the average.

Return the corrected markdown body and nothing else. No preamble, no
explanation, no code fence around the whole post.
"""


async def humanize(
    body: str,
    *,
    client: AnthropicClient,
    settings: Settings,
    voice: str,
    max_rounds: int = 3,
) -> tuple[str, list[Violation]]:
    """Scan, ask the model to fix what was found, rescan.

    Returns the best body produced and whatever violations survived.
    """
    rules = load_rules(settings.banned_patterns_file)
    current = body

    for round_index in range(max_rounds):
        violations = scan(current, rules)
        if not violations:
            log.info("humanizer_clean", round=round_index)
            return current, []

        log.info(
            "humanizer_round",
            round=round_index,
            violations=len(violations),
            rules=sorted({v.rule for v in violations})[:12],
        )

        listing = "\n".join(
            f"- [{v.rule}] {v.message}" + (f"  Found near: {v.excerpt!r}" if v.excerpt else "")
            for v in violations[:60]
        )
        current = await client.complete(
            system_shared=voice,
            system_specific=HUMANIZER_SYSTEM,
            user=f"Violations to fix:\n{listing}\n\n---\n\nPost body:\n\n{current}",
            max_tokens=settings.max_tokens_humanizer,
            label=f"humanizer-{round_index}",
            thinking=False,
            effort="medium",
        )
        current = drop_orphan_code_fence(_strip_wrapping_fence(current))

    remaining = scan(current, rules)
    blocking = [v for v in remaining if v.rule not in ADVISORY_RULES]
    advisory = [v for v in remaining if v.rule in ADVISORY_RULES]

    if advisory:
        log.info("humanizer_advisory", violations=[v.as_dict() for v in advisory])
    if blocking:
        log.warning("humanizer_unresolved", violations=[v.as_dict() for v in blocking[:10]])
    return current, blocking


def _strip_wrapping_fence(text: str) -> str:
    """Drop a code fence the model may have wrapped the whole post in."""
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped
