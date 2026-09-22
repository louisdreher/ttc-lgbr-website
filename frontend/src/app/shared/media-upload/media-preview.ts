import { ChangeDetectionStrategy, Component, effect, inject, input, signal } from '@angular/core';
import { MediaApiService } from '../../core/media/media-api.service';

@Component({
  selector: 'app-media-preview',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (url()) {
      <img [src]="url()" [alt]="alt()" />
    } @else {
      <p role="status">
        {{ failed() ? 'Die Bildvorschau ist nicht verfügbar.' : 'Bildvorschau wird geladen …' }}
      </p>
    }
  `,
  styles: `
    :host {
      display: block;
    }
    img {
      display: block;
      width: 100%;
      max-width: 420px;
      max-height: 260px;
      object-fit: contain;
      margin: 1rem auto;
      border-radius: 8px;
    }
  `,
})
export class MediaPreview {
  readonly alt = input('Ausgewähltes Titelbild');
  readonly eventId = input<number | null>(null);
  readonly galleryId = input<number | null>(null);
  readonly mediaId = input.required<number>();
  readonly url = signal('');
  readonly failed = signal(false);
  private readonly api = inject(MediaApiService);
  constructor() {
    effect((onCleanup) => {
      const id = this.mediaId();
      this.url.set('');
      this.failed.set(false);
      let url = '';
      const subscription = this.api.image(id, this.galleryId(), this.eventId()).subscribe({
        next: (blob) => {
          url = URL.createObjectURL(blob);
          this.url.set(url);
        },
        error: () => this.failed.set(true),
      });
      onCleanup(() => {
        subscription.unsubscribe();
        if (url) URL.revokeObjectURL(url);
      });
    });
  }
}
