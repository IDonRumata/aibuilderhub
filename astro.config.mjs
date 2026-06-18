import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
// import sitemap from '@astrojs/sitemap'; // TODO: re-enable after fixing v3.2.x bug

export default defineConfig({
  site: 'https://aibuilderhub.app',
  integrations: [
    tailwind(),
    // sitemap(),
  ],
});
