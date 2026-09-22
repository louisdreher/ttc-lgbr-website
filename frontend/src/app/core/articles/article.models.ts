import { EditorialEventInput } from '../events/editorial-event.models';

export type ArticleType =
  'NEWS' | 'MATCH_REPORT' | 'EVENT_REPORT' | 'ANNUAL_REPORT' | 'ANNOUNCEMENT';
export type ArticleStatus = 'DRAFT' | 'IN_REVIEW' | 'PUBLISHED' | 'ARCHIVED';
export type ArticleVisibility = 'PUBLIC' | 'MEMBERS_ONLY' | 'HIDDEN';
export type ArticleAction =
  'save' | 'submit' | 'publish' | 'visibility' | 'archive' | 'restore' | 'delete';
export interface PublicArticle {
  id: number;
  author_name: string;
  title: string;
  slug: string;
  teaser: string;
  content: string;
  article_type: ArticleType;
  published_at: string | null;
  tags: string[];
  cover_image_id: number | null;
}
export interface Article extends PublicArticle {
  author_id: number;
  visibility: ArticleVisibility;
  status: ArticleStatus;
  event_id: number | null;
  updated_at: string;
  system_authored: boolean;
  generated: boolean;
  allowed_actions: ArticleAction[];
}
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
export interface Opportunity {
  event_id: number;
  title: string;
  starts_at: string;
  team_match_id: number | null;
  article_id: number | null;
}
export interface Opportunities {
  team_matches: Opportunity[];
  other_events: Opportunity[];
  total: number;
  offset: number;
  limit: number;
}
export type OpportunityGroup = 'team_matches' | 'other_events';
export interface PreparedArticle {
  article_id: number | null;
  event_id: number;
  title: string;
  slug: string;
  teaser: string;
  content: string;
  article_type: ArticleType;
  visibility: ArticleVisibility;
  tags: string[];
  cover_image_id: number | null;
  editable_fields: string[];
}
export interface ArticleWrite {
  title: string;
  slug: string;
  teaser: string;
  content: string;
  article_type: ArticleType;
  visibility: ArticleVisibility;
  event_id: number | null;
  tags: string[];
  cover_image_id: number | null;
  new_event: EditorialEventInput | null;
}
export const ARTICLE_TYPES: { value: ArticleType; label: string }[] = [
  { value: 'NEWS', label: 'Nachricht' },
  { value: 'MATCH_REPORT', label: 'Spielbericht' },
  { value: 'EVENT_REPORT', label: 'Veranstaltungsbericht' },
  { value: 'ANNUAL_REPORT', label: 'Jahresbericht' },
  { value: 'ANNOUNCEMENT', label: 'Ankündigung' },
];
export const STATUS_LABELS: Record<ArticleStatus, string> = {
  DRAFT: 'Entwurf',
  IN_REVIEW: 'Eingereicht',
  PUBLISHED: 'Veröffentlicht',
  ARCHIVED: 'Archiviert',
};
export function articleTypeLabel(type: ArticleType): string {
  return ARTICLE_TYPES.find((item) => item.value === type)?.label ?? type;
}
