export type EventStatus = 'PLANNED' | 'COMPLETED' | 'CANCELLED' | 'POSTPONED';
export type EventVisibility = 'PUBLIC' | 'MEMBERS_ONLY' | 'HIDDEN';

export interface EventCategory {
  id: number;
  name: string;
  slug: string;
  default_report_expected: boolean;
  is_active: boolean;
  sort_order: number;
}

export interface EventCategoryCreate {
  name: string;
  slug: string;
  default_report_expected: boolean;
  is_active: boolean;
  sort_order: number;
}

export interface AdminEvent {
  id: number;
  title: string;
  starts_at: string;
  ends_at: string | null;
  is_all_day: boolean;
  category_id: number;
  team_match_id: number | null;
  created_by_user_id: number | null;
  created_by_name: string | null;
  status: EventStatus;
  visibility: EventVisibility;
  report_expected: boolean;
  location: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface EventWrite {
  title: string;
  starts_at: string;
  ends_at: string | null;
  is_all_day: boolean;
  category_id: number;
  status: EventStatus;
  visibility: EventVisibility;
  report_expected: boolean;
  location: string | null;
  description: string | null;
}

export type EventUpdate = Partial<EventWrite>;
