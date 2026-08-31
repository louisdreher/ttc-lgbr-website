import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { PublicEvent, PublicEventCategory } from './public-event.models';

@Injectable({ providedIn: 'root' })
export class PublicEventApiService {
  private readonly http = inject(HttpClient);

  getCategories(): Observable<PublicEventCategory[]> {
    return this.http.get<PublicEventCategory[]>('/api/event-categories');
  }

  getEvents(
    startsFrom: string,
    startsUntil: string,
    categoryIds: number[],
  ): Observable<PublicEvent[]> {
    const params: Record<string, string | readonly string[]> = {
      starts_from: startsFrom,
      starts_until: startsUntil,
    };
    if (categoryIds.length > 0) params['category_id'] = categoryIds.map(String);
    return this.http.get<PublicEvent[]>('/api/events', { params });
  }
}
