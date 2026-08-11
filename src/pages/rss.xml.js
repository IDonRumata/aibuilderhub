import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

/**
 * RSS feed for AIBuilderHub.
 *
 * pubDate is intentionally invisible in the site UI, but RSS readers need it
 * to order and de-duplicate items, so it is emitted here (same reasoning as
 * the sitemap and the BlogPosting structured data).
 */
export async function GET(context) {
  const posts = await getCollection('blog', ({ data }) => !data.draft);
  const sorted = posts.sort(
    (a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf()
  );

  return rss({
    title: 'AIBuilderHub',
    description:
      'Honest reviews and guides for AI app builders, vibe coding tools, and no-code platforms.',
    site: context.site,
    trailingSlash: false,
    items: sorted.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      categories: post.data.tags,
      link: `/blog/${post.slug}`,
    })),
    customData: '<language>en-us</language>',
  });
}
