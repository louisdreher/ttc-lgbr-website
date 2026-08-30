import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  AdminEvent,
  EventCategory,
  EventCategoryCreate,
  EventUpdate,
  EventWrite,
} from './event.models';

@Injectable({ providedIn: 'root' })
export class EventApiService {
  private readonly http = inject(HttpClient);
  private readonly eventsUrl = '/api/admin/events';
  private readonly categoriesUrl = '/api/admin/event-categories';
  readonly eventsChanged = signal(0);
  readonly categoryCreated = signal<EventCategory | null>(null);

  getEvents(year?: number, categoryIds?: number[]): Observable<AdminEvent[]> {
    const params: Record<string, string | readonly string[]> = {};
    if (year !== undefined) params['year'] = String(year);
    if (categoryIds !== undefined) params['category_id'] = categoryIds.map(String);
    return this.http.get<AdminEvent[]>(this.eventsUrl, { params });
  }

  getEventYears(): Observable<number[]> {
    return this.http.get<number[]>('/api/admin/event-years');
  }

  getEvent(id: number): Observable<AdminEvent> {
    return this.http.get<AdminEvent>(`${this.eventsUrl}/${id}`);
  }

  getCategories(): Observable<EventCategory[]> {
    return this.http.get<EventCategory[]>(this.categoriesUrl);
  }

  createCategory(category: EventCategoryCreate): Observable<EventCategory> {
    return this.http.post<EventCategory>(this.categoriesUrl, category);
  }

  createEvent(event: EventWrite): Observable<AdminEvent> {
    return this.http.post<AdminEvent>(this.eventsUrl, event);
  }

  updateEvent(id: number, changes: EventUpdate): Observable<AdminEvent> {
    return this.http.patch<AdminEvent>(`${this.eventsUrl}/${id}`, changes);
  }

  deleteEvent(id: number): Observable<void> {
    return this.http.delete<void>(`${this.eventsUrl}/${id}`);
  }

  deleteEvents(eventIds: number[]): Observable<void> {
    return this.http.post<void>(`${this.eventsUrl}/bulk-delete`, { event_ids: eventIds });
  }

  updateEventsVisibility(
    eventIds: number[],
    visibility: EventWrite['visibility'],
  ): Observable<AdminEvent[]> {
    return this.http.patch<AdminEvent[]>(`${this.eventsUrl}/bulk/visibility`, {
      event_ids: eventIds,
      visibility,
    });
  }

  notifyEventChanged(): void {
    this.eventsChanged.update((value) => value + 1);
  }
}
