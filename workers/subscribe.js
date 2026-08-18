/**
 * Cloudflare Worker: email subscription handler for the AIBuilderHub newsletter.
 *
 * Accepts POST /api/subscribe with JSON { email, website?, source?, t? }
 * and performs a dual write:
 *   1. Brevo  - sends the double opt-in confirmation email and owns the send
 *               infrastructure for the digest itself. This is the source of
 *               truth for subscription status.
 *   2. NocoDB - our own copy of the subscriber record, so the list is not
 *               locked inside a third party. Written best-effort in the
 *               background; a NocoDB outage must never break the form.
 *
 * Required environment variables (Workers dashboard -> Settings -> Variables):
 *   BREVO_API_KEY          Brevo API key (secret, starts with "xkeysib-")
 *   BREVO_LIST_ID          numeric list id
 *   ALLOWED_ORIGIN         exact site origin, e.g. https://aibuilderhub.app
 *                          The worker FAILS CLOSED if this is missing.
 *
 * Double opt-in (GDPR - strongly recommended, see SETUP-NEWSLETTER.md):
 *   BREVO_DOI_TEMPLATE_ID  numeric id of the Brevo double opt-in template.
 *                          When set, the worker uses Brevo's DOI endpoint and
 *                          the contact is only added to the list AFTER the
 *                          subscriber clicks the link in the email.
 *                          When unset, falls back to single opt-in.
 *   DOI_REDIRECT_URL       where Brevo sends the user after they confirm.
 *                          Defaults to ALLOWED_ORIGIN + /newsletter/confirmed
 *
 * NocoDB mirror (optional - skipped silently when not configured):
 *   NOCODB_BASE_URL        e.g. https://db.don-rumata.ru
 *   NOCODB_TABLE_ID        table id from the NocoDB table URL
 *   NOCODB_TOKEN           API token (secret) from NocoDB -> Account -> Tokens
 *
 * Optional:
 *   EXTRA_ORIGINS          comma-separated additional origins (previews, staging)
 *   TURNSTILE_SECRET       when set, a valid Turnstile token becomes mandatory
 *
 * Abuse controls implemented here: origin allowlist, honeypot field, request
 * body size cap, and optional Turnstile. Volumetric protection belongs in a
 * Cloudflare Rate Limiting rule on the /api/subscribe route - see
 * SECURITY-AUDIT.md.
 */

const MAX_BODY_BYTES = 1024;
const MAX_SOURCE_LEN = 200;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i;

export default {
  async fetch(request, env, ctx) {
    const allowed = allowedOrigins(env);

    // Fail closed: without a configured origin the worker refuses to serve.
    if (allowed.length === 0) {
      console.error('ALLOWED_ORIGIN is not configured');
      return json({ error: 'Service unavailable.' }, 503, null);
    }

    const origin = request.headers.get('Origin');
    const corsOrigin = origin && allowed.includes(origin) ? origin : null;

    if (request.method === 'OPTIONS') {
      return json(null, corsOrigin ? 204 : 403, corsOrigin);
    }

    const url = new URL(request.url);
    if (request.method !== 'POST' || url.pathname !== '/api/subscribe') {
      return json({ error: 'Not found' }, 404, corsOrigin);
    }

    // Same-site requests from our own pages always carry Origin. Anything
    // else (curl, scripts, other sites) is rejected before touching Brevo.
    if (!corsOrigin || !refererAllowed(request, allowed)) {
      return json({ error: 'Forbidden' }, 403, corsOrigin);
    }

    const contentLength = Number(request.headers.get('Content-Length') || 0);
    if (contentLength > MAX_BODY_BYTES) {
      return json({ error: 'Payload too large' }, 413, corsOrigin);
    }

    let body;
    try {
      const raw = await request.text();
      if (raw.length > MAX_BODY_BYTES) {
        return json({ error: 'Payload too large' }, 413, corsOrigin);
      }
      body = JSON.parse(raw);
    } catch {
      return json({ error: 'Invalid JSON' }, 400, corsOrigin);
    }

    if (!body || typeof body !== 'object') {
      return json({ error: 'Invalid request' }, 400, corsOrigin);
    }

    // Honeypot: the form ships a hidden "website" input that humans never
    // fill. Answer 200 so bots get no signal that they were detected.
    if (typeof body.website === 'string' && body.website.trim() !== '') {
      return json({ success: true }, 200, corsOrigin);
    }

    if (env.TURNSTILE_SECRET) {
      const ok = await verifyTurnstile(env.TURNSTILE_SECRET, body.t, request);
      if (!ok) {
        return json({ error: 'Verification failed. Please try again.' }, 403, corsOrigin);
      }
    }

    const email = String(body.email || '').trim().toLowerCase();
    if (email.length > 254 || !EMAIL_RE.test(email)) {
      return json({ error: 'Invalid email address' }, 400, corsOrigin);
    }

    // Which page the form was submitted from. Client-supplied, so it is
    // treated as untrusted: path-shaped strings only, hard length cap.
    const source = sanitizeSource(body.source);

    try {
      const doi = Boolean(env.BREVO_DOI_TEMPLATE_ID);
      const res = doi
        ? await brevoDoubleOptIn(env, email, source, allowed[0])
        : await brevoSingleOptIn(env, email, source);

      // DOI endpoint returns 204 on success. Contacts endpoint returns
      // 201 (created) or 204 (already existed and was updated).
      if (res.status === 201 || res.status === 204) {
        // Mirror into NocoDB after the response is on its way back. The
        // subscription already succeeded in Brevo, so a NocoDB failure is
        // logged but never surfaced to the visitor.
        if (ctx && typeof ctx.waitUntil === 'function') {
          ctx.waitUntil(mirrorToNocoDB(env, { email, source, doi, request }));
        }
        return json({ success: true, doi }, 200, corsOrigin);
      }

      console.error('Brevo responded with status', res.status);
      return json({ error: 'Subscription failed. Please try again.' }, 502, corsOrigin);
    } catch (err) {
      console.error('Worker error:', err && err.message);
      return json({ error: 'Server error. Please try again.' }, 500, corsOrigin);
    }
  },
};

/**
 * Adds the contact straight to the list. No confirmation email is sent.
 * Only used when BREVO_DOI_TEMPLATE_ID is not configured.
 *
 * @param {object} env     Worker environment bindings.
 * @param {string} email   Validated, lowercased address.
 * @param {string} source  Sanitised page path the form was submitted from.
 * @returns {Promise<Response>} Raw Brevo response.
 */
function brevoSingleOptIn(env, email, source) {
  return fetch('https://api.brevo.com/v3/contacts', {
    method: 'POST',
    headers: {
      accept: 'application/json',
      'content-type': 'application/json',
      'api-key': env.BREVO_API_KEY,
    },
    body: JSON.stringify({
      email,
      listIds: [Number(env.BREVO_LIST_ID)],
      updateEnabled: true,
      attributes: { SOURCE: source || 'aibuilderhub-newsletter' },
    }),
  });
}

/**
 * Sends a double opt-in confirmation email via Brevo. The contact is added
 * to the list only after the recipient clicks the link, which is what makes
 * the consent record defensible under GDPR.
 *
 * @param {object} env         Worker environment bindings.
 * @param {string} email       Validated, lowercased address.
 * @param {string} source      Sanitised page path the form was submitted from.
 * @param {string} siteOrigin  Primary allowed origin, used for the fallback
 *                             redirect target.
 * @returns {Promise<Response>} Raw Brevo response (204 on success).
 */
function brevoDoubleOptIn(env, email, source, siteOrigin) {
  const redirect = env.DOI_REDIRECT_URL || `${siteOrigin}/newsletter/confirmed`;

  return fetch('https://api.brevo.com/v3/contacts/doubleOptinConfirmation', {
    method: 'POST',
    headers: {
      accept: 'application/json',
      'content-type': 'application/json',
      'api-key': env.BREVO_API_KEY,
    },
    body: JSON.stringify({
      email,
      includeListIds: [Number(env.BREVO_LIST_ID)],
      templateId: Number(env.BREVO_DOI_TEMPLATE_ID),
      redirectionUrl: redirect,
      attributes: { SOURCE: source || 'aibuilderhub-newsletter' },
    }),
  });
}

/**
 * Writes the subscriber into our own NocoDB table. Best-effort by design:
 * every failure path logs and returns rather than throwing, because this runs
 * inside ctx.waitUntil after the visitor already got a success response.
 *
 * Skipped entirely when the NocoDB variables are not configured, so the
 * worker keeps working before the table exists.
 *
 * @param {object} env             Worker environment bindings.
 * @param {object} params
 * @param {string} params.email    Validated, lowercased address.
 * @param {string} params.source   Sanitised page path.
 * @param {boolean} params.doi     Whether a confirmation email was sent.
 * @param {Request} params.request Original request, for Cloudflare geo headers.
 * @returns {Promise<void>}
 */
async function mirrorToNocoDB(env, { email, source, doi, request }) {
  const { NOCODB_BASE_URL, NOCODB_TABLE_ID, NOCODB_TOKEN } = env;
  if (!NOCODB_BASE_URL || !NOCODB_TABLE_ID || !NOCODB_TOKEN) return;

  const endpoint =
    `${NOCODB_BASE_URL.replace(/\/+$/, '')}/api/v2/tables/${NOCODB_TABLE_ID}/records`;

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'xc-token': NOCODB_TOKEN,
      },
      body: JSON.stringify({
        email,
        status: doi ? 'pending' : 'confirmed',
        source_page: source || '/',
        country: request.headers.get('CF-IPCountry') || '',
        subscribed_at: new Date().toISOString(),
      }),
    });

    if (!res.ok) {
      console.error('NocoDB mirror failed with status', res.status);
    }
  } catch (err) {
    console.error('NocoDB mirror error:', err && err.message);
  }
}

/**
 * Normalises the client-supplied source path. Anything that is not a simple
 * same-site path is discarded rather than stored.
 *
 * @param {unknown} value Raw value from the request body.
 * @returns {string} A safe path, or an empty string.
 */
function sanitizeSource(value) {
  if (typeof value !== 'string') return '';
  const trimmed = value.trim().slice(0, MAX_SOURCE_LEN);
  return /^\/[\w\-/.]*$/.test(trimmed) ? trimmed : '';
}

function allowedOrigins(env) {
  const list = [env.ALLOWED_ORIGIN, ...String(env.EXTRA_ORIGINS || '').split(',')];
  return list.map((o) => (o || '').trim()).filter(Boolean);
}

function refererAllowed(request, allowed) {
  const referer = request.headers.get('Referer');
  if (!referer) return true; // Origin was already checked; Referer may be stripped.
  try {
    return allowed.includes(new URL(referer).origin);
  } catch {
    return false;
  }
}

async function verifyTurnstile(secret, token, request) {
  if (!token || typeof token !== 'string') return false;
  try {
    const form = new FormData();
    form.append('secret', secret);
    form.append('response', token);
    const ip = request.headers.get('CF-Connecting-IP');
    if (ip) form.append('remoteip', ip);

    const res = await fetch(
      'https://challenges.cloudflare.com/turnstile/v0/siteverify',
      { method: 'POST', body: form }
    );
    const data = await res.json();
    return data.success === true;
  } catch (err) {
    console.error('Turnstile verification error:', err && err.message);
    return false;
  }
}

function json(body, status, allowedOrigin) {
  const headers = {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    Vary: 'Origin',
  };
  if (allowedOrigin) {
    headers['Access-Control-Allow-Origin'] = allowedOrigin;
    headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS';
    headers['Access-Control-Allow-Headers'] = 'Content-Type';
    headers['Access-Control-Max-Age'] = '86400';
  }
  return new Response(body !== null ? JSON.stringify(body) : null, { status, headers });
}
