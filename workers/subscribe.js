/**
 * Cloudflare Worker: email subscription handler for the AIBuilderHub newsletter.
 *
 * Accepts POST /api/subscribe with JSON { email, website? , t? }
 * and adds the address to a Brevo (Sendinblue) contact list.
 *
 * Required environment variables (Workers dashboard → Settings → Variables):
 *   BREVO_API_KEY      Brevo API key (secret, starts with "xkeysib-")
 *   BREVO_LIST_ID      numeric list id
 *   ALLOWED_ORIGIN     exact site origin, e.g. https://aibuilderhub.app
 *                      The worker FAILS CLOSED if this is missing.
 *
 * Optional:
 *   EXTRA_ORIGINS      comma-separated additional origins (previews, staging)
 *   TURNSTILE_SECRET   when set, a valid Turnstile token becomes mandatory
 *
 * Abuse controls implemented here: origin allowlist, honeypot field, request
 * body size cap, and optional Turnstile. Volumetric protection belongs in a
 * Cloudflare Rate Limiting rule on the /api/subscribe route — see
 * SECURITY-AUDIT.md.
 */

const MAX_BODY_BYTES = 1024;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i;

export default {
  async fetch(request, env) {
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

    try {
      const res = await fetch('https://api.brevo.com/v3/contacts', {
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
          attributes: { SOURCE: 'aibuilderhub-newsletter' },
        }),
      });

      // 201 = created, 204 = already existed and was updated.
      if (res.status === 201 || res.status === 204) {
        return json({ success: true }, 200, corsOrigin);
      }

      console.error('Brevo responded with status', res.status);
      return json({ error: 'Subscription failed. Please try again.' }, 502, corsOrigin);
    } catch (err) {
      console.error('Worker error:', err && err.message);
      return json({ error: 'Server error. Please try again.' }, 500, corsOrigin);
    }
  },
};

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
