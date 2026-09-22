import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  GalleryApiService,
  GalleryDetails,
  galleryError,
} from '../../../core/media/gallery-api.service';
import { UploadedImage } from '../../../core/media/media-api.service';
import { MediaUpload } from '../../../shared/media-upload/media-upload';
import { GalleryImagePicker } from './gallery-image-picker';

@Component({
  selector: 'app-report-gallery',
  imports: [MediaUpload, GalleryImagePicker],
  templateUrl: './report-gallery.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    :host {
      display: block;
    }
    button {
      min-height: 44px;
      padding: 0.65rem 1rem;
      font: inherit;
      color: #20252b;
      background: white;
      border: 1px solid #667581;
      border-radius: 6px;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.6;
      cursor: default;
    }
    button:focus-visible {
      outline: 3px solid #226487;
      outline-offset: 3px;
    }
    p {
      font-size: 0.875rem;
      line-height: 1.5;
    }
    [role='alert'] {
      color: #a12020;
    }
  `,
})
export class ReportGallery {
  readonly eventId = input.required<number>();
  readonly articleId = input<number | null>(null);
  readonly title = input.required<string>();
  readonly dirty = input(false);
  readonly selectedId = input<number | null>(null);
  readonly savedCoverId = input<number | null>(null);
  readonly selected = output<number>();
  readonly galleryLoaded = output<GalleryDetails | null>();
  readonly busyChange = output<boolean>();
  readonly gallery = signal<GalleryDetails | null>(null);
  readonly loaded = signal(false);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly uploadOpen = signal(false);
  readonly pickerOpen = signal(false);
  readonly pending = signal<number[]>([]);
  readonly retry = signal(0);
  private readonly api = inject(GalleryApiService);
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    effect(() =>
      this.busyChange.emit(
        this.uploadOpen() || this.pickerOpen() || this.saving() || this.pending().length > 0,
      ),
    );
    effect((onCleanup) => {
      const eventId = this.eventId();
      const articleId = this.articleId();
      this.savedCoverId();
      this.retry();
      this.gallery.set(null);
      this.galleryLoaded.emit(null);
      this.loaded.set(false);
      this.error.set('');
      if (articleId === null) return;
      this.loading.set(true);
      const request = this.api.byEvent(eventId).subscribe({
        next: (gallery) => {
          this.gallery.set(gallery);
          this.galleryLoaded.emit(gallery);
          this.loaded.set(true);
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(galleryError(error));
          this.loading.set(false);
        },
      });
      onCleanup(() => request.unsubscribe());
    });
  }
  openUpload(): void {
    if (!this.loaded() || this.gallery() || this.dirty() || this.saving()) return;
    this.uploadOpen.set(true);
  }
  uploaded(images: UploadedImage[]): void {
    this.uploadOpen.set(false);
    this.pending.set(images.map((image) => image.id));
    if (images.length) this.create();
  }
  create(): void {
    if (this.saving() || !this.pending().length || this.dirty() || this.articleId() === null)
      return;
    this.saving.set(true);
    this.error.set('');
    this.api
      .create({
        title: this.title(),
        event_id: this.eventId(),
        gallery_date: null,
        show_date: true,
        media_ids: this.pending(),
        new_event: null,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.pending.set([]);
          this.saving.set(false);
          this.notice.set('Galerie angelegt. Ein vorhandenes Titelbild wurde übernommen.');
          this.retry.update((value) => value + 1);
        },
        error: (error) => {
          this.error.set(galleryError(error));
          this.saving.set(false);
        },
      });
  }
  choose(id: number): void {
    this.pickerOpen.set(false);
    this.selected.emit(id);
  }
  discard(): void {
    this.pending.set([]);
    this.retry.update((value) => value + 1);
  }
}
