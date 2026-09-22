import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { EditorialEventInput } from '../events/editorial-event.models';

export interface GalleryWrite {
  title: string;
  event_id: number | null;
  gallery_date: string | null;
  show_date: boolean;
  media_ids: number[];
  new_event: EditorialEventInput | null;
}
export interface CreatedGallery {
  id: number;
  cover_image_id: number | null;
  gallery_date: string;
  show_date: boolean;
}

export interface GallerySummary extends CreatedGallery {
  title: string;
  event_id: number | null;
  image_count: number;
}
export interface GalleryDetails extends GallerySummary {
  media_ids: number[];
  updated_at: string;
  created_by_user_id: number;
}
export interface GalleryUpdate {
  title: string;
  gallery_date: string;
  show_date: boolean;
  media_ids: number[];
  cover_image_id: number | null;
  updated_at: string;
}
export interface GalleryPage {
  items: GallerySummary[];
  total: number;
  offset: number;
  limit: number;
  years: number[];
}

export type GalleryEventGroup = 'other_events' | 'team_matches';

export interface GalleryOpportunity {
  event_id: number;
  title: string;
  starts_at: string;
  ends_at: string | null;
  team_match_id: number | null;
}

export interface GalleryOpportunityPage {
  items: GalleryOpportunity[];
  total: number;
  offset: number;
  limit: number;
}

@Injectable({ providedIn: 'root' })
export class GalleryApiService {
  private readonly http = inject(HttpClient);
  list(year: number | null = null, offset = 0) {
    return this.http.get<GalleryPage>('/api/admin/media/galleries', {
      params: { offset, limit: 20, ...(year === null ? {} : { year }) },
    });
  }
  get(id: number) {
    return this.http.get<GalleryDetails>(`/api/admin/media/galleries/${id}`);
  }
  byEvent(eventId: number) {
    return this.http.get<GalleryDetails | null>(`/api/admin/media/galleries/events/${eventId}`);
  }
  update(id: number, data: GalleryUpdate) {
    return this.http.put<void>(`/api/admin/media/galleries/${id}`, data);
  }
  create(data: GalleryWrite) {
    return this.http.post<CreatedGallery>('/api/admin/media/galleries', data);
  }

  opportunities(group: GalleryEventGroup, offset = 0) {
    return this.http.get<GalleryOpportunityPage>('/api/admin/media/galleries/opportunities', {
      params: { group, offset, limit: 20 },
    });
  }
}

export function galleryError(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 401) return 'Bitte melde dich erneut an.';
    if (error.status === 403)
      return 'Du darfst für diesen Termin keine Galerie anlegen. Ohne Redaktionsrechte benötigst du einen bearbeitbaren Bericht.';
    if (error.status === 409)
      return 'Die Galerie wurde inzwischen geändert oder für dieses Event bereits angelegt. Deine Eingaben bleiben erhalten. Bitte lade den aktuellen Stand neu.';
    if (typeof error.error?.detail === 'string') return error.error.detail;
    if (error.status === 422) return 'Bitte prüfe Titel, Datum und die Eventangaben.';
  }
  return 'Die Anfrage konnte nicht abgeschlossen werden. Bitte versuche es erneut.';
}
