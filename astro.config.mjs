import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const BLOG_DIR = resolve(here, 'src/content/blog');

/**
 * Reads pubDate / updatedDate straight out of the markdown frontmatter so the
 * sitemap can carry a real `lastmod`. Google treats lastmod as a crawl hint,
 * but only while it believes the value - so dates are only emitted for pages
 * where a genuine one exists. Static pages like /about and /privacy get none
 * rather than a fabricated build timestamp.
 *
 * A regex is enough here instead of a frontmatter parser: the date lines are
 * machine-written by this repo and always take the form `pubDate: 2026-08-11`.
 *
 * @returns {{ byPath: Map<string, string>, newest: string | null }}
 *   byPath maps a site path to an ISO date; newest is the most recent post date.
 */
function readPostDates() {
  const byPath = new Map();
  let newest = null;

  for (const file of readdirSync(BLOG_DIR)) {
    if (!file.endsWith('.md') && !file.endsWith('.mdx')) continue;

    const raw = readFileSync(resolve(BLOG_DIR, file), 'utf8');
    const frontmatter = raw.split(/^---\s*$/m)[1] ?? '';

    // A draft is not published, so it never reaches the sitemap.
    if (/^draft:\s*true\s*$/m.test(frontmatter)) continue;

    // Quote style varies across the posts - some use "…", some '…', some none.
    const pub = frontmatter.match(/^pubDate:\s*['"]?(\d{4}-\d{2}-\d{2})/m)?.[1];
    const updated = frontmatter.match(/^updatedDate:\s*['"]?(\d{4}-\d{2}-\d{2})/m)?.[1];
    const date = updated || pub;
    if (!date) continue;

    const slug = file.replace(/\.mdx?$/, '');
    byPath.set(`/blog/${slug}/`, date);

    if (!newest || date > newest) newest = date;
  }

  return { byPath, newest };
}

const { byPath: postDates, newest: newestPost } = readPostDates();

// The home page and the blog index both list the latest posts, so their real
// last-modified date is the date of the most recent post.
const indexPages = new Set(['/', '/blog/']);

export default defineConfig({
  site: 'https://aibuilderhub.app',
  integrations: [
    sitemap({
      // The newsletter confirmation page is a thin utility page reached only
      // from the double opt-in email. It is marked noindex, so keep it out of
      // the sitemap too rather than sending Google mixed signals.
      filter: (page) => !page.includes('/newsletter/confirmed'),

      serialize(item) {
        const path = new URL(item.url).pathname;

        const date = indexPages.has(path) ? newestPost : postDates.get(path);
        if (date) item.lastmod = new Date(`${date}T00:00:00Z`).toISOString();

        return item;
      },
    }),
  ],
});
