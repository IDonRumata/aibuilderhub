/**
 * Single source of truth for author identity across the site: byline,
 * author box, About page, and the Person/BlogPosting structured data.
 *
 * Why a shared file: the LinkedIn/X URLs below start empty and get filled
 * in once confirmed. Every consumer (BaseLayout, PostLayout, about.astro)
 * imports from here, so filling in `sameAs` later is a one-file edit
 * instead of a search-and-replace across the whole site.
 */

export interface AuthorProfile {
  name: string;
  /** One-line role shown under the name in the author box. */
  role: string;
  /** Path under /public used for the avatar in the author box, About page, and Person schema. */
  photo: string;
  /** Short bio shown in the author box at the bottom of every post. */
  shortBio: string;
  /** Longer paragraphs for the About page, one string per paragraph. */
  longBio: string[];
  email: string;
  /**
   * Profile URLs for the Person schema's `sameAs` and the author box links.
   * Add entries here once confirmed — nothing else needs to change.
   */
  sameAs: { label: string; url: string }[];
}

export const AUTHOR: AuthorProfile = {
  name: 'Andrei Maroz',
  role: 'Solo builder behind AIBuilderHub',
  photo: '/images/author-andrei-maroz.jpg',
  shortBio:
    'I research, test, and write every review on this site myself, using the same AI tools I review to build the site itself.',
  longBio: [
    "I'm Andrei, and I'm the only person who works on AIBuilderHub. I test the tool, build something real with it, write the review, and ship the page - no ghostwriters, no outsourced \"content team.\"",
    "Outside of this site, I'm building a cybersecurity and compliance startup in the EU, solo, currently pre-launch. AIBuilderHub runs on the same playbook: pick a capable AI tool, move fast without a team, and be honest about what breaks along the way. That's the lens every review here is written through - not \"is this tool impressive in a demo,\" but \"would I actually build my own product on this.\"",
    "Most review sites in this space are written by people who've never shipped anything with the tools they're ranking. I'd rather show my work: what I built, what it cost, what broke, and whether I'd use it again.",
  ],
  email: 'hello@aibuilderhub.app',
  sameAs: [
    // Add once confirmed, e.g.:
    // { label: 'LinkedIn', url: 'https://www.linkedin.com/in/...' },
  ],
};
