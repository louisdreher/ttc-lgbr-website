import { provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import axe from 'axe-core';
import { AdminGalleryCreate } from './create';
import { AuthService } from '../../core/auth/auth.service';

describe('Gallery event selection', () => {
  function setup(editor = true) {
    TestBed.configureTestingModule({
      imports: [AdminGalleryCreate],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { hasAnyRole: () => editor } },
      ],
    });
    const fixture = TestBed.createComponent(AdminGalleryCreate);
    const http = TestBed.inject(HttpTestingController);
    const request = (group: string) =>
      http.expectOne(
        (r) =>
          r.url === '/api/admin/media/galleries/opportunities' && r.params.get('group') === group,
      );
    const page = (offset = 0, total = 40) => ({
      items: [
        {
          event_id: offset + 1,
          title: 'Vereinsfest',
          starts_at: '2026-09-17T12:00:00Z',
          ends_at: null,
          team_match_id: null,
        },
      ],
      total,
      offset,
      limit: 20,
    });
    return { fixture, http, request, page, component: fixture.componentInstance };
  }

  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('shows events first and paginates each group independently', () => {
    const { fixture, component, request, page, http } = setup();
    request('other_events').flush(page());
    request('team_matches').flush(page());
    fixture.detectChanges();
    const headings = [...fixture.nativeElement.querySelectorAll('h2')].map(
      (h: HTMLElement) => h.textContent,
    );
    expect(headings).toEqual(['Neue Galerie', 'Veranstaltungen', 'Mannschaftsspiele']);
    component.load('other_events', 20);
    const next = request('other_events');
    expect(next.request.params.get('offset')).toBe('20');
    expect(next.request.params.get('limit')).toBe('20');
    http.expectNone((r) => r.params.get('group') === 'team_matches');
    next.flush(page(20));
    expect(component.groups[0].page()?.offset).toBe(20);
    expect(component.groups[1].page()?.offset).toBe(0);
  });

  it('retries the failed requested page without discarding the other list', () => {
    const { component, request, page } = setup();
    request('other_events').flush(page());
    request('team_matches').flush(page());
    component.load('other_events', 20);
    request('other_events').flush({}, { status: 500, statusText: 'Error' });
    expect(component.groups[0].error()).toContain('erneut');
    expect(component.groups[1].error()).toBe('');
    component.load('other_events');
    const retry = request('other_events');
    expect(retry.request.params.get('offset')).toBe('20');
    retry.flush(page(20));
    expect(component.groups[0].error()).toBe('');
  });

  it('returns to the last available page when a gallery removes the last item', () => {
    const { component, request, page } = setup();
    request('other_events').flush(page());
    request('team_matches').flush(page());
    component.load('other_events', 20);
    request('other_events').flush({ items: [], total: 20, offset: 20, limit: 20 });
    const back = request('other_events');
    expect(back.request.params.get('offset')).toBe('0');
    back.flush(page(0, 20));
  });

  it('shows empty lists and hides standalone creation from writers', async () => {
    const { fixture, request } = setup(false);
    for (const key of ['other_events', 'team_matches']) {
      request(key).flush({ items: [], total: 0, offset: 0, limit: 20 });
    }
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.primary')).toBeNull();
    expect(
      [...fixture.nativeElement.querySelectorAll('nav button')].every(
        (button) => (button as HTMLButtonElement).disabled,
      ),
    ).toBe(true);
    const result = await axe.run(fixture.nativeElement, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });
});
