# Newsletter setup: NocoDB + Brevo

Architecture: the subscribe worker writes to two places.

```
Form (footer + end of every post)
   -> POST /api/subscribe  (Cloudflare Worker)
        |
        +--> Brevo   sends the double opt-in email, owns subscription status,
        |            sends the digest itself
        |
        +--> NocoDB  our own copy of the record (best-effort, background write)
```

**Why both:** NocoDB is a database, it cannot send email. Double opt-in requires
sending a confirmation email, so Brevo stays. NocoDB gives us ownership of the
list so it is not locked inside a third party.

**Failure behaviour:** if NocoDB is down, the subscription still succeeds through
Brevo and the error is logged. NocoDB is never a single point of failure for the
form on the site.

---

## Step 1 - Create the NocoDB table

**Automated (recommended).** Run from the project root in PowerShell:

```powershell
$env:NOCODB_TOKEN="your-token-here"
node scripts/setup-nocodb.mjs
```

The script creates the table with the correct schema and prints the
`NOCODB_TABLE_ID` you need in step 4. It is idempotent - running it twice will
not create a duplicate table.

**Status: done.** The table exists, `status` is a SingleSelect with the three
options. Table id: `ms53n43un2ejcq1`

If it fails, the error output names the likely cause (expired token, wrong base
id, server unreachable).

**Manual alternative.** In NocoDB (`https://db.don-rumata.ru`, base
`pq5rnkutmq37uz7`), create a table named `subscribers` with exactly these fields:

| Field name       | NocoDB type   | Notes                                     |
|------------------|---------------|-------------------------------------------|
| `email`          | Email         | Set to unique if available                |
| `status`         | Single Select | Options: `pending`, `confirmed`, `unsubscribed` |
| `source_page`    | Single Line Text | Which page the form was submitted from |
| `country`        | Single Line Text | Two-letter code from Cloudflare        |
| `subscribed_at`  | DateTime      | ISO timestamp written by the worker       |

Field names must match exactly - they are the JSON keys the worker sends.

**Get the table ID:** open the table, look at the browser URL. The segment that
starts with `m` (for example `mxyz123abc456`) is the table ID.

## Step 2 - Create the NocoDB API token

1. NocoDB -> click your avatar (top right) -> **Account Settings**
2. **Tokens** -> **Add New Token**
3. Name it `aibuilderhub-worker`, copy the value immediately

Treat this token like a password. It grants write access to your base.

## Step 3 - Create the Brevo double opt-in template

1. Brevo -> **Campaigns** -> **Templates** -> **Create a new template**
2. Choose **Double opt-in confirmation** as the purpose
3. The template body must contain the confirmation link variable:
   `{{ doubleOptinUrl }}` - without it the flow silently breaks
4. Save and activate it, then note the numeric template ID from the URL

Suggested copy:

> **Subject:** Confirm your AIBuilderHub subscription
>
> One click and you're in. Confirm your email to start getting the weekly
> digest of AI builder reviews and pricing changes.
>
> [Confirm subscription]({{ doubleOptinUrl }})
>
> If you didn't sign up, ignore this email and nothing happens.

## Step 4 - Set the worker environment variables

Cloudflare dashboard -> **Workers & Pages** -> your subscribe worker ->
**Settings** -> **Variables and Secrets**.

| Variable | Type | Value |
|---|---|---|
| `ALLOWED_ORIGIN` | Text | `https://aibuilderhub.app` |
| `BREVO_API_KEY` | **Secret** | your `xkeysib-...` key |
| `BREVO_LIST_ID` | Text | numeric list id |
| `BREVO_DOI_TEMPLATE_ID` | Text | template id from step 3 |
| `DOI_REDIRECT_URL` | Text | `https://aibuilderhub.app/newsletter/confirmed` |
| `NOCODB_BASE_URL` | Text | `https://db.don-rumata.ru` |
| `NOCODB_TABLE_ID` | Text | `ms53n43un2ejcq1` |
| `NOCODB_TOKEN` | **Secret** | token from step 2 |

`BREVO_API_KEY` and `NOCODB_TOKEN` must be **Secret**, not Text. Text variables
are readable in the dashboard by anyone with access to the account.

**Graceful degradation is built in:**
- No `BREVO_DOI_TEMPLATE_ID` -> falls back to single opt-in (not GDPR-safe, fix it)
- No NocoDB variables -> the mirror write is skipped silently, Brevo still works

## Step 5 - Deploy the worker

```
cd "D:\Claude Code doc\Projects\Profitable website"
npx wrangler deploy workers/subscribe.js
```

The worker must be routed to `aibuilderhub.app/api/subscribe`. Check
Cloudflare -> Workers -> your worker -> **Settings** -> **Domains & Routes**.

## Step 6 - Test end to end

1. Open the site, submit a real address in the footer form
2. Expected on-page message: *"Almost there - check your inbox and confirm..."*
3. Check NocoDB: a row appears with `status = pending`
4. Open the email, click confirm -> you land on `/newsletter/confirmed`
5. Check Brevo: the contact is now in the list

If step 3 fails but the email arrives, the NocoDB config is wrong - check the
worker logs with `npx wrangler tail`.

---

## Known gap: status never flips to `confirmed` in NocoDB

The worker writes `pending` when the email is sent. Brevo knows when the user
confirms, but nothing tells NocoDB.

Two ways to close this, in order of effort:

1. **Brevo webhook** (recommended) - Brevo -> Settings -> Webhooks -> add a
   webhook on the `contact confirmed` event pointing at a second small worker
   that PATCHes the NocoDB row. Real time, no polling.
2. **Scheduled reconciliation** - a Cron Trigger worker that pulls the Brevo
   list once a day and updates NocoDB rows to match. Simpler, up to 24h stale.

Until one of these is built, treat Brevo as the source of truth for who is
actually subscribed, and NocoDB as a signup log.

---

## GDPR notes (Poland/EU jurisdiction)

What is now in place:

- Double opt-in - proof of consent, the strongest position under GDPR
- Privacy Policy link next to the footer form
- Brevo handles the unsubscribe link in every campaign automatically

What still needs attention:

- **Data retention.** Decide how long unconfirmed `pending` rows are kept.
  Anything past 30 days should be deleted - it is personal data you have no
  consent to hold.
- **Right to erasure.** A subscriber can demand deletion. Deleting from Brevo
  alone is no longer enough now that NocoDB holds a copy. Delete from both.
- **Records of processing.** NocoDB on your own server means you are the data
  controller for that copy. Make sure the Privacy Policy mentions where
  subscriber data is stored.

This is a technical summary, not legal advice - worth a check with a lawyer
before the list gets large.
