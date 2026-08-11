# Security audit - aibuilderhub.app

One-off audit carried out alongside the content-automation build, plus the CI
checks that now keep the findings from regressing.

Scope: the Astro site, the Cloudflare Worker in `workers/`, the published
`dist/` output, the full git history, and the new `automation/` pipeline.

---

## Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | No security response headers on any route | High | Fixed |
| 2 | `/api/subscribe` was an open, unthrottled write endpoint | High | Fixed in code, needs worker redeploy |
| 3 | Worker fell back to `Access-Control-Allow-Origin: *` when misconfigured | Medium | Fixed |
| 4 | 7 npm advisories (6 high) in the dependency tree | High | Fixed |
| 5 | Decap CMS admin panel is publicly reachable and non-functional | Medium | Mitigated, removal recommended |
| 6 | Inline event handlers made a strict CSP impossible | Medium | Fixed |
| 7 | Draft posts were still given public URLs | Low | Fixed |
| 8 | Secrets in git history | - | None found |
| 9 | Secrets or source leaking into `dist/` | - | None found |
| 10 | Cloudflare zone settings | - | Needs owner action |

---

## 1. Missing security headers

**Was**: the live site returned no `Content-Security-Policy`,
`Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy` or `Permissions-Policy`. Verified with
`curl -sSI https://aibuilderhub.app/`.

**Fixed**: `public/_headers` now sets all of them, plus COOP and CORP, and
marks `/_astro/*` immutable. Cloudflare Pages applies the file automatically.

CSP still allows `'unsafe-inline'` for `script-src`. Two inline scripts cannot
move to a bundle: the theme bootstrap has to run before first paint or the page
flashes the wrong theme, and the GA4 snippet is inline by design. Every inline
*event handler attribute* was removed (see finding 6), so tightening this to
hashes later is a template-only change with no behaviour risk.

**Verify after deploy**:

```bash
curl -sSI https://aibuilderhub.app/ | sort
```

## 2. Open subscription endpoint

**Was**: `POST /api/subscribe` accepted any JSON body from any origin with no
rate limit, no bot check and no origin verification, and wrote the address
straight into the Brevo contact list. Confirmed against production during the
audit: an arbitrary address was accepted with `{"success":true}`.

That allows unlimited list poisoning, burning the Brevo quota, and using the
site as an open relay for address validation.

**Note**: the audit probe added one junk contact, `probe-check@example.invalid`,
to the Brevo list. Delete it.

**Fixed** in `workers/subscribe.js`:

- fails closed when `ALLOWED_ORIGIN` is unset (was: wildcard CORS)
- `Origin` and `Referer` must match the allowlist, else 403
- hidden honeypot field, added to both newsletter forms; a filled honeypot gets
  a fake success so bots learn nothing
- request body capped at 1 KB
- optional Turnstile verification that activates as soon as `TURNSTILE_SECRET`
  is set on the worker
- upstream error details no longer echoed to the caller

**Still needed from the owner**:

1. Redeploy the worker. It is not part of the Pages deployment, so a push to
   `main` does not update it.
2. Confirm `ALLOWED_ORIGIN=https://aibuilderhub.app` is set, or the worker will
   now return 503 by design.
3. Add a Cloudflare Rate Limiting rule on `/api/subscribe` (for example 5
   requests per minute per IP). Origin checks stop browsers, not `curl`; volume
   control belongs at the edge.
4. Optionally create a Turnstile widget and set `TURNSTILE_SECRET`.

## 3. Wildcard CORS fallback

`corsResponse()` fell back to `'*'` whenever `ALLOWED_ORIGIN` was missing.
Replaced with fail-closed behaviour and a `Vary: Origin` header.

## 4. Dependency vulnerabilities

`npm audit` reported 7 advisories, 6 of them high: `astro`, `vite`, `esbuild`,
`sharp`, `js-yaml`, `nanoid`, `postcss`.

`npm audit fix` cleared three. The rest had no fix below `astro@7`, so the site
was migrated from Astro 4 to Astro 7:

- `@astrojs/tailwind` is archived with no Astro 5+ peer range, so Tailwind 3 is
  now wired through `postcss.config.mjs`; `tailwind.config.mjs` and every
  `@apply` rule are untouched
- content collections moved to the Content Layer API (`src/content.config.ts`,
  `glob()` loader, `entry.id`, `render(entry)`)
- `ViewTransitions` renamed to `ClientRouter`
- restored spaces the new `compressHTML: 'jsx'` default strips between a text
  node and a following inline link

`npm audit` and `pip-audit` are both now CI steps that fail the build on a
high or critical finding. Dependabot should be enabled in the repository
settings (Settings, Code security, Dependabot alerts and security updates) -
that is a UI action and cannot be done from the repo.

## 5. Decap CMS admin panel

`public/admin/` is served publicly at `/admin/`. It loads its bundle from
`unpkg.com` at an unpinned `^3.0.0` range with no Subresource Integrity, and
its configured auth backend is Netlify Identity (`base_url: api.netlify.com`),
which does not exist for a site hosted on Cloudflare Pages. So it is both a
supply-chain surface and non-functional.

**Mitigated**: `Disallow: /admin/` in `robots.txt`, `X-Robots-Tag: noindex`,
and a separate scoped CSP for `/admin/*` so the site-wide policy does not have
to allow `unpkg.com` or `unsafe-eval`.

**Recommended**: delete `public/admin/` entirely. Publishing is automated now,
and posts are edited directly in the repository. Left in place because deleting
a feature is the owner's call, not the auditor's.

## 6. Inline event handlers

`onclick`, `onsubmit`, `onmouseover` and `onmouseout` attributes appeared in
`Header.astro`, `PostCard.astro`, `index.astro` and `PostLayout.astro`. Inline
handlers are blocked by any CSP that does not include `unsafe-hashes`, so they
were the reason a meaningful policy could not be applied.

All were removed. Hovers became CSS `:hover` rules, the theme toggle and the
newsletter forms use delegated `addEventListener` listeners. Verified in a
browser against the production build: `document.querySelectorAll('[onclick],
[onsubmit],[onmouseover],[onmouseout]').length === 0` on every page type.

## 7. Draft posts were publicly routable

`src/pages/blog/[...slug].astro` called `getCollection('blog')` without a
filter, so a post with `draft: true` still got a public URL; only the index
listings hid it. The pipeline publishes with `draft: true` during review, which
would have made those posts reachable by anyone guessing the slug. The route
now filters drafts out.

## 8. Secrets in git history

No credential patterns found across all 119 blobs in the history (64 text
blobs scanned). gitleaks and trufflehog were unavailable locally (no Docker
daemon), so the one-off pass used a purpose-written scanner covering Anthropic,
OpenAI, Brevo, Voyage, AWS, GitHub, Slack, Google, Stripe, Telegram and
Cloudflare token formats, private key blocks, and generic
`secret = "..."`-style assignments.

Ongoing coverage: the `secrets` job in `.github/workflows/ci.yml` runs
TruffleHog over the full history on every push and pull request.

The only credentials the project needs at runtime are the Brevo key and origin
on the Worker, and `ANTHROPIC_API_KEY` (plus optionally `VOYAGE_API_KEY`) in
GitHub Actions secrets. None of them are in the repository.

## 9. Build output

`dist/` contains only HTML, hashed CSS, `favicon.svg`, `robots.txt`,
`_headers`, the sitemap, the RSS feed and the `admin/` panel. No `.env`, no
source maps, no draft content, no secret markers.

`state/published_topics.json` and `state/embeddings.json` are committed by the
pipeline. They contain post slugs, titles, public source URLs and numeric
vectors. Nothing sensitive, and nothing is served from `automation/`.

## 10. Cloudflare zone settings - owner action

These cannot be checked or changed from the repository. In the Cloudflare
dashboard for `aibuilderhub.app`:

- SSL/TLS, Edge Certificates: **Always Use HTTPS** on
- SSL/TLS, Edge Certificates: **Minimum TLS Version** 1.2 or higher
- SSL/TLS: encryption mode **Full (strict)**
- Security, Bots: **Bot Fight Mode** on
- Security, WAF: a rate limiting rule on `/api/subscribe`

HSTS is already asserted from `_headers` with a two-year max-age and
`preload`. Do not submit the domain to the HSTS preload list until you are
certain every subdomain will stay on HTTPS permanently.

---

## What now runs in CI

`.github/workflows/ci.yml`, on every push and pull request:

- Astro build must succeed
- `npm audit --audit-level=high` must be clean
- `ruff` lint over the pipeline
- the pipeline test suite, including the style gate that fails if any generated
  post contains a banned pattern
- `pip-audit --strict` on the Python dependencies
- TruffleHog over the full git history

`.github/workflows/content-pipeline.yml` additionally re-runs the style gate
and a full site build before it is allowed to commit anything.

## Residual risk

- `script-src 'unsafe-inline'` remains, for the reasons in finding 1. The site
  is static with no user-generated content rendered anywhere, so the practical
  XSS surface is close to zero, but this is the one item that stops the policy
  from being strict.
- Google Analytics and Google Fonts are third-party origins on every page.
  Self-hosting Inter would remove one of them.
- The subscription endpoint remains reachable by anything that can set an
  `Origin` header until the edge rate limit is in place.
