import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const blog = defineCollection({
  loader: glob({ pattern: '**/[^_]*.md', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    // pubDate is never rendered in the UI. It exists for sorting, the sitemap,
    // the RSS feed and BlogPosting structured data only.
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    author: z.string().default('AIBuilderHub'),
    draft: z.boolean().default(false),
  }),
});

export const collections = { blog };
