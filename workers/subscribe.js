/**
 * Cloudflare Worker: Email subscription handler for AIBuilderHub newsletter
 *
 * Accepts POST /api/subscribe with JSON { email }
 * Adds the email to a Brevo (Sendinblue) contact list
 *
 * Environment variables (set in Cloudflare Workers dashboard):
 *   BREVO_API_KEY   — your Brevo API key (starts with "xkeysib-...")
 *   BREVO_LIST_ID   — the numeric ID of your Brevo list (e.g. 3)
 *   ALLOWED_ORIGIN  — your site URL (e.g. https://aibuilderhub.app)
 */

export default {
  async fetch(request, env) {
    // CORS preflight
    if (request.method === 'OPTIONS') {
      return corsResponse(null, 204, env.ALLOWED_ORIGIN);
    }

    // Only handle POST /api/subscribe
    const url = new URL(request.url);
    if (request.method !== 'POST' || url.pathname !== '/api/subscribe') {
      return corsResponse({ error: 'Not found' }, 404, env.ALLOWED_ORIGIN);
    }

    // Parse body
    let body;
    try {
      body = await request.json();
    } catch {
      return corsResponse({ error: 'Invalid JSON' }, 400, env.ALLOWED_ORIGIN);
    }

    const email = (body.email || '').trim().toLowerCase();

    // Basic email validation
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return corsResponse({ error: 'Invalid email address' }, 400, env.ALLOWED_ORIGIN);
    }

    // Call Brevo API
    try {
      const brevoRes = await fetch('https://api.brevo.com/v3/contacts', {
        method: 'POST',
        headers: {
          'accept':       'application/json',
          'content-type': 'application/json',
          'api-key':      env.BREVO_API_KEY,
        },
        body: JSON.stringify({
          email,
          listIds:       [parseInt(env.BREVO_LIST_ID)],
          updateEnabled: true,           // update if contact already exists
          attributes: {
            SOURCE: 'aibuilderhub-newsletter',
          },
        }),
      });

      // 201 = created, 204 = updated (already exists)
      if (brevoRes.status === 201 || brevoRes.status === 204) {
        return corsResponse({ success: true }, 200, env.ALLOWED_ORIGIN);
      }

      const errData = await brevoRes.json();
      console.error('Brevo error:', errData);
      return corsResponse({ error: 'Subscription failed. Please try again.' }, 500, env.ALLOWED_ORIGIN);

    } catch (err) {
      console.error('Worker error:', err);
      return corsResponse({ error: 'Server error. Please try again.' }, 500, env.ALLOWED_ORIGIN);
    }
  },
};

function corsResponse(body, status, allowedOrigin) {
  const headers = {
    'Access-Control-Allow-Origin':  allowedOrigin || '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };

  return new Response(
    body !== null ? JSON.stringify(body) : null,
    { status, headers }
  );
}
