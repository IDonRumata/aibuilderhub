# AIBuilderHub 🤖

[![Astro](https://img.shields.io/badge/Astro-4.x-FF5D01?logo=astro&logoColor=white)](https://astro.build/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.x-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Cloudflare Pages](https://img.shields.io/badge/Hosted%20on-Cloudflare%20Pages-F38020?logo=cloudflare&logoColor=white)](https://pages.cloudflare.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Affiliate content site — honest reviews and comparisons of AI app builders, vibe coding tools, and no-code platforms for solopreneurs. Built with Astro for maximum performance and SEO.

**Niche:** 🏗️ AI Builders | 🔬 Vibe Coding | ⚡ No-Code Tools

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| ⚡ **Static-first** | Astro generates pure HTML — Core Web Vitals 95+ out of the box |
| 🎨 **Dark theme** | Indigo-accented design, mobile-first, zero JavaScript by default |
| 📝 **Content Collections** | Type-safe Markdown posts with Zod schema validation |
| 🗺️ **Auto Sitemap** | `@astrojs/sitemap` generates sitemap on every build |
| 🔗 **Affiliate-ready** | Tool cards with `rel="nofollow sponsored"`, disclosure page included |
| 📬 **Newsletter CTA** | Email capture on homepage and at end of every article |
| 🔍 **SEO-complete** | Canonical URLs, Open Graph, Twitter cards, structured meta on all pages |

---

## 🏗️ Architecture

```
Browser Request
      │
      ▼
┌─────────────────────┐
│  Cloudflare CDN     │  (free plan, unlimited bandwidth)
│  Global edge cache  │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│ Cloudflare Pages                             │
│ • Serves pre-built static HTML               │
│ • Auto-deploys on every git push to main     │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│ Astro Build (CI/CD)                          │
│ • Reads /src/content/blog/*.md               │
│ • Validates frontmatter via Zod schema       │
│ • Generates HTML + sitemap + robots.txt      │
└──────────────────────────────────────────────┘

Content pipeline:
  Markdown (.md) → Astro Content Collections → Static HTML
```

---

## 🛠️ Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| **Framework** | [Astro 4.x](https://astro.build) | Zero JS by default, best static site SEO |
| **Styling** | [Tailwind CSS 3.x](https://tailwindcss.com) | Utility-first, no CSS files to manage |
| **Typography** | [@tailwindcss/typography](https://tailwindcss.com/docs/typography-plugin) | Prose styles for blog posts |
| **Sitemap** | @astrojs/sitemap | Auto-generated on build |
| **Hosting** | Cloudflare Pages | Free, unlimited bandwidth, global CDN |
| **Font** | Inter via Google Fonts | System UI fallback for performance |

**Cost:** ~$11/year (domain only). Hosting, CDN, deployment — all free.

---

## 📁 Project Structure

```
aibuilderhub/
├── public/
│   ├── favicon.svg             # SVG favicon (indigo brand color)
│   └── robots.txt              # Allow all + sitemap reference
│
├── src/
│   ├── styles/
│   │   └── global.css          # Tailwind directives + custom utilities
│   │
│   ├── layouts/
│   │   ├── BaseLayout.astro    # HTML shell: meta, OG, fonts, header+footer
│   │   └── PostLayout.astro    # Blog post layout: affiliate notice, meta bar, CTA
│   │
│   ├── components/
│   │   ├── Header.astro        # Sticky nav with active link detection
│   │   ├── Footer.astro        # Links + affiliate disclosure line
│   │   ├── PostCard.astro      # Blog post preview card (grid)
│   │   └── ToolCard.astro      # Tool card with rating, badge, affiliate button
│   │
│   ├── content/
│   │   ├── config.ts           # Zod schema: title, description, pubDate, tags, draft
│   │   └── blog/
│   │       ├── lovable-vs-bolt-2026.md
│   │       └── vibe-coding-beginners-guide.md
│   │
│   └── pages/
│       ├── index.astro         # Homepage: hero + tools + posts + trust signals
│       ├── about.astro         # About the site and editorial policy
│       ├── disclosure.astro    # FTC/EU affiliate disclosure (legally required)
│       ├── privacy.astro       # GDPR-compliant privacy policy
│       ├── blog/
│       │   ├── index.astro     # All posts grid
│       │   └── [...slug].astro # Dynamic post pages
│       └── tools/
│           └── index.astro     # Tools directory with comparison cards
│
├── astro.config.mjs            # Site URL, integrations (tailwind + sitemap)
├── tailwind.config.mjs         # Theme: colors, fonts, typography config
├── tsconfig.json               # TypeScript paths
├── package.json                # Dependencies
└── .gitignore
```

---

## 🚀 Quick Start

### 1️⃣ Prerequisites

- [Node.js 18+](https://nodejs.org/) installed
- Git

### 2️⃣ Clone & Install

```bash
git clone https://github.com/IDonRumata/aibuilderhub.git
cd aibuilderhub
npm install
```

### 3️⃣ Run locally

```bash
npm run dev
```

Open [http://localhost:4321](http://localhost:4321)

### 4️⃣ Build for production

```bash
npm run build
npm run preview  # Preview the production build locally
```

---

## ✍️ Adding Content

All content lives in `/src/content/blog/` as Markdown files.

### Post frontmatter schema

```markdown
---
title: "Your Post Title Here"
description: "One sentence description for SEO meta and post cards. Keep under 160 chars."
pubDate: "2026-06-15"
updatedDate: "2026-06-20"    # optional — shows "Updated" badge on post
tags: ["comparison", "lovable", "vibe-coding"]
author: "AIBuilderHub"
draft: false                  # set true to hide from production
---

Your content here in standard Markdown...
```

### Available tags

`comparison` · `guide` · `tutorial` · `review` · `beginners` · `vibe-coding` · `no-code` · `lovable` · `bolt` · `cursor` · `framer` · `v0`

### Adding affiliate links in posts

Always use `rel="nofollow sponsored noopener"` on affiliate links:

```markdown
[Try Lovable →](https://lovable.dev){rel="nofollow sponsored noopener"}
```

Or just write the URL — the PostLayout already includes a disclosure notice at the top of every article.

---

## 🎨 Design Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `bg` | `#0A0A0B` | Page background |
| `surface` | `#111113` | Cards, code blocks |
| `accent` | `#6366F1` | Primary CTA, links, brand color |
| `accent-light` | `#818CF8` | Hover states, in-text links |
| `muted` | `#94A3B8` | Secondary text, meta info |
| `border` | `#27272A` | Card borders, dividers |
| `success` | `#10B981` | "Updated" badges, positive indicators |

Font: **Inter** (Google Fonts, preconnect loaded in BaseLayout)

---

## 🌐 Deployment (Cloudflare Pages)

Deploys automatically on every push to `main`.

### Manual setup (first time)

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com) → **Workers & Pages** → **Create** → **Pages**
2. Connect GitHub → select `aibuilderhub` repo
3. Build settings:
   - Framework preset: **Astro**
   - Build command: `npm run build`
   - Build output directory: `dist`
4. Click **Save and Deploy**

### Custom domain

In Cloudflare Pages → Custom domains → add `aibuilderhub.app`  
Then in OVHcloud DNS: add a CNAME pointing to your `*.pages.dev` URL.

### Environment variables (if needed)

Set in Cloudflare Pages → Settings → Environment Variables. Currently none required.

---

## 💰 Monetization Setup

### Affiliate programs to register

| Tool | Program URL | Commission |
|------|-------------|------------|
| Lovable | lovable.dev/affiliates | ~30% recurring |
| Cursor | cursor.sh/affiliates | ~20% recurring |
| Framer | framer.com/affiliates | 30% recurring |
| Webflow | webflow.com/affiliates | 25% recurring |
| Replit | replit.com/affiliates | 25% recurring |

After getting affiliate links, replace placeholder `href` values in:
- `src/pages/index.astro` (featured tools section)
- `src/pages/tools/index.astro` (full tools directory)

### Newsletter (Brevo)

1. Create free account at [brevo.com](https://brevo.com)
2. Create a subscription form → get the form action URL
3. Replace `action="#"` in the newsletter forms with your Brevo form URL

### Display ads (when ready)

- **0–10k sessions/mo:** Google AdSense
- **10k–50k sessions/mo:** Ezoic
- **50k+ sessions/mo:** Mediavine (apply) or Raptive

---

## 🔒 Legal Pages

All required legal pages are included and pre-filled:

| Page | URL | Status |
|------|-----|--------|
| Affiliate Disclosure | `/disclosure` | ✅ FTC + EU compliant |
| Privacy Policy | `/privacy` | ✅ GDPR compliant |
| About | `/about` | ✅ Editorial policy stated |

**Before launch:** Update contact email `hello@aibuilderhub.app` in disclosure and privacy pages once email is set up.

---

## 📊 Analytics Setup

1. [Google Search Console](https://search.google.com/search-console) — add property for `aibuilderhub.app`, verify via DNS TXT record in Cloudflare
2. [Google Analytics 4](https://analytics.google.com) — create property, add GA4 script to `BaseLayout.astro` before `</head>`
3. [Ahrefs Webmaster Tools](https://ahrefs.com/webmaster-tools) — free after domain verification in GSC

---

## 🔧 Troubleshooting

### `npm` not recognized / execution policy error (Windows)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then retry `npm install`.

### Build fails: "Content collection not found"

Ensure `/src/content/config.ts` exists and exports a `blog` collection. Run `npm run dev` once to let Astro generate type definitions in `.astro/`.

### Sitemap not generated

Ensure `site: 'https://aibuilderhub.app'` is set in `astro.config.mjs` — sitemap requires an absolute site URL.

---

## 📄 License

MIT © 2026 IDonRumata

---

**Built with Astro ⚡ · Deployed on Cloudflare · Domain: aibuilderhub.app**
