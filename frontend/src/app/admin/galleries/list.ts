import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  inject,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription } from 'rxjs';
import { GalleryApiService, GalleryPage, galleryError } from '../../core/media/gallery-api.service';
import { MediaPreview } from '../../shared/media-upload/media-preview';

@Component({
  selector: 'app-gallery-list',
  imports: [RouterLink, DatePipe, MediaPreview],
  templateUrl: './list.html',
  styleUrls: ['./create.css', './list.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GalleryList {
  private readonly api = inject(GalleryApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  private request?: Subscription;
  private offset = 0;
  readonly year = signal<number | null>(null);
  readonly page = signal<GalleryPage | null>(null);
  readonly years = signal<number[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  constructor() {
    this.load();
    afterNextRender(() => this.element.nativeElement.querySelector('h1')?.focus());
  }
  filter(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.year.set(value ? Number(value) : null);
    this.page.set(null);
    this.load(0);
  }
  load(offset = this.offset): void {
    this.request?.unsubscribe();
    this.offset = Math.max(0, offset);
    this.loading.set(true);
    this.error.set('');
    this.request = this.api
      .list(this.year(), this.offset)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          this.page.set(page);
          this.years.set(page.years);
          this.loading.set(false);
          if (page.offset > 0 && page.items.length === 0)
            this.load(Math.max(0, Math.ceil(page.total / page.limit) - 1) * page.limit);
        },
        error: (error: unknown) => {
          this.error.set(galleryError(error));
          this.loading.set(false);
        },
      });
  }
}
