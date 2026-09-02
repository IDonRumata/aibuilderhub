# Upstream — emilkowalski/skills

These skills are vendored, unmodified, from:

- Repo: https://github.com/emilkowalski/skills
- Path: `skills/<name>/`
- Commit: `d23d7f88a2e21c9e4b1418c7abe420f5c1052ba7` (2026-08-21)
- License: MIT (see `LICENSE-emilkowalski`)

Author: Emil Kowalski (ex-Vercel, ex-Linear; author of Sonner and Vaul).

## Vendored

| Skill | Auto-invoked | What it does |
| --- | --- | --- |
| `emil-design-eng` | yes | Umbrella skill: UI polish, component design, the invisible details. |
| `animate` | yes | Builds a web animation from scratch: purpose, tool, properties, curve, duration, exit. |
| `review-animations` | no (`disable-model-invocation`) | Strict review of motion code against `STANDARDS.md`. |
| `improve-animations` | yes | Read-only audit of all motion in the codebase, emits prioritized plans. |
| `find-animation-opportunities` | yes | Finds places that should animate, and rejects the ones that should not. |
| `animation-vocabulary` | yes | Reverse glossary: vague description -> exact term. |
| `apple-design` | yes | Apple's fluid-interface principles (WWDC) translated to the web platform. |
| `pick-ui-library` | no (`disable-model-invocation`) | Curated library picks instead of hand-rolled or abandoned packages. |
| `prototype` | no (`disable-model-invocation`) | Builds N divergent variants of one UI piece behind a visual picker. |

## Not vendored

Upstream also ships three skills that do not apply to this codebase (Astro,
zero-JS by default, no React Native, no Swift). Skill descriptions are loaded
into every session's context, so carrying dead ones costs tokens on every turn.

- `animate-expo` — React Native / Reanimated / Expo Router.
- `write-swift` — Swift 6 language guide.
- `ask-sonner` — Sonner toast library (React-only; this site ships no React).

Clone upstream directly if the stack ever changes.

## Updating

```bash
git clone --depth 1 https://github.com/emilkowalski/skills /tmp/emil-skills
for s in emil-design-eng animate review-animations improve-animations \
         find-animation-opportunities animation-vocabulary apple-design \
         pick-ui-library prototype; do
  rsync -a --delete "/tmp/emil-skills/skills/$s/" ".claude/skills/$s/"
done
cp /tmp/emil-skills/LICENSE .claude/skills/LICENSE-emilkowalski
```

Then refresh the commit hash and date above.

## Caveat for this project

This site is static Astro with **zero JavaScript by default** (see `README.md`).
Any motion these skills produce must stay CSS-only (`transform`/`opacity`,
`@media (prefers-reduced-motion: reduce)` honored) unless a component genuinely
justifies a client directive. Shipping a motion library to hit a 300ms ease-out
would trade a Core Web Vitals score for a flourish — the skills raise the craft
bar, they do not override the performance budget.
