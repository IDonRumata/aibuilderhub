/**
 * One-shot setup for the newsletter subscribers table in NocoDB.
 *
 * Creates a `subscribers` table with the exact schema the subscribe worker
 * writes to, then prints the table id you need for the Cloudflare variables.
 *
 * Idempotent: if the table already exists it reports the id and changes nothing.
 *
 * Usage (PowerShell, from the project root):
 *
 *   $env:NOCODB_TOKEN="your-token-here"
 *   node scripts/setup-nocodb.mjs
 *
 * The token is read from the environment on purpose - never hardcode it in a
 * file that goes into git.
 *
 * Optional overrides:
 *   NOCODB_BASE_URL   default https://db.don-rumata.ru
 *   NOCODB_BASE_ID    default pq5rnkutmq37uz7
 *   TABLE_TITLE       default subscribers
 */

const BASE_URL = (process.env.NOCODB_BASE_URL || 'https://db.don-rumata.ru').replace(/\/+$/, '');
const BASE_ID = process.env.NOCODB_BASE_ID || 'pq5rnkutmq37uz7';
const TABLE_TITLE = process.env.TABLE_TITLE || 'subscribers';
const TOKEN = process.env.NOCODB_TOKEN;

if (!TOKEN) {
  console.error('\nNOCODB_TOKEN is not set.\n');
  console.error('PowerShell:');
  console.error('  $env:NOCODB_TOKEN="your-token-here"');
  console.error('  node scripts/setup-nocodb.mjs\n');
  process.exit(1);
}

const headers = {
  'xc-token': TOKEN,
  'content-type': 'application/json',
};

/**
 * Calls the NocoDB meta API and fails loudly with the response body, because
 * NocoDB error messages are the only useful signal when a schema is rejected.
 *
 * @param {string} path   Path after the origin, e.g. /api/v2/meta/bases/x/tables
 * @param {object} [init] Extra fetch options.
 * @returns {Promise<any>} Parsed JSON response.
 * @throws {Error} When the response status is not 2xx.
 */
async function api(path, init = {}) {
  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  const text = await res.text();

  if (!res.ok) {
    throw new Error(`${init.method || 'GET'} ${path} -> HTTP ${res.status}\n${text.slice(0, 600)}`);
  }
  return text ? JSON.parse(text) : null;
}

/**
 * Column definitions matching exactly what workers/subscribe.js sends.
 * Field titles are the JSON keys in the worker payload - do not rename one
 * without renaming the other.
 *
 * @param {boolean} useSelect Whether `status` is a SingleSelect or plain text.
 * @returns {object[]} NocoDB column definitions.
 */
function columns(useSelect) {
  const status = useSelect
    ? {
        title: 'status',
        column_name: 'status',
        uidt: 'SingleSelect',
        dtxp: "'pending','confirmed','unsubscribed'",
        colOptions: {
          options: [
            { title: 'pending', color: '#cfdffe' },
            { title: 'confirmed', color: '#d1f7c4' },
            { title: 'unsubscribed', color: '#ffdce5' },
          ],
        },
      }
    : { title: 'status', column_name: 'status', uidt: 'SingleLineText' };

  return [
    { title: 'email', column_name: 'email', uidt: 'Email', pv: true },
    status,
    { title: 'source_page', column_name: 'source_page', uidt: 'SingleLineText' },
    { title: 'country', column_name: 'country', uidt: 'SingleLineText' },
    { title: 'subscribed_at', column_name: 'subscribed_at', uidt: 'DateTime' },
  ];
}

async function main() {
  console.log(`\nNocoDB : ${BASE_URL}`);
  console.log(`Base   : ${BASE_ID}`);
  console.log(`Table  : ${TABLE_TITLE}\n`);

  // 1. Verify the token and that the base is reachable.
  process.stdout.write('Checking token and base access... ');
  const existing = await api(`/api/v2/meta/bases/${BASE_ID}/tables`);
  console.log('ok');

  const list = existing?.list || existing?.tables || [];
  const found = list.find(
    (t) => (t.title || '').toLowerCase() === TABLE_TITLE.toLowerCase()
  );

  if (found) {
    console.log(`\nTable "${TABLE_TITLE}" already exists. Nothing to create.`);
    report(found.id);
    return;
  }

  // 2. Create it. SingleSelect is nicer in the UI but the exact payload shape
  //    varies between NocoDB versions, so fall back to plain text rather than
  //    leaving you with no table at all.
  let table;
  try {
    process.stdout.write('Creating table (status as SingleSelect)... ');
    table = await api(`/api/v2/meta/bases/${BASE_ID}/tables`, {
      method: 'POST',
      body: JSON.stringify({
        title: TABLE_TITLE,
        table_name: TABLE_TITLE,
        columns: columns(true),
      }),
    });
    console.log('ok');
  } catch (err) {
    console.log('rejected');
    console.log('  NocoDB did not accept the SingleSelect column on this version.');
    console.log('  Retrying with status as plain text...');
    process.stdout.write('Creating table (status as SingleLineText)... ');
    table = await api(`/api/v2/meta/bases/${BASE_ID}/tables`, {
      method: 'POST',
      body: JSON.stringify({
        title: TABLE_TITLE,
        table_name: TABLE_TITLE,
        columns: columns(false),
      }),
    });
    console.log('ok');
    console.log('  Tip: change the "status" field type to Single Select in the UI');
    console.log('       if you want a dropdown. The worker does not care either way.');
  }

  report(table.id);
}

/**
 * Prints the follow-up steps with the real table id filled in.
 *
 * @param {string} tableId NocoDB table id.
 */
function report(tableId) {
  console.log('\n' + '='.repeat(64));
  console.log('  NOCODB_TABLE_ID =', tableId);
  console.log('='.repeat(64));
  console.log('\nNext: Cloudflare -> Workers & Pages -> subscribe worker');
  console.log('      -> Settings -> Variables and Secrets\n');
  console.log('  NOCODB_BASE_URL   (Text)    ', BASE_URL);
  console.log('  NOCODB_TABLE_ID   (Text)    ', tableId);
  console.log('  NOCODB_TOKEN      (Secret)   <your token>');
  console.log('\nThen deploy:  npx wrangler deploy workers/subscribe.js');
  console.log('\nRotate the token afterwards if it has been shared anywhere.\n');
}

main().catch((err) => {
  console.error('\nFAILED\n');
  console.error(err.message);
  console.error('\nCommon causes:');
  console.error('  - token expired or revoked');
  console.error('  - token lacks write access to this base');
  console.error('  - wrong NOCODB_BASE_ID (check the dashboard URL)');
  console.error('  - NocoDB unreachable from this machine\n');
  process.exit(1);
});
