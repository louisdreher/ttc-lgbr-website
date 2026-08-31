import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { PublicEventApiService } from './public-event-api.service';

describe('PublicEventApiService', () => {
  let service: PublicEventApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PublicEventApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads public categories', () => {
    service.getCategories().subscribe();

    const request = http.expectOne('/api/event-categories');
    expect(request.request.method).toBe('GET');
    request.flush([]);
  });

  it('loads events for a date range and categories', () => {
    service.getEvents('2026-08-31T22:00:00.000Z', '2027-08-31T21:59:59.999Z', [2, 4]).subscribe();

    const request = http.expectOne(
      (candidate) =>
        candidate.url === '/api/events' &&
        candidate.params.get('starts_from') === '2026-08-31T22:00:00.000Z' &&
        candidate.params.get('starts_until') === '2027-08-31T21:59:59.999Z' &&
        candidate.params.getAll('category_id')?.join(',') === '2,4',
    );
    expect(request.request.method).toBe('GET');
    request.flush([]);
  });
});
