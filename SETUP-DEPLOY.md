# Deploying the site: what is wrong and how to fix it

## The symptom

On 7 September 2026 the live site was serving a build made on 1 September.
Two posts - `claude-fable-mythos-5-1-pricing` (3 September) and
`gpt-6-astra-vercel-ai-gateway` (7 September) - were in `main`, were not
drafts, built cleanly in CI, and returned 404 to readers.

Measured, not assumed:

| URL | Result |
|---|---|
| `aibuilderhub.app/blog/` | 200, lists 27 posts, newest is 1 September |
| `aibuilderhub.app/blog/claude-fable-mythos-5-1-pricing/` | 404 |
| `aibuilderhub.pages.dev/blog/` | 200, lists **9** posts - a much older build |
| `main.aibuilderhub.pages.dev/blog/` | 404 - no branch alias exists |

Two conclusions follow. The custom domain is served by a different Pages
deployment than `aibuilderhub.pages.dev`, and nothing rebuilds the site when
`main` changes: a git-connected project would have a `main.<project>.pages.dev`
alias, and this one does not.

So the pipeline has been doing its job and the result has been invisible. Any
work on publishing cadence is pointless until this is fixed - a post that
readers cannot open is not published.

## The fix

The repository now deploys the site itself, from the same workflow that writes
the post, instead of hoping something else notices the push. It needs one
credential, which only the account owner can create.

### 1. Create a Cloudflare API token

1. <https://dash.cloudflare.com/profile/api-tokens> -> **Create Token**
2. Use the template **Edit Cloudflare Workers**, or a custom token with
   permission **Account / Cloudflare Pages / Edit**
3. Restrict it to the one account that owns the site
4. Create, then copy the token. It is shown once.

### 2. Find the account ID and the project name

Both are in the dashboard: **Workers & Pages**. The account ID is in the URL
(`dash.cloudflare.com/<account id>/...`), and the project is the row whose
**Custom domains** column says `aibuilderhub.app`. It is not the project called
`aibuilderhub`, which serves an old build with 9 posts.

**Write down what that row calls itself: "Pages" or "Worker".** It matters,
and it cannot be determined from outside: the seven obvious candidate names
(`aibuilderhub-app`, `aibuilderhub-site`, `aibuilder-hub`, `aibuilderhub-web`,
`aibuilderhub2`, `aibuilderhub-astro`, `aibuilderhubapp`) all fail to resolve
as `*.pages.dev`, so the deployment serving the domain is either a Pages
project under some other name or a Worker serving static assets. The workflow
runs `wrangler pages deploy`, which is right for a Pages project and wrong for
a Worker - a Worker needs `wrangler deploy` and a `wrangler.toml` instead. If
the row says Worker, say so before adding the token and the workflow gets a
one-line change.

### 3. Put them in the repository

GitHub -> the repo -> **Settings** -> **Secrets and variables** -> **Actions**:

| Where | Name | Value |
|---|---|---|
| Secrets | `CLOUDFLARE_API_TOKEN` | the token from step 1 |
| Secrets | `CLOUDFLARE_ACCOUNT_ID` | the account ID from step 2 |
| Variables | `CLOUDFLARE_PAGES_PROJECT` | the project name from step 2 |

The variable can be left out if the project really is called `aibuilderhub`;
the workflow falls back to that name.

### 4. Push the waiting posts live

Actions -> **Deploy the site** -> **Run workflow**. It builds from `main`,
deploys, and then checks over HTTP that the newest post actually answers 200.
If the deploy succeeds but the check fails, the custom domain belongs to a
different project than the one in `CLOUDFLARE_PAGES_PROJECT`.

From then on the content pipeline deploys automatically after every post.

## If wrangler refuses the upload

If the deploy step fails with a message about the project being connected to a
Git repository, then the project *is* git-connected after all and its builds
are failing rather than not running. In that case do not add the token: open
the project in the dashboard, look at the failed builds, and fix the build
there instead. The two facts to check first are the build command
(`npm run build`) and the Node version (the site needs 20.19 or newer; the
repository pins 22 in `.node-version`).

## Why not a deploy hook

Cloudflare deploy hooks only exist for git-connected projects, and this one
does not appear to be git-connected. An API token works either way and keeps
the failure visible in Actions, where the rest of the pipeline already reports.
