import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Tailwind is applied via postcss.config.mjs — see the note there.
export default defineConfig({
  site: 'https://aibuilderhub.app',
  integrations: [
    sitemap({
      // The newsletter confirmation page is a thin utility page reached only
      // from the double opt-in email. It is marked noindex, so keep it out of
      // the sitemap too rather than sending Google mixed signals.
      filter: (page) => !page.includes('/newsletter/confirmed'),
    }),
  ],
});
