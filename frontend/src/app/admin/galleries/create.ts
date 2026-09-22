import { RouterLink } from '@angular/router';
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
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  GalleryApiService,
  GalleryEventGroup,
  GalleryOpportunityPage,
  galleryError,
} from '../../core/media/gallery-api.service';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-gallery-create',
  imports: [DatePipe, RouterLink],
  templateUrl: './create.html',
  styleUrl: './create.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminGalleryCreate {
  private readonly api = inject(GalleryApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly auth = inject(AuthService);
  readonly groups = (['other_events', 'team_matches'] as const).map((key) => ({
    key,
    title: key === 'other_events' ? 'Veranstaltungen' : 'Mannschaftsspiele',
    page: signal<GalleryOpportunityPage | null>(null),
    loading: signal(false),
    error: signal(''),
    requestedOffset: 0,
  }));

  constructor() {
    afterNextRender(() => this.element.nativeElement.querySelector('h1')?.focus());
    for (const group of this.groups) this.load(group.key);
  }

  eventDate(value: string): string {
    return new Intl.DateTimeFormat('sv-SE', {
      timeZone: 'Europe/Berlin',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date(value));
  }

  load(key: GalleryEventGroup, offset?: number): void {
    const group = this.groups.find((item) => item.key === key)!;
    if (group.loading()) return;
    group.requestedOffset = Math.max(0, offset ?? group.requestedOffset);
    group.loading.set(true);
    group.error.set('');
    this.api
      .opportunities(key, group.requestedOffset)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          group.page.set(page);
          group.loading.set(false);
          // A gallery created in another session can empty the last page.
          if (page.offset > 0 && page.items.length === 0) {
            this.load(key, Math.max(0, Math.ceil(page.total / page.limit) - 1) * page.limit);
          }
        },
        error: (error: unknown) => {
          group.error.set(galleryError(error));
          group.loading.set(false);
        },
      });
  }
}
