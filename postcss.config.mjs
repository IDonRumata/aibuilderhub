/**
 * Tailwind is wired through PostCSS directly rather than @astrojs/tailwind,
 * which was archived and never gained Astro 5+ peer support. Keeping Tailwind
 * on v3 this way avoids the Tailwind 4 CSS-first config rewrite.
 */
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
