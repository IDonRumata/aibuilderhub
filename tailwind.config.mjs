/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,ts,tsx}'],
  // "class" strategy: dark mode is toggled by adding class="dark" on <html>
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // All colors use CSS variables — light/dark switching happens in global.css
        bg:            'var(--color-bg)',
        surface:       'var(--color-surface)',
        'surface-2':   'var(--color-surface-2)',
        accent:        'var(--color-accent)',
        'accent-light':'var(--color-accent-light)',
        muted:         'var(--color-muted)',
        border:        'var(--color-border)',
        success:       'var(--color-success)',
        text:          'var(--color-text)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      typography: (theme) => ({
        DEFAULT: {
          css: {
            '--tw-prose-body':          'var(--color-prose-body)',
            '--tw-prose-headings':      'var(--color-text)',
            '--tw-prose-links':         'var(--color-accent-light)',
            '--tw-prose-bold':          'var(--color-text)',
            '--tw-prose-counters':      'var(--color-muted)',
            '--tw-prose-bullets':       'var(--color-muted)',
            '--tw-prose-hr':            'var(--color-border)',
            '--tw-prose-quotes':        'var(--color-muted)',
            '--tw-prose-quote-borders': 'var(--color-accent)',
            '--tw-prose-code':          'var(--color-accent-light)',
            '--tw-prose-pre-bg':        'var(--color-surface)',
            '--tw-prose-th-borders':    'var(--color-border)',
            '--tw-prose-td-borders':    'var(--color-border)',
          },
        },
      }),
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};
