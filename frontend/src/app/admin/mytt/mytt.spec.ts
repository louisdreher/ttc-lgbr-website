import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { vi } from 'vitest';
import { AdminMytt } from './mytt';
import { OutboxMessage, SyncSettings, SyncStatus } from './mytt.models';

const settings: SyncSettings = {
  enabled: true, nightly_hour: 3, nightly_minute: 0, result_delay_minutes: 180,
  result_retry_minutes: 30, result_retry_window_hours: 24, include_tables: true, include_registrations: true,
};
const initialStatus = (): SyncStatus => ({
  settings, state: { requested: false, last_nightly_slot: null, last_nightly_success_at: null,
    last_run: null, nightly_run: null, last_error: null, last_error_at: null },
  heartbeat_at: new Date().toISOString(), worker_online: true, running: false, stale_run: false,
  next_nightly_at: null, next_match_at: null,
});
const message: OutboxMessage = {
  event_id: 'e1', event_type: 'MatchImported', deduplication_key: 'match:1', occurred_at: '2026-09-16T10:00:00Z',
  processed_at: null, attempts: 5, last_error: 'TimeoutError', next_attempt_at: null,
  locked_until: null, failed_at: '2026-09-16T11:00:00Z',
};

describe('AdminMytt', () => {
  let fixture: ComponentFixture<AdminMytt>;
  let component: AdminMytt;
  let http: HttpTestingController;
  const base = '/api/admin/mytt';
  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ imports: [AdminMytt], providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AdminMytt);
    component = fixture.componentInstance;
  });
  afterEach(() => { fixture.destroy(); http.verify(); vi.useRealTimers(); });
  function load(value = initialStatus()) {
    http.expectOne(`${base}/status`).flush(value);
    http.expectOne(`${base}/settings`).flush(settings);
    http.expectOne(`${base}/outbox?limit=20`).flush([message]);
    fixture.detectChanges();
  }

  it('shows loading, empty runs and a separately preserved general run', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Status wird geladen');
    const value = initialStatus();
    value.state.last_run = { kind: 'match', match_id: 42, started_at: value.heartbeat_at!, finished_at: null, status: 'waiting', imported: 0, skipped: 1, errors: ['Incomplete'] };
    value.state.nightly_run = { ...value.state.last_run, kind: 'nightly', match_id: null, status: 'succeeded', imported: 3, errors: [] };
    load(value);
    expect(fixture.nativeElement.textContent).toContain('Spiel-ID 42');
    expect(fixture.nativeElement.textContent).toContain('Abgeschlossen – erfolgreich');
    expect(fixture.nativeElement.textContent).toContain('Incomplete');
  });

  it('treats 202 as requested even with automation disabled and worker offline', () => {
    const value = initialStatus();
    value.worker_online = false;
    value.settings = { ...settings, enabled: false };
    load(value);
    component.requestSync();
    const request = http.expectOne(`${base}/sync`);
    expect(request.request.method).toBe('POST');
    request.flush({ requested: true }, { status: 202, statusText: 'Accepted' });
    expect(component.status()?.state.requested).toBe(true);
    http.expectOne(`${base}/status`).flush({ ...value, state: { ...value.state, requested: true } });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Worker nicht erreichbar');
    expect(fixture.nativeElement.textContent).toContain('Angefordert');
    expect(component.notice()).toContain('noch nicht abgeschlossen');
    component.requestSync();
    http.expectNone(`${base}/sync`);
  });

  it('replaces a pending status read after a successful request', () => {
    load();
    component.refreshStatus();
    const oldRead = http.expectOne(`${base}/status`);
    component.requestSync();
    http.expectOne(`${base}/sync`).flush({ requested: true }, { status: 202, statusText: 'Accepted' });
    expect(oldRead.cancelled).toBe(true);
    const value = initialStatus();
    value.state.requested = true;
    http.expectOne(`${base}/status`).flush(value);
    expect(component.status()?.state.requested).toBe(true);
  });

  it('polls without overwriting edits, recovers from errors and stops on destruction', () => {
    load();
    component.form.controls.nightly_time.setValue('04:15');
    vi.advanceTimersByTime(15_000);
    http.expectOne(`${base}/status`).flush(null, { status: 503, statusText: 'Unavailable' });
    http.expectOne(`${base}/outbox?limit=20`).flush([]);
    expect(component.statusError()).toContain('veraltet');
    expect(component.uncertain()).toBe(true);
    vi.advanceTimersByTime(15_000);
    http.expectOne(`${base}/status`).flush(initialStatus());
    http.expectOne(`${base}/outbox?limit=20`).flush([]);
    expect(component.statusError()).toBe('');
    expect(component.form.controls.nightly_time.value).toBe('04:15');
    fixture.destroy();
    vi.advanceTimersByTime(15_000);
    http.expectNone(`${base}/status`);
  });

  it('does not overlap polling requests and cancels outstanding reads on leave', () => {
    component.refresh();
    const requests = http.match(request => request.method === 'GET');
    expect(requests.length).toBe(3);
    fixture.destroy();
    expect(requests.every(request => request.cancelled)).toBe(true);
  });

  it('validates bounds and sends all settings with parsed nightly time', () => {
    load();
    for (const invalid of [-1, 1441, 1.5]) {
      component.form.controls.result_delay_minutes.setValue(invalid);
      component.saveSettings();
      http.expectNone(`${base}/settings`);
    }
    component.form.patchValue({ nightly_time: '23:59', result_delay_minutes: 0, result_retry_minutes: 5, result_retry_window_hours: 168, enabled: false, include_tables: false });
    component.saveSettings();
    const request = http.expectOne(`${base}/settings`);
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({ ...settings, nightly_hour: 23, nightly_minute: 59,
      result_delay_minutes: 0, result_retry_minutes: 5, result_retry_window_hours: 168, enabled: false, include_tables: false });
    request.flush(null, { status: 500, statusText: 'Error' });
    expect(component.form.controls.nightly_time.value).toBe('23:59');
    expect(component.settingsError()).toContain('Eingaben bleiben erhalten');
    expect(component.saving()).toBe(false);
  });

  it('shows stale runs as uncertain and expires a heartbeat locally', () => {
    const value = initialStatus();
    value.state.last_run = { kind: 'manual', match_id: null, started_at: value.heartbeat_at!, finished_at: null, status: 'running', imported: 0, skipped: 0, errors: [] };
    value.running = true;
    load(value);
    component.now.set(Date.parse(value.heartbeat_at!) + 91_000);
    fixture.detectChanges();
    expect(component.workerOnline()).toBe(false);
    expect(fixture.nativeElement.textContent).toContain('Laufstatus unklar');
  });

  it('blocks processed/reserved messages and handles retry conflicts and success', () => {
    load();
    expect(component.canRetry({ ...message, processed_at: message.occurred_at })).toBe(false);
    expect(component.canRetry({ ...message, locked_until: new Date(Date.now() + 60_000).toISOString() })).toBe(false);
    component.retry(message);
    const conflict = http.expectOne(`${base}/outbox/e1/retry`);
    expect(conflict.request.method).toBe('POST');
    conflict.flush({}, { status: 409, statusText: 'Conflict' });
    http.expectOne(`${base}/outbox?limit=20`).flush([message]);
    expect(component.actionError()).toContain('reserviert');
    component.retry(message);
    http.expectOne(`${base}/outbox/e1/retry`).flush(null, { status: 204, statusText: 'No Content' });
    http.expectOne(`${base}/outbox?limit=20`).flush([{ ...message, failed_at: null, attempts: 0 }]);
    expect(component.notice()).toContain('erneut freigegeben');
    expect(component.retrying()).toBe(null);
  });

  it('keeps failed settings disabled and supports explicitly reloading them', () => {
    http.expectOne(`${base}/status`).flush(initialStatus());
    http.expectOne(`${base}/outbox?limit=20`).flush([]);
    http.expectOne(`${base}/settings`).flush({}, { status: 403, statusText: 'Forbidden' });
    expect(component.settingsReady()).toBe(false);
    expect(component.settingsError()).toContain('ADMIN');
    component.saveSettings();
    http.expectNone(`${base}/settings`);
    component.loadSettings();
    http.expectOne(`${base}/settings`).flush(settings);
    expect(component.settingsReady()).toBe(true);
  });
});
