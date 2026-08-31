export type PublicEventStatus = 'PLANNED' | 'COMPLETED' | 'CANCELLED' | 'POSTPONED';

export interface PublicEventCategory {
  id: number;
  name: string;
  slug: string;
}

export interface PublicEvent {
  id: number;
  title: string;
  starts_at: string;
  ends_at: string | null;
  is_all_day: boolean;
  category_id: number;
  status: PublicEventStatus;
  location: string | null;
  description: string | null;
}
