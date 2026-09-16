import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { vi } from 'vitest';
import { MyttMatches } from './matches';
import { MatchReload, SyncMatch, SyncMatchOverview } from './mytt.models';

const game: SyncMatch = {
  id: 5514, team_id: 798, team_name: 'TTC VI', opponent_name: 'KSG Hetschbach', is_home: true,
  scheduled_at: '2026-09-12T11:30:00Z', is_completed: true, details_imported_at: null,
  reload: null, can_reload: true, reload_blocked_reason: null,
};
const request: MatchReload = {
  team_match_id: game.id, status: 'requested', requested_at: '2026-09-16T18:00:00Z',
  started_at: null, finished_at: null, last_error: null,
};
const overview = (): SyncMatchOverview => ({ imported: [], missing_details: [{ ...game }], upcoming: [] });

describe('MyttMatches', () => {
  let fixture: ComponentFixture<MyttMatches>;
  let component: MyttMatches;
  let http: HttpTestingController;
  const url = '/api/admin/mytt/matches';
  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ imports: [MyttMatches], providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(MyttMatches);
    component = fixture.componentInstance;
  });
  afterEach(() => { fixture.destroy(); http.verify(); vi.useRealTimers(); });
  function load(value = overview()) {
    http.expectOne(url).flush(value);
    fixture.detectChanges();
  }

  it('renders all groups and preserves collapsed state across refreshes', () => {
    const value = overview();
    value.imported = [{ ...game, id: 2, details_imported_at: '2026-09-16T17:00:00Z', can_reload: false }];
    value.upcoming = [{ ...game, id: 3, is_home: false, is_completed: false, scheduled_at: '2026-09-20T17:00:00Z', can_reload: false }];
    load(value);
    const sections = fixture.nativeElement.querySelectorAll('details') as NodeListOf<HTMLDetailsElement>;
    expect(sections.length).toBe(3);
    expect(sections[0].open).toBe(true);
    expect(sections[2].open).toBe(false);
    expect(fixture.nativeElement.textContent).toContain('Auswärtsspiel');
    sections[0].open = false;
    component.refresh();
    http.expectOne(url).flush(value);
    fixture.detectChanges();
    expect(sections[0].open).toBe(false);
  });

  it('handles loading, failed reads and recovery without discarding prior data', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Spiele werden geladen');
    http.expectOne(url).flush({}, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Spiele erneut laden');
    component.refresh();
    load();
    component.refresh();
    http.expectOne(url).flush({}, { status: 503, statusText: 'Unavailable' });
    expect(component.overview()?.missing_details.length).toBe(1);
    expect(component.error()).toContain('veraltet');
    component.refresh();
    load({ imported: [], missing_details: [], upcoming: [] });
    expect(component.error()).toBe('');
    expect(fixture.nativeElement.textContent).toContain('Keine Spiele');
  });

  it('accepts 202 without marking the game imported and cancels older reads', () => {
    load();
    component.refresh();
    const staleRead = http.expectOne(url);
    const button = fixture.nativeElement.querySelector('tbody button') as HTMLButtonElement;
    button.click();
    component.reload(game);
    fixture.detectChanges();
    expect(button.disabled).toBe(true);
    const post = http.expectOne(`${url}/${game.id}/reload`);
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toBeNull();
    post.flush(request, { status: 202, statusText: 'Accepted' });
    expect(staleRead.cancelled).toBe(true);
    expect(component.overview()?.missing_details[0].details_imported_at).toBeNull();
    expect(component.state(component.overview()!.missing_details[0])).toBe('Angefordert');
    const value = overview();
    value.missing_details[0] = { ...game, reload: request, can_reload: false };
    load(value);
  });

  it('polls running and completed states and stops after destruction', () => {
    load();
    vi.advanceTimersByTime(15_000);
    const value = overview();
    value.missing_details[0] = { ...game, reload: { ...request, status: 'running' }, can_reload: false };
    load(value);
    expect(component.state(value.missing_details[0])).toBe('Laufstatus unklar');
    fixture.componentRef.setInput('uncertain', false);
    expect(component.state(value.missing_details[0])).toBe('Läuft');
    vi.advanceTimersByTime(15_000);
    load({ missing_details: [], upcoming: [], imported: [{ ...game, details_imported_at: '2026-09-16T18:01:00Z', can_reload: false }] });
    expect(component.overview()?.missing_details).toEqual([]);
    expect(component.state(component.overview()!.imported[0])).toBe('Erfolgreich geladen');
    fixture.destroy();
    vi.advanceTimersByTime(15_000);
    http.expectNone(url);
  });

  it('honors blocked reasons and permits retrying failed imports', () => {
    const value = overview();
    value.missing_details[0] = { ...game, can_reload: false, reload_blocked_reason: 'Externe Spiel-ID fehlt.' };
    load(value);
    expect(fixture.nativeElement.textContent).toContain('Externe Spiel-ID fehlt.');
    component.reload(value.missing_details[0]);
    http.expectNone(`${url}/${game.id}/reload`);
    component.refresh();
    value.missing_details[0] = { ...game, reload: { ...request, status: 'failed', last_error: 'SourceError' } };
    load(value);
    expect(fixture.nativeElement.textContent).toContain('SourceError');
    component.reload(value.missing_details[0]);
    http.expectOne(`${url}/${game.id}/reload`).flush(request, { status: 202, statusText: 'Accepted' });
    load();
  });

  for (const [status, text] of [[409, 'Nachladen derzeit nicht möglich'], [404, 'nicht mehr vorhanden'], [403, 'ADMIN'], [401, 'Sitzung'], [500, 'nicht bestätigt']] as const) {
    it(`handles HTTP ${status} with actionable feedback and refresh`, () => {
      load();
      component.reload(game);
      http.expectOne(`${url}/${game.id}/reload`).flush({}, { status, statusText: 'Error' });
      expect(component.rowErrors()[game.id]).toContain(text);
      expect(component.pending().size).toBe(0);
      load();
    });
  }

  it('does not overlap reads and cancels requests on leave', () => {
    component.refresh();
    const reads = http.match(url);
    expect(reads.length).toBe(1);
    fixture.destroy();
    expect(reads[0].cancelled).toBe(true);
  });
});
