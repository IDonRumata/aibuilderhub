import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Tailwind is applied via postcss.config.mjs — see the note there.
export default defineConfig({
  site: 'https://aibuilderhub.app',
  integrations: [sitemap()],
});
