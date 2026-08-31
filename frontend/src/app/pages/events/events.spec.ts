import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PublicEvents } from './events';

describe('PublicEvents', () => {
  let fixture: ComponentFixture<PublicEvents>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PublicEvents],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(PublicEvents);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('loads categories followed by events', () => {
    http.expectOne('/api/event-categories').flush([
      {
        id: 2,
        name: 'Veranstaltung',
        slug: 'veranstaltung',
      },
    ]);

    const eventsRequest = http.expectOne((request) => request.url === '/api/events');
    expect(eventsRequest.request.params.getAll('category_id')).toEqual(['2']);
    eventsRequest.flush([]);

    expect(fixture.componentInstance.loading()).toBe(false);
  });

  it('continues multi-day events in the following calendar week', () => {
    http
      .expectOne('/api/event-categories')
      .flush([{ id: 2, name: 'Veranstaltung', slug: 'veranstaltung' }]);
    http
      .expectOne((request) => request.url === '/api/events')
      .flush([
        {
          id: 7,
          title: 'Vereinsfahrt',
          starts_at: '2026-09-04T00:00:00Z',
          ends_at: '2026-09-07T00:00:00Z',
          is_all_day: true,
          category_id: 2,
          status: 'PLANNED',
          location: null,
          description: null,
        },
      ]);

    fixture.componentInstance.calendarDate.set(new Date(2026, 8, 1));
    const segments = fixture.componentInstance.calendarWeeks().flatMap((week) => week.segments);

    expect(segments.map((segment) => segment.startColumn)).toEqual([5, 1]);
    expect(segments.map((segment) => segment.span)).toEqual([3, 1]);
  });
});
