import { ChangeDetectionStrategy, Component, effect, inject, input, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { MediaApiService } from '../../core/media/media-api.service';

@Component({
  selector: 'app-media-caption',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <label [for]="'caption-' + mediaId()">Bildunterschrift (optional)</label>
    <textarea
      [id]="'caption-' + mediaId()"
      [formControl]="caption"
      maxlength="1000"
      rows="3"
      [attr.aria-describedby]="'caption-help-' + mediaId()"
    ></textarea>
    <p [id]="'caption-help-' + mediaId()">
      Die Bildunterschrift gehört zum Bild. Änderungen gelten auch bei Wiederverwendung und werden
      separat vom Bericht gespeichert.
    </p>
    @if (loaded() && !canEdit()) {
      <p>
        Die Bildunterschrift kann die Person ändern, die das Bild hochgeladen hat, oder die
        Redaktion.
      </p>
    }
    @if (error()) {
      <p role="alert">{{ error() }}</p>
    }
    @if (notice()) {
      <p role="status">{{ notice() }}</p>
    }
    @if (!loaded() && !loading()) {
      <button type="button" (click)="retry.update(increment)">Erneut laden</button>
    }
    <button
      type="button"
      [disabled]="!loaded() || !canEdit() || saving() || caption.pristine"
      (click)="save()"
    >
      {{ saving() ? 'Wird gespeichert …' : 'Bildunterschrift speichern' }}
    </button>
  `,
  styles: `
    :host {
      display: block;
      margin: 1rem 0;
    }
    label {
      display: block;
      font-weight: 600;
      margin-bottom: 0.5rem;
    }
    textarea {
      width: 100%;
      box-sizing: border-box;
      padding: 0.65rem;
      font: inherit;
      border: 1px solid #667581;
      border-radius: 6px;
    }
    p {
      font-size: 0.875rem;
      line-height: 1.5;
    }
    button {
      padding: 0.65rem 1rem;
      min-height: 44px;
      font: inherit;
      border: 1px solid #667581;
      border-radius: 6px;
      background: white;
      color: #20252b;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.6;
      cursor: default;
    }
    :is(button, textarea):focus-visible {
      outline: 3px solid #226487;
      outline-offset: 3px;
    }
    [role='alert'] {
      color: #a12020;
    }
  `,
})
export class MediaCaption {
  readonly eventId = input<number | null>(null);
  readonly canEdit = signal(false);
  readonly mediaId = input.required<number>();
  readonly caption = new FormControl('', { nonNullable: true });
  readonly loading = signal(true);
  readonly loaded = signal(false);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly retry = signal(0);
  readonly increment = (value: number) => value + 1;
  private readonly api = inject(MediaApiService);
  private saveRequest?: Subscription;

  constructor() {
    effect((onCleanup) => {
      const id = this.mediaId();
      this.retry();
      this.loading.set(true);
      this.loaded.set(false);
      this.saving.set(false);
      this.error.set('');
      this.notice.set('');
      this.caption.reset('');
      this.caption.disable();
      const request = this.api.caption(id, this.eventId()).subscribe({
        next: (result) => {
          this.caption.reset(result.caption ?? '');
          this.canEdit.set(result.can_edit !== false);
          if (this.canEdit()) this.caption.enable();
          this.loaded.set(true);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Bildunterschrift konnte nicht geladen werden.');
          this.loading.set(false);
        },
      });
      onCleanup(() => {
        request.unsubscribe();
        this.saveRequest?.unsubscribe();
      });
    });
  }
  save(): void {
    if (!this.loaded() || !this.canEdit() || this.saving()) return;
    this.saving.set(true);
    this.caption.disable();
    this.error.set('');
    this.notice.set('');
    this.saveRequest = this.api.updateCaption(this.mediaId(), this.caption.value).subscribe({
      next: (result) => {
        this.caption.reset(result.caption ?? '');
        this.caption.enable();
        this.saving.set(false);
        this.notice.set('Bildunterschrift gespeichert.');
      },
      error: () => {
        this.caption.enable();
        this.saving.set(false);
        this.error.set('Bildunterschrift konnte nicht gespeichert werden. Bitte erneut versuchen.');
      },
    });
  }
}
