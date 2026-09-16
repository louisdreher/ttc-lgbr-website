import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { SyncRun } from './mytt.models';

@Component({
  selector: 'app-sync-run',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (run(); as value) {
      <p><strong>{{ value.status === 'running' && uncertain() ? 'Laufstatus unklar' : labels[value.status] }}</strong>
        · {{ kinds[value.kind] }} @if (value.match_id !== null) { · Spiel-ID {{ value.match_id }} }
      </p>
      <p>Start: {{ value.started_at | date:'dd.MM.yyyy HH:mm:ss' }}<br>
        Ende: {{ (value.finished_at | date:'dd.MM.yyyy HH:mm:ss') ?? 'Noch offen' }}</p>
      @if (value.status !== 'running') {
        <p>{{ value.imported }} erfolgreich · {{ value.skipped }} übersprungen
          ({{ value.kind === 'match' ? 'Spielabruf' : 'Teilschritte, keine Spielanzahl' }})</p>
      }
      @if (value.errors.length) {
        <ul aria-label="Fehler des Laufs">@for (error of value.errors; track $index) { <li>{{ error }}</li> }</ul>
      }
    } @else { <p>Noch kein Lauf vorhanden.</p> }
  `,
})
export class SyncRunComponent {
  readonly run = input<SyncRun | null>(null);
  readonly uncertain = input(false);
  readonly labels = {
    running: 'Läuft', succeeded: 'Abgeschlossen – erfolgreich', partial: 'Abgeschlossen – teilweise erfolgreich',
    failed: 'Abgeschlossen – fehlgeschlagen', waiting: 'Abruf beendet – wartet auf vollständige Ergebnisse',
  };
  readonly kinds = { nightly: 'Nachtlauf', manual: 'Manueller Abgleich', match: 'Einzelspielabruf' };
}
