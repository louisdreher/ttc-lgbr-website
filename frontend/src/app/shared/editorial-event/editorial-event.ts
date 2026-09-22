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
import { ReactiveFormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { PublicEventApiService } from '../../pages/events/public-event-api.service';
import { PublicEventCategory } from '../../pages/events/public-event.models';
import { EditorialEventForm } from './editorial-event-form';

@Component({
  selector: 'app-editorial-event',
  imports: [ReactiveFormsModule],
  templateUrl: './editorial-event.html',
  styleUrl: './editorial-event.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EditorialEvent {
  readonly form = input.required<EditorialEventForm>();
  readonly idPrefix = input.required<string>();
  readonly enabled = input(false);
  readonly enabledChange = output<boolean>();
  readonly categories = signal<PublicEventCategory[]>([]);
  readonly categoryError = signal('');
  private readonly api = inject(PublicEventApiService);
  private readonly destroyRef = inject(DestroyRef);
  private loaded = false;

  constructor() {
    effect(() => {
      if (this.enabled() && !this.loaded) this.loadCategories();
    });
  }

  loadCategories(): void {
    this.loaded = true;
    this.categoryError.set('');
    this.api
      .getCategories()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (categories) => this.categories.set(categories),
        error: () => this.categoryError.set('Die Event-Kategorien konnten nicht geladen werden.'),
      });
  }
}
