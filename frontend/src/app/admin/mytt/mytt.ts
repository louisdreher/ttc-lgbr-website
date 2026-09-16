import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, interval, Subscription } from 'rxjs';
import { MyttApiService } from './mytt-api.service';
import { OutboxMessage, SyncSettings, SyncStatus } from './mytt.models';
import { SyncRunComponent } from './sync-run';
import { MyttMatches } from './matches';

@Component({
  selector: 'app-admin-mytt',
  imports: [DatePipe, ReactiveFormsModule, SyncRunComponent, MyttMatches],
  templateUrl: './mytt.html',
  styleUrl: './mytt.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminMytt {
  private readonly api = inject(MyttApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder).nonNullable;
  private statusRequest?: Subscription;
  private outboxRequest?: Subscription;
  readonly status = signal<SyncStatus | null>(null);
  readonly outbox = signal<OutboxMessage[]>([]);
  readonly statusLoading = signal(false);
  readonly outboxLoading = signal(false);
  readonly settingsLoading = signal(false);
  readonly settingsReady = signal(false);
  readonly statusError = signal('');
  readonly outboxError = signal('');
  readonly settingsError = signal('');
  readonly actionError = signal('');
  readonly notice = signal('');
  readonly saving = signal(false);
  readonly requesting = signal(false);
  readonly retrying = signal<string | null>(null);
  readonly updatedAt = signal<Date | null>(null);
  readonly now = signal(Date.now());
  readonly workerOnline = computed(() => {
    const value = this.status();
    return !!value?.worker_online && !!value.heartbeat_at &&
      this.now() - Date.parse(value.heartbeat_at) <= 90_000;
  });
  readonly uncertain = computed(() => !!this.statusError() || !this.workerOnline() || !!this.status()?.stale_run);
  readonly generalRunning = computed(() => this.status()?.state.nightly_run?.status === 'running');
  readonly syncLabel = computed(() => {
    if (this.requesting()) return 'Wird angefordert …';
    if (this.status()?.state.requested) return 'Angefordert';
    if (this.generalRunning()) return this.uncertain() ? 'Laufstatus unklar' : 'Synchronisierung läuft';
    return 'Spielplan synchronisieren';
  });
  readonly form = this.fb.group({
    enabled: true,
    nightly_time: ['03:00', [Validators.required, Validators.pattern(/^([01]\d|2[0-3]):[0-5]\d$/)]],
    result_delay_minutes: [180, [Validators.required, Validators.min(0), Validators.max(1440), Validators.pattern(/^\d+$/)]],
    result_retry_minutes: [30, [Validators.required, Validators.min(5), Validators.max(1440), Validators.pattern(/^\d+$/)]],
    result_retry_window_hours: [24, [Validators.required, Validators.min(1), Validators.max(168), Validators.pattern(/^\d+$/)]],
    include_tables: true,
    include_registrations: true,
  });

  constructor() {
    this.refresh();
    this.loadSettings();
    interval(15_000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.refresh());
  }

  refresh(): void {
    this.now.set(Date.now());
    this.refreshStatus();
    this.refreshOutbox();
  }

  refreshStatus(force = false): void {
    if (force) this.statusRequest?.unsubscribe();
    if (this.statusLoading()) return;
    this.statusLoading.set(true);
    this.statusRequest = this.api.getStatus().pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.statusLoading.set(false))).subscribe({
      next: value => { this.status.set(value); this.statusError.set(''); this.updatedAt.set(new Date()); },
      error: error => this.statusError.set(this.errorText(error, 'Status konnte nicht aktualisiert werden. Angezeigte Daten sind möglicherweise veraltet.')),
    });
  }

  refreshOutbox(force = false): void {
    if (force) this.outboxRequest?.unsubscribe();
    if (this.outboxLoading()) return;
    this.outboxLoading.set(true);
    this.outboxRequest = this.api.getOutbox().pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.outboxLoading.set(false))).subscribe({
      next: value => { this.outbox.set(value); this.outboxError.set(''); },
      error: error => this.outboxError.set(this.errorText(error, 'Outbox konnte nicht aktualisiert werden. Angezeigte Daten sind möglicherweise veraltet.')),
    });
  }

  loadSettings(): void {
    if (this.settingsLoading()) return;
    this.settingsLoading.set(true);
    this.api.getSettings().pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.settingsLoading.set(false))).subscribe({
      next: value => { this.setForm(value); this.settingsReady.set(true); this.settingsError.set(''); },
      error: error => this.settingsError.set(this.errorText(error, 'Einstellungen konnten nicht geladen werden.')),
    });
  }

  saveSettings(): void {
    if (!this.settingsReady() || this.saving()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const { nightly_time, ...values } = this.form.getRawValue();
    const [nightly_hour, nightly_minute] = nightly_time.split(':').map(Number);
    this.saving.set(true);
    this.settingsError.set('');
    this.notice.set('');
    this.api.saveSettings({ ...values, nightly_hour, nightly_minute })
      .pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.saving.set(false))).subscribe({
        next: value => { this.setForm(value); this.notice.set('Einstellungen gespeichert. Sie gelten für die nächste Aufgabenauswahl.'); this.refreshStatus(true); },
        error: error => this.settingsError.set(this.errorText(error, 'Einstellungen konnten nicht gespeichert werden. Deine Eingaben bleiben erhalten.')),
      });
  }

  requestSync(): void {
    if (!this.status() || this.requesting() || this.status()?.state.requested || this.generalRunning()) return;
    this.requesting.set(true);
    this.actionError.set('');
    this.notice.set('');
    this.api.requestSync().pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.requesting.set(false))).subscribe({
      next: () => {
        this.status.update(value => value ? { ...value, state: { ...value.state, requested: true } } : value);
        this.refreshStatus(true);
      },
      error: error => this.actionError.set(this.errorText(error, 'Anforderung konnte nicht bestätigt werden. Bitte Status aktualisieren, bevor du es erneut versuchst.')),
    });
  }

  outboxState(message: OutboxMessage): string {
    if (message.processed_at) return 'Verarbeitet';
    if (message.locked_until && Date.parse(message.locked_until) > this.now()) return 'In Verarbeitung (reserviert)';
    if (message.failed_at) return 'Fehlgeschlagen';
    return message.next_attempt_at ? 'Wartet auf nächsten Versuch' : 'Bereit';
  }

  canRetry(message: OutboxMessage): boolean {
    return !message.processed_at && (!message.locked_until || Date.parse(message.locked_until) <= this.now());
  }

  retry(message: OutboxMessage): void {
    if (this.retrying() || !this.canRetry(message)) return;
    this.retrying.set(message.event_id);
    this.actionError.set('');
    this.notice.set('');
    this.api.retry(message.event_id).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.retrying.set(null))).subscribe({
      next: () => { this.notice.set('Nachricht erneut freigegeben. Die Verarbeitung erfolgt durch den Worker.'); this.refreshOutbox(true); },
      error: error => {
        this.actionError.set(error instanceof HttpErrorResponse && error.status === 409
          ? 'Nachricht kann nicht erneut freigegeben werden: Sie wurde bereits verarbeitet, ist reserviert oder nicht mehr vorhanden.'
          : this.errorText(error, 'Nachricht konnte nicht erneut freigegeben werden.'));
        this.refreshOutbox(true);
      },
    });
  }

  private setForm(value: SyncSettings): void {
    this.form.reset({ ...value, nightly_time: `${String(value.nightly_hour).padStart(2, '0')}:${String(value.nightly_minute).padStart(2, '0')}` });
  }

  private errorText(error: unknown, fallback: string): string {
    if (error instanceof HttpErrorResponse && error.status === 403) return 'Zugriff verweigert. Für diese Aktion ist die Rolle ADMIN erforderlich.';
    if (error instanceof HttpErrorResponse && error.status === 401) return 'Deine Sitzung ist abgelaufen. Bitte melde dich erneut an.';
    return fallback;
  }
}
