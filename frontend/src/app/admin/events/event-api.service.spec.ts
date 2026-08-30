import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { EventApiService } from './event-api.service';
import { EventWrite } from './event.models';

describe('EventApiService', () => {
  let service: EventApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(EventApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads events and categories from the admin API', () => {
    service.getEvents().subscribe();
    http.expectOne('/api/admin/events').flush([]);

    service.getCategories().subscribe();
    http.expectOne('/api/admin/event-categories').flush([]);
  });

  it('creates and updates events', () => {
    const payload: EventWrite = {
      title: 'Vereinsabend',
      starts_at: '2026-09-01T18:00:00.000Z',
      ends_at: null,
      is_all_day: false,
      category_id: 1,
      status: 'PLANNED',
      visibility: 'PUBLIC',
      report_expected: false,
      location: null,
      description: null,
    };

    service.createEvent(payload).subscribe();
    const create = http.expectOne('/api/admin/events');
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual(payload);
    create.flush({});

    service.updateEvent(7, { description: 'Neu' }).subscribe();
    const update = http.expectOne('/api/admin/events/7');
    expect(update.request.method).toBe('PATCH');
    expect(update.request.body).toEqual({ description: 'Neu' });
    update.flush({});
  });

  it('deletes events and updates visibility in bulk', () => {
    service.deleteEvent(7).subscribe();
    const singleDelete = http.expectOne('/api/admin/events/7');
    expect(singleDelete.request.method).toBe('DELETE');
    singleDelete.flush(null);

    service.deleteEvents([2, 3]).subscribe();
    const bulkDelete = http.expectOne('/api/admin/events/bulk-delete');
    expect(bulkDelete.request.method).toBe('POST');
    expect(bulkDelete.request.body).toEqual({ event_ids: [2, 3] });
    bulkDelete.flush(null);

    service.updateEventsVisibility([2, 3], 'HIDDEN').subscribe();
    const visibility = http.expectOne('/api/admin/events/bulk/visibility');
    expect(visibility.request.method).toBe('PATCH');
    expect(visibility.request.body).toEqual({ event_ids: [2, 3], visibility: 'HIDDEN' });
    visibility.flush([]);
  });
});
