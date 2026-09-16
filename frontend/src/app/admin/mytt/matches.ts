import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize, interval, Subscription } from 'rxjs';
import { MyttApiService } from './mytt-api.service';
import { SyncMatch, SyncMatchOverview } from './mytt.models';

@Component({
  selector: 'app-mytt-matches',
  imports: [DatePipe],
  templateUrl: './matches.html',
  styleUrl: './matches.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MyttMatches {
  private readonly api = inject(MyttApiService);
  private readonly destroyRef = inject(DestroyRef);
  private read?: Subscription;
  readonly uncertain = input(true);
  readonly overview = signal<SyncMatchOverview | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly feedback = signal('');
  readonly pending = signal<ReadonlySet<number>>(new Set());
  readonly rowErrors = signal<Record<number, string>>({});
  readonly groups = computed(() => [
    { key: 'missing_details', title: 'Details fehlen', matches: this.overview()?.missing_details ?? [], open: true },
    { key: 'upcoming', title: 'Anstehend', matches: this.overview()?.upcoming ?? [], open: true },
    { key: 'imported', title: 'Erfolgreich geladen', matches: this.overview()?.imported ?? [], open: false },
  ]);

  constructor() {
    this.refresh();
    interval(15_000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.refresh());
  }

  refresh(force = false): void {
    if (force) this.read?.unsubscribe();
    if (this.loading()) return;
    this.loading.set(true);
    this.read = this.api.getMatches().pipe(
      takeUntilDestroyed(this.destroyRef), finalize(() => this.loading.set(false)),
    ).subscribe({
      next: value => { this.overview.set(value); this.error.set(''); },
      error: error => this.error.set(this.accessError(error) ?? 'Spiele konnten nicht aktualisiert werden. Vorhandene Angaben sind möglicherweise veraltet.'),
    });
  }

  state(match: SyncMatch): string {
    if (match.details_imported_at) return 'Erfolgreich geladen';
    if (this.pending().has(match.id)) return 'Wird angefordert …';
    switch (match.reload?.status) {
      case 'requested': return 'Angefordert';
      case 'running': return this.uncertain() || !!this.error() ? 'Laufstatus unklar' : 'Läuft';
      case 'failed': return 'Nachladen fehlgeschlagen';
      case 'succeeded': return 'Auftrag abgeschlossen';
      default: return match.is_completed ? 'Details fehlen' : 'Anstehend';
    }
  }

  reload(match: SyncMatch): void {
    if (!match.can_reload || this.pending().has(match.id)) return;
    this.pending.update(ids => new Set([...ids, match.id]));
    this.rowErrors.update(errors => ({ ...errors, [match.id]: '' }));
    this.feedback.set('');
    this.api.reloadMatch(match.id).pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.pending.update(ids => new Set([...ids].filter(id => id !== match.id)))),
    ).subscribe({
      next: reload => {
        // Discard pre-request snapshots so they cannot undo the accepted status.
        this.read?.unsubscribe();
        this.overview.update(value => value ? {
          ...value,
          missing_details: value.missing_details.map(item => item.id === match.id
            ? { ...item, reload, can_reload: false, reload_blocked_reason: 'Nachlade-Auftrag vorhanden.' }
            : item),
        } : value);
        this.feedback.set(`Nachladen für ${match.team_name} gegen ${match.opponent_name}: ${reload.status === 'running' ? 'Auftrag läuft bereits.' : 'Anforderung gespeichert.'}`);
        this.refresh(true);
      },
      error: error => {
        const message = this.accessError(error) ?? (error instanceof HttpErrorResponse && error.status === 409
          ? 'Nachladen derzeit nicht möglich. Das Spiel wurde bereits importiert, wird gerade geladen oder erfüllt die Voraussetzungen nicht mehr.'
          : error instanceof HttpErrorResponse && error.status === 404
            ? 'Das Spiel ist nicht mehr vorhanden.'
            : 'Anforderung konnte nicht bestätigt werden. Bitte den aktualisierten Status prüfen, bevor du es erneut versuchst.');
        this.rowErrors.update(errors => ({ ...errors, [match.id]: message }));
        this.feedback.set(`${match.team_name} gegen ${match.opponent_name}: ${message}`);
        this.refresh(true);
      },
    });
  }

  private accessError(error: unknown): string | null {
    if (error instanceof HttpErrorResponse && error.status === 403) return 'Zugriff verweigert. Die Rolle ADMIN ist erforderlich.';
    if (error instanceof HttpErrorResponse && error.status === 401) return 'Deine Sitzung ist abgelaufen. Bitte erneut anmelden.';
    return null;
  }
}
