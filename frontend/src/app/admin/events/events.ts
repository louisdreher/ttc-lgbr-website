import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';
import { forkJoin } from 'rxjs';

import { EventApiService } from './event-api.service';
import { AdminEvent, EventCategory, EventStatus, EventVisibility } from './event.models';

interface EventMonthGroup {
  key: string;
  label: string;
  events: AdminEvent[];
}

@Component({
  selector: 'app-events',
  imports: [DatePipe, RouterLink, RouterOutlet],
  templateUrl: './events.html',
  styleUrl: './events.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminEvents {
  private readonly eventApi = inject(EventApiService);

  readonly events = signal<AdminEvent[]>([]);
  readonly categories = signal<EventCategory[]>([]);
  readonly years = signal<number[]>([]);
  readonly selectedYear = signal<number | null>(null);
  readonly selectedCategoryIds = signal<Set<number>>(new Set());
  readonly selectedVisibilities = signal<Set<EventVisibility>>(
    new Set(['PUBLIC', 'MEMBERS_ONLY', 'HIDDEN']),
  );
  readonly selectedEventIds = signal<Set<number>>(new Set());
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly categoryNames = computed(
    () => new Map(this.categories().map((category) => [category.id, category.name])),
  );
  readonly visibleEvents = computed(() =>
    this.events().filter((event) => this.selectedVisibilities().has(event.visibility)),
  );
  readonly monthGroups = computed<EventMonthGroup[]>(() => {
    const groups: EventMonthGroup[] = [];
    for (const event of this.visibleEvents()) {
      const date = new Date(event.starts_at);
      const year = event.is_all_day ? date.getUTCFullYear() : date.getFullYear();
      const month = event.is_all_day ? date.getUTCMonth() : date.getMonth();
      const key = `${year}-${String(month + 1).padStart(2, '0')}`;
      let group = groups.at(-1);
      if (group?.key !== key) {
        group = {
          key,
          label: new Intl.DateTimeFormat('de-DE', {
            month: 'long',
            year: 'numeric',
            timeZone: event.is_all_day ? 'UTC' : undefined,
          }).format(date),
          events: [],
        };
        groups.push(group);
      }
      group.events.push(event);
    }
    return groups;
  });
  readonly selectedEvents = computed(() =>
    this.events().filter((event) => this.selectedEventIds().has(event.id)),
  );
  readonly selectionContainsSyncedEvent = computed(() =>
    this.selectedEvents().some((event) => event.team_match_id !== null),
  );

  constructor() {
    forkJoin({
      categories: this.eventApi.getCategories(),
      years: this.eventApi.getEventYears(),
    }).subscribe({
      next: ({ categories, years }) => {
        const current = new Date().getFullYear();
        this.categories.set(categories);
        this.years.set(years);
        this.selectedYear.set(years.includes(current) ? current : (years[0] ?? null));
        this.selectedCategoryIds.set(
          new Set(
            categories
              .filter((category) => category.is_active && category.slug !== 'mannschaftsspiel')
              .map((category) => category.id),
          ),
        );
        this.loadEvents();
      },
      error: (error) => this.handleError(error),
    });
    effect(() => {
      if (this.eventApi.eventsChanged() > 0) untracked(() => this.loadEvents());
    });
    effect(() => {
      const category = this.eventApi.categoryCreated();
      if (category && !this.categories().some((item) => item.id === category.id)) {
        this.categories.update((items) => [...items, category]);
        this.selectedCategoryIds.update((ids) => new Set(ids).add(category.id));
      }
    });
  }

  loadEvents(): void {
    this.loading.set(true);
    this.error.set(null);
    this.selectedEventIds.set(new Set());
    const year = this.selectedYear();
    const categoryIds = [...this.selectedCategoryIds()];
    if (year === null || categoryIds.length === 0) {
      this.events.set([]);
      this.loading.set(false);
      return;
    }
    this.eventApi.getEvents(year, categoryIds).subscribe({
      next: (events) => {
        this.events.set(events);
        this.loading.set(false);
      },
      error: (error) => this.handleError(error),
    });
  }

  selectYear(year: number): void {
    this.selectedYear.set(year);
    this.loadEvents();
  }
  toggleCategory(id: number, checked: boolean): void {
    this.selectedCategoryIds.update((ids) => {
      const next = new Set(ids);
      checked ? next.add(id) : next.delete(id);
      return next;
    });
    this.loadEvents();
  }
  toggleVisibility(visibility: EventVisibility, checked: boolean): void {
    this.selectedVisibilities.update((visibilities) => {
      const next = new Set(visibilities);
      checked ? next.add(visibility) : next.delete(visibility);
      return next;
    });
    this.clearSelection();
  }
  closeFilter(filter: HTMLDetailsElement, event: Event): void {
    if (event.target instanceof Node && !filter.contains(event.target)) filter.open = false;
  }
  toggleEvent(id: number): void {
    this.selectedEventIds.update((ids) => {
      const next = new Set(ids);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  clearSelection(): void {
    this.selectedEventIds.set(new Set());
  }
  selectAllVisible(): void {
    this.selectedEventIds.set(new Set(this.visibleEvents().map((event) => event.id)));
  }

  deleteOne(event: AdminEvent): void {
    if (event.team_match_id !== null || !globalThis.confirm(`„${event.title}“ wirklich löschen?`))
      return;
    this.eventApi.deleteEvent(event.id).subscribe({
      next: () => this.removeEvents([event.id]),
      error: (error) => this.handleError(error),
    });
  }

  deleteSelected(): void {
    const ids = [...this.selectedEventIds()];
    if (
      !ids.length ||
      this.selectionContainsSyncedEvent() ||
      !globalThis.confirm(`${ids.length} ausgewählte Events wirklich löschen?`)
    )
      return;
    this.eventApi
      .deleteEvents(ids)
      .subscribe({ next: () => this.removeEvents(ids), error: (error) => this.handleError(error) });
  }

  changeSelectedVisibility(visibility: EventVisibility | ''): void {
    const ids = [...this.selectedEventIds()];
    if (!visibility || !ids.length) return;
    this.eventApi.updateEventsVisibility(ids, visibility).subscribe({
      next: (updated) => {
        const updates = new Map(updated.map((event) => [event.id, event]));
        this.events.update((events) => events.map((event) => updates.get(event.id) ?? event));
        this.clearSelection();
      },
      error: (error) => this.handleError(error),
    });
  }

  statusLabel(status: EventStatus): string {
    return {
      PLANNED: 'Geplant',
      COMPLETED: 'Abgeschlossen',
      CANCELLED: 'Abgesagt',
      POSTPONED: 'Verschoben',
    }[status];
  }
  visibilityLabel(visibility: EventVisibility): string {
    return { PUBLIC: 'Öffentlich', MEMBERS_ONLY: 'Nur Mitglieder', HIDDEN: 'Verborgen' }[
      visibility
    ];
  }
  sourceLabel(event: AdminEvent): string {
    return event.team_match_id !== null ? 'Synchronisiert' : (event.created_by_name ?? 'Unbekannt');
  }
  hasDistinctEnd(event: AdminEvent): boolean {
    return (
      event.ends_at !== null &&
      new Date(event.ends_at).getTime() !== new Date(event.starts_at).getTime()
    );
  }

  private removeEvents(ids: number[]): void {
    const deleted = new Set(ids);
    this.events.update((events) => events.filter((event) => !deleted.has(event.id)));
    this.clearSelection();
  }
  private handleError(error: HttpErrorResponse): void {
    this.error.set(error.error?.detail ?? 'Die Aktion konnte nicht ausgeführt werden.');
    this.loading.set(false);
  }
}
