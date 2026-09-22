import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import axe from 'axe-core';
import { GalleryList } from './list';

describe('Gallery overview', () => {
  function setup() {
    TestBed.configureTestingModule({
      imports: [GalleryList],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(GalleryList);
    const http = TestBed.inject(HttpTestingController);
    const response = {
      items: [
        {
          id: 3,
          title: 'Archiv',
          event_id: null,
          gallery_date: '2007-06-16',
          show_date: false,
          cover_image_id: null,
          image_count: 2,
        },
      ],
      total: 40,
      offset: 0,
      limit: 20,
      years: [2026, 2007],
    };
    http.expectOne((r) => r.url === '/api/admin/media/galleries').flush(response);
    fixture.detectChanges();
    return { fixture, http, response, component: fixture.componentInstance };
  }
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('lists saved galleries and sends year and offset for pagination', () => {
    const { fixture, component, http, response } = setup();
    expect(fixture.nativeElement.querySelector('a[href="/admin/galleries/3/edit"]')).not.toBeNull();
    const select = fixture.nativeElement.querySelector('select');
    select.value = '2007';
    select.dispatchEvent(new Event('change'));
    const request = http.expectOne((r) => r.params.get('year') === '2007');
    expect(request.request.params.get('offset')).toBe('0');
    request.flush(response);
    component.load(20);
    const next = http.expectOne((r) => r.params.get('offset') === '20');
    expect(next.request.params.get('year')).toBe('2007');
    next.flush({ ...response, offset: 20 });
  });

  it('shows retry after load errors and has labelled controls', async () => {
    const { fixture, component, http } = setup();
    component.load();
    http
      .expectOne((r) => r.url === '/api/admin/media/galleries')
      .flush({}, { status: 500, statusText: 'Failed' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=alert]')).not.toBeNull();
    const result = await axe.run(fixture.nativeElement, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });
});
