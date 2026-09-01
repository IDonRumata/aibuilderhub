"""A style rule applies to our prose, not to other people's names.

Vercel shipped a package called `@ai-sdk/harness-fx`. "harness" is on the
banned-word list as an AI cliche ("harness the power of"), so the post about
that release tripped the rule twice - once inside a code span, once inside the
changelog URL - and no rewrite could clear it, because renaming somebody
else's package is not an option. The 1 September run was skipped on it.
"""

from __future__ import annotations

from aibh_pipeline.services.humanizer import load_rules, mask_non_prose, scan

VENDOR_POST = (
    "## What shipped\n\n"
    "Vercel added the [fx adapter](https://vercel.com/changelog/fx-ai-sdk-harness-adapter) "
    "today. You wire it up with `@ai-sdk/harness-fx` and it talks over the wire.\n"
)

CLICHE_POST = "## What shipped\n\nYou should harness the power of AI to grow your business.\n"


def test_a_banned_word_inside_code_or_a_url_is_not_a_violation(settings):
    rules = load_rules(settings.banned_patterns_file)
    assert [v.rule for v in scan(VENDOR_POST, rules) if "harness" in v.rule] == []


def test_the_same_word_in_our_own_prose_still_is(settings):
    rules = load_rules(settings.banned_patterns_file)
    assert [v.rule for v in scan(CLICHE_POST, rules) if "harness" in v.rule] == ["word:harness"]


def test_masking_preserves_offsets_so_excerpts_stay_accurate():
    masked = mask_non_prose(VENDOR_POST)
    assert len(masked) == len(VENDOR_POST)
    # Prose and link text survive; the target half and the code span are
    # blanked. The closing bracket goes with the target, which is fine - no
    # style rule keys off it.
    assert "Vercel added the [fx adapter" in masked
    assert "today. You wire it up with" in masked
    assert "harness" not in masked
