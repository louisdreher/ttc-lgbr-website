import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { AdminTeams } from './teams';
import { TeamDetail } from './team-detail';

const seasons = [
  { id: 2, start_year: 2026, end_year: 2027, half: 'rr' },
  { id: 1, start_year: 2009, end_year: 2010, half: 'vr' },
];
const team = { id: 8, name: 'Herren III', category: 'H', team_number: 3 };

describe('Team pages', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'admin/teams', component: AdminTeams }, { path: 'admin/teams/:teamId', component: TeamDetail }]),
    ] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  async function list(url = '/admin/teams?season=1') {
    const harness = await RouterTestingHarness.create(url);
    http.expectOne('/api/competition/seasons').flush(seasons);
    await harness.fixture.whenStable();
    http.expectOne('/api/competition/teams?season_id=' + (url.includes('season=1') ? 1 : 2)).flush([team]);
    await harness.fixture.whenStable();
    return harness;
  }

  it('renders rows and links with the selected historical season', async () => {
    const harness = await list();
    const element = harness.routeNativeElement!;
    expect(element.querySelectorAll('.team-row').length).toBe(1);
    expect(element.querySelector<HTMLSelectElement>('select')!.value).toBe('1');
    expect(element.querySelector('.button')!.getAttribute('href')).toBe('/admin/teams/8?season=1');
    expect(element.querySelector('app-player-portrait')).toBeNull();
  });

  it('keeps the season when opening a team and returning', async () => {
    const harness = await list();
    await harness.navigateByUrl('/admin/teams/8?season=1', TeamDetail);
    http.expectOne('/api/competition/seasons').flush(seasons);
    http.expectOne('/api/competition/teams/8/lineup').flush({ team_id: 8, team_name: team.name, season_id: 1, category: 'H', players: [
      { player_id: 1, first_name: 'Anna', last_name: 'Test', position: 1, status: null, media_id: null },
    ] });
    await harness.fixture.whenStable();
    const element = harness.routeNativeElement!;
    expect(element.textContent).toContain('Anna Test');
    expect(element.textContent).toContain('2009/2010');
    expect(element.querySelector('img')!.getAttribute('alt')).toBe('Kein Spielerfoto vorhanden');
    const back = element.querySelector<HTMLAnchorElement>('.back')!;
    expect(back.getAttribute('href')).toBe('/admin/teams?season=1');
    await harness.navigateByUrl(back.getAttribute('href')!, AdminTeams);
    http.expectOne('/api/competition/seasons').flush(seasons);
    await harness.fixture.whenStable();
    http.expectOne('/api/competition/teams?season_id=1').flush([team]);
    await harness.fixture.whenStable();
    expect(harness.routeNativeElement!.querySelector<HTMLSelectElement>('select')!.value).toBe('1');
  });

  it('updates the URL filter and cancels stale team requests', async () => {
    const harness = await RouterTestingHarness.create('/admin/teams');
    http.expectOne('/api/competition/seasons').flush(seasons);
    await harness.fixture.whenStable();
    const stale = http.expectOne('/api/competition/teams?season_id=2');
    await harness.navigateByUrl('/admin/teams?season=1', AdminTeams);
    expect(stale.cancelled).toBe(true);
    http.expectOne('/api/competition/teams?season_id=1').flush([]);
    await harness.fixture.whenStable();
    expect(TestBed.inject(Router).url).toContain('season=1');
    expect(harness.routeNativeElement!.textContent).toContain('Keine Mannschaften');
  });

  it('falls back to the newest season for an invalid URL filter', async () => {
    const harness = await list('/admin/teams?season=999');
    expect(harness.routeNativeElement!.querySelector<HTMLSelectElement>('select')!.value).toBe('2');
  });

  it('provides a useful error and back link for an unknown team', async () => {
    const harness = await RouterTestingHarness.create('/admin/teams/999?season=1');
    http.expectOne('/api/competition/seasons').flush(seasons);
    http.expectOne('/api/competition/teams/999/lineup').flush({}, { status: 404, statusText: 'Not found' });
    await harness.fixture.whenStable();
    expect(harness.routeNativeElement!.querySelector('[role="alert"]')!.textContent).toContain('nicht gefunden');
    expect(harness.routeNativeElement!.querySelector('.back')!.getAttribute('href')).toBe('/admin/teams?season=1');
  });

  it('uses the actual team season for direct detail links', async () => {
    const harness = await RouterTestingHarness.create('/admin/teams/8');
    http.expectOne('/api/competition/seasons').flush(seasons);
    http.expectOne('/api/competition/teams/8/lineup').flush({ team_id: 8, team_name: team.name, season_id: 1, category: 'H', players: [] });
    await harness.fixture.whenStable();
    expect(harness.routeNativeElement!.textContent).toContain('Noch keine Spieler');
    expect(harness.routeNativeElement!.querySelector('.back')!.getAttribute('href')).toBe('/admin/teams?season=1');
  });
});

// Assignment actions reuse the actual API service and refresh the historical lineup.
describe('Team assignment actions', () => {
  let http: HttpTestingController;
  const player = { player_id: 3, first_name: 'Ben', last_name: 'Test', position: 1, status: null, media_id: null };
  beforeEach(() => {
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
      configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); },
    });
    Object.defineProperty(HTMLDialogElement.prototype, 'close', {
      configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); },
    });
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'admin/teams/:teamId', component: TeamDetail }]),
    ] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());
  async function detail(players: typeof player[] = []) {
    const harness = await RouterTestingHarness.create('/admin/teams/8');
    http.expectOne('/api/competition/seasons').flush(seasons);
    http.expectOne('/api/competition/teams/8/lineup').flush({ team_id: 8, team_name: team.name, season_id: 1, category: 'H', players });
    await harness.fixture.whenStable();
    return harness;
  }
  it('adds a selected candidate and refreshes the lineup', async () => {
    const harness = await detail();
    const component = harness.routeDebugElement!.componentInstance as TeamDetail;
    component.openPicker();
    await harness.fixture.whenStable();
    http.expectOne('/api/competition/teams/8/candidates').flush([
      { player_id: 3, first_name: 'Ben', last_name: 'Test', team_number: 3, rank: '4' },
    ]);
    await harness.fixture.whenStable();
    expect(harness.routeNativeElement!.textContent).toContain('3.4');
    expect(harness.routeNativeElement!.querySelector<HTMLDialogElement>('dialog')!.open).toBe(true);
    harness.routeNativeElement!.querySelector<HTMLButtonElement>('[aria-label="Ben Test hinzufügen"]')!.click();
    component.addPlayer(3); // busy state prevents duplicate submissions
    const request = http.expectOne('/api/competition/teams/8/lineup/3');
    expect(request.request.method).toBe('PUT');
    request.flush(null);
    await harness.fixture.whenStable();
    http.expectOne('/api/competition/teams/8/lineup').flush({ team_id: 8, team_name: team.name, season_id: 1, category: 'H', players: [player] });
    await harness.fixture.whenStable();
    expect(component.choosingPlayer()).toBe(false);
    expect(harness.routeNativeElement!.textContent).toContain('Ben Test');
    expect(harness.routeNativeElement!.querySelector('img')!.getAttribute('alt')).toBe('Kein Spielerfoto vorhanden');
  });
  it('removes only after confirmation and keeps the lineup on failure', async () => {
    const harness = await detail([player]);
    const component = harness.routeDebugElement!.componentInstance as TeamDetail;
    harness.routeNativeElement!.querySelector<HTMLButtonElement>('[aria-label="Ben Test aus Mannschaft entfernen"]')!.click();
    await harness.fixture.whenStable();
    http.expectNone('/api/competition/teams/8/lineup/3');
    expect(component.confirmRemoval()).toBe(3);
    component.removePlayer(3);
    const request = http.expectOne('/api/competition/teams/8/lineup/3');
    expect(request.request.method).toBe('DELETE');
    request.flush({ detail: 'Speichern fehlgeschlagen' }, { status: 500, statusText: 'Error' });
    await harness.fixture.whenStable();
    expect(component.lineup()!.players.length).toBe(1);
    expect(harness.routeNativeElement!.textContent).toContain('Speichern fehlgeschlagen');
    expect(component.busy()).toBe(false);
    component.removePlayer(3);
    http.expectOne('/api/competition/teams/8/lineup/3').flush(null);
    await harness.fixture.whenStable();
    http.expectOne('/api/competition/teams/8/lineup').flush({ team_id: 8, team_name: team.name, season_id: 1, category: 'H', players: [] });
    await harness.fixture.whenStable();
    expect(harness.routeNativeElement!.textContent).toContain('Noch keine Spieler');
  });

  it('retries a failed image association without uploading again', async () => {
    const harness = await detail([player]);
    const component = harness.routeDebugElement!.componentInstance as TeamDetail;
    harness.routeNativeElement!.querySelector<HTMLButtonElement>('[aria-label="Ben Test: Bild hochladen"]')!.click();
    await harness.fixture.whenStable();
    expect(harness.routeNativeElement!.querySelector<HTMLDialogElement>('dialog')!.open).toBe(true);
    component.imageUploaded([{ id: 42, mime_type: 'image/webp', file_size: 100, width: 100, height: 100 }]);
    const request = http.expectOne('/api/competition/teams/8/lineup/3/image');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ media_id: 42 });
    request.flush({}, { status: 500, statusText: 'Error' });
    await harness.fixture.whenStable();
    expect(component.pendingImage()?.mediaId).toBe(42);
    expect(harness.routeNativeElement!.textContent).toContain('Bildzuordnung erneut speichern');
    component.savePlayerImage();
    http.expectOne('/api/competition/teams/8/lineup/3/image').flush(null);
    await harness.fixture.whenStable();
    http.expectOne('/api/competition/teams/8/lineup').flush({ team_id: 8, team_name: team.name, season_id: 1, category: 'H', players: [player] });
    await harness.fixture.whenStable();
    expect(component.pendingImage()).toBeNull();
    expect(component.notice()).toContain('Halbserie'.toLowerCase());
  });
});
