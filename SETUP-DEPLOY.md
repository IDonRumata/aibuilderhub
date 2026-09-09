# Deploying the site: what was wrong, and what to do when it breaks again

## The symptom

Between 3 and 9 September 2026 the live site served a build made on
1 September. Three posts - `claude-fable-mythos-5-1-pricing` (3 September),
`gpt-6-astra-vercel-ai-gateway` (7 September) and
`chatgpt-images-2-5-sketch-feature` (9 September) - were in `main`, were not
drafts, built cleanly in CI, and returned 404 to readers.

The content pipeline was doing its job the whole time. Nobody could see the
result.

## What was actually wrong

The first version of this document guessed. The guess was wrong in a way worth
recording, because it would have cost real money and time to act on.

**The domain is served by a Worker, not by a Pages project.** In the Cloudflare
dashboard, Workers & Pages lists three things:

| Name | Kind | Serves |
|---|---|---|
| `aibuilderhub` | Worker | **aibuilderhub.app** - the live site |
| `aibuilderhub` | Pages | `aibuilderhub.pages.dev` - an abandoned July build |
| `aibuilderhub-subscribe` | Worker | the newsletter endpoint |

A Worker and a Pages project may carry the same name; they are different
objects. Every deploy instruction written against the Pages project would have
updated a URL nobody reads, and the domain would have stayed stale.

**The Worker was already connected to this repository, and was already
rebuilding on every push.** Its build settings are build command `npm run
build`, deploy command `npx wrangler deploy`, branch `main`. Nothing was
missing. Every build was simply failing, and had been since 3 September.

**Why it failed.** `main` carried no `wrangler.jsonc`. Faced with an Astro
project and no configuration, wrangler decided what kind of project this must
be: it pulled `@astrojs/cloudflare` at whatever version was newest, wired it in
as a server-side-rendering adapter, and rebuilt the site through it. That
adapter does not match the `astro` version pinned in `package-lock.json`, so
every deploy died on the same line:

```
[MISSING_EXPORT] "renderForPrerender" is not exported by
node_modules/astro/dist/core/app/entrypoints/index.js
  at node_modules/@astrojs/cloudflare/dist/utils/prerender.js:1:10
```

Nothing in the repository changed on 3 September. The adapter was never in
`package.json`, so it was never pinned, and a new release of it broke a build
that had worked the day before. The site has no server-side rendering at all -
`astro build` emits static files and no `_worker.js` - so the adapter should
never have been involved.

**Why nobody noticed.** The build command succeeded every time; only the deploy
command failed. The GitHub run was green, the pipeline state file said
published, and the watchdog measured the registry rather than the site. Every
signal available said healthy.

## The fix

`wrangler.jsonc` in the repository root now states what this project is: static
assets in `dist/`, no `main`, no adapter, no compatibility flags. There is
nothing left for wrangler to guess, and no second build to fall out of step
with the lockfile. The long comment at the top of that file is the explanation;
keep it there.

No credential was needed, and none was added. Deploys continue to happen where
they always happened - Cloudflare Workers Builds, on every push to `main`.

The workflow that writes a post now waits for the live URL to answer 200 and
raises a warning if it does not, so this class of failure can no longer pass
for health.

## When the site is stale again

1. **Check whether readers can see the newest post.** Not the repository - the
   site.

   ```bash
   curl -o /dev/null -w '%{http_code}\n' https://aibuilderhub.app/blog/<slug>/
   ```

2. **Look at the Worker's build history.** Cloudflare dashboard -> Workers &
   Pages -> `aibuilderhub` (the row whose custom domain is `aibuilderhub.app`)
   -> Deployments -> build history. A red row is a failed deploy; open it and
   read the last twenty lines of the log, which is where the actual error is.

3. **Retry from there.** The same page has **Retry build**. It needs no token
   and no laptop.

4. **If the build itself is fine but the domain is stale**, the domain is
   attached to something other than the `name` in `wrangler.jsonc`. Check
   Workers & Pages -> `aibuilderhub` -> Domains.

The `Deploy the site` workflow in GitHub Actions is a spare handle for the case
where the Cloudflare wiring is broken rather than the build. It needs
`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as repository secrets, which
do not exist today; it refuses to run rather than pretending to work. Creating
them is only worth doing if step 3 is ever unavailable.
