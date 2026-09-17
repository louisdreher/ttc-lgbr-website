import { Article } from './article.models';
export function articleFixture(changes: Partial<Article> = {}): Article {
  return {
    id: 1,
    author_id: 7,
    author_name: 'Anna',
    title: 'Unser Vereinsfest',
    slug: 'vereinsfest',
    teaser: 'Ein schöner Tag.',
    content: 'Der Bericht zum Vereinsfest.',
    article_type: 'EVENT_REPORT',
    visibility: 'PUBLIC',
    status: 'DRAFT',
    event_id: null,
    published_at: null,
    updated_at: '2026-09-17T12:00:00Z',
    tags: ['verein'],
    cover_image_id: null,
    system_authored: false,
    generated: false,
    allowed_actions: ['save', 'submit'],
    ...changes,
  };
}
