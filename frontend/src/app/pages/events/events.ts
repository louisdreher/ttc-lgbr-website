import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { forkJoin } from 'rxjs';

import { PublicEventApiService } from './public-event-api.service';
import { PublicEvent, PublicEventCategory, PublicEventStatus } from './public-event.models';

type EventView = 'list' | 'calendar';

interface EventMonthGroup {
  key: string;
  label: string;
  events: PublicEvent[];
}

interface CalendarDay {
  key: string;
  date: Date;
  isToday: boolean;
  isCurrentMonth: boolean;
}

interface CalendarSegment {
  key: string;
  event: PublicEvent;
  startColumn: number;
  span: number;
  row: number;
}

interface CalendarWeek {
  key: string;
  days: CalendarDay[];
  segments: CalendarSegment[];
}

const VIEW_STORAGE_KEY = 'public-events-view';

@Component({
  selector: 'app-public-events',
  imports: [DatePipe],
  templateUrl: './events.html',
  styleUrl: './events.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PublicEvents {
  private readonly eventApi = inject(PublicEventApiService);

  readonly events = signal<PublicEvent[]>([]);
  readonly categories = signal<PublicEventCategory[]>([]);
  readonly selectedCategoryIds = signal<Set<number>>(new Set());
  readonly startsFrom = signal(this.toDateInput(new Date()));
  readonly startsUntil = signal(this.defaultEndDate());
  readonly view = signal<EventView>(this.savedView());
  readonly calendarDate = signal(this.startOfMonth(new Date()));
  readonly selectedCalendarEvent = signal<PublicEvent | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  readonly categoryNames = computed(
    () => new Map(this.categories().map((category) => [category.id, category.name])),
  );
  readonly categoryColorIndexes = computed(
    () => new Map(this.categories().map((category, index) => [category.id, index % 6])),
  );
  readonly monthGroups = computed<EventMonthGroup[]>(() => {
    const groups: EventMonthGroup[] = [];
    for (const event of this.events()) {
      const date = new Date(event.starts_at);
      const key = this.dateKey(date, event.is_all_day).slice(0, 7);
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
  readonly calendarLabel = computed(() =>
    new Intl.DateTimeFormat('de-DE', { month: 'long', year: 'numeric' }).format(
      this.calendarDate(),
    ),
  );
  readonly calendarWeeks = computed<CalendarWeek[]>(() => {
    const month = this.calendarDate();
    const year = month.getFullYear();
    const monthIndex = month.getMonth();
    const firstWeekday = (new Date(year, monthIndex, 1).getDay() + 6) % 7;
    const gridStart = new Date(year, monthIndex, 1 - firstWeekday);
    const today = this.toDateInput(new Date());
    const weeks: CalendarWeek[] = [];
    for (let weekIndex = 0; weekIndex < 6; weekIndex += 1) {
      const days = Array.from({ length: 7 }, (_, dayIndex): CalendarDay => {
        const date = new Date(
          gridStart.getFullYear(),
          gridStart.getMonth(),
          gridStart.getDate() + weekIndex * 7 + dayIndex,
        );
        const key = this.toDateInput(date);
        return {
          key,
          date,
          isToday: key === today,
          isCurrentMonth: date.getMonth() === monthIndex,
        };
      });
      weeks.push({
        key: days[0].key,
        days,
        segments: this.calendarSegments(days[0].key, days[6].key, weekIndex),
      });
    }
    return weeks;
  });

  constructor() {
    forkJoin({ categories: this.eventApi.getCategories() }).subscribe({
      next: ({ categories }) => {
        this.categories.set(categories);
        this.selectedCategoryIds.set(new Set(categories.map((category) => category.id)));
        this.loadEvents();
      },
      error: (error) => this.handleError(error),
    });
  }

  setView(view: EventView): void {
    this.view.set(view);
    globalThis.localStorage?.setItem(VIEW_STORAGE_KEY, view);
  }

  changeDateRange(startsFrom: string, startsUntil: string): void {
    this.startsFrom.set(startsFrom);
    this.startsUntil.set(startsUntil);
    if (startsFrom) this.calendarDate.set(this.startOfMonth(new Date(`${startsFrom}T12:00:00`)));
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

  closeFilter(filter: HTMLDetailsElement, event: Event): void {
    if (event.target instanceof Node && !filter.contains(event.target)) {
      filter.open = false;
    }
  }

  previousMonth(): void {
    const current = this.calendarDate();
    this.calendarDate.set(new Date(current.getFullYear(), current.getMonth() - 1, 1));
    this.selectedCalendarEvent.set(null);
  }

  nextMonth(): void {
    const current = this.calendarDate();
    this.calendarDate.set(new Date(current.getFullYear(), current.getMonth() + 1, 1));
    this.selectedCalendarEvent.set(null);
  }

  showToday(): void {
    this.calendarDate.set(this.startOfMonth(new Date()));
    this.selectedCalendarEvent.set(null);
  }

  selectCalendarEvent(event: PublicEvent): void {
    this.selectedCalendarEvent.set(event);
  }

  categoryColorIndex(categoryId: number): number {
    return this.categoryColorIndexes().get(categoryId) ?? 0;
  }

  statusLabel(status: PublicEventStatus): string {
    return {
      PLANNED: 'Geplant',
      COMPLETED: 'Abgeschlossen',
      CANCELLED: 'Abgesagt',
      POSTPONED: 'Verschoben',
    }[status];
  }

  hasDistinctEnd(event: PublicEvent): boolean {
    return (
      event.ends_at !== null &&
      new Date(event.ends_at).getTime() !== new Date(event.starts_at).getTime()
    );
  }

  loadEvents(): void {
    const startsFrom = this.startsFrom();
    const startsUntil = this.startsUntil();
    if (!startsFrom || !startsUntil || startsUntil < startsFrom) {
      this.error.set('Bitte wähle einen gültigen Datumsbereich.');
      this.events.set([]);
      this.loading.set(false);
      return;
    }

    this.loading.set(true);
    this.error.set(null);
    const categoryIds = [...this.selectedCategoryIds()];
    if (this.categories().length > 0 && categoryIds.length === 0) {
      this.events.set([]);
      this.loading.set(false);
      return;
    }

    this.eventApi
      .getEvents(this.startOfDay(startsFrom), this.endOfDay(startsUntil), categoryIds)
      .subscribe({
        next: (events) => {
          this.events.set(events);
          this.loading.set(false);
        },
        error: (error) => this.handleError(error),
      });
  }

  private savedView(): EventView {
    return globalThis.localStorage?.getItem(VIEW_STORAGE_KEY) === 'calendar' ? 'calendar' : 'list';
  }

  private calendarSegments(
    weekStart: string,
    weekEnd: string,
    weekIndex: number,
  ): CalendarSegment[] {
    const occupiedRows: boolean[][] = [];
    return this.events()
      .filter((event) => {
        const start = this.dateKey(new Date(event.starts_at), event.is_all_day);
        const end = event.ends_at ? this.dateKey(new Date(event.ends_at), event.is_all_day) : start;
        return start <= weekEnd && end >= weekStart;
      })
      .map((event) => {
        const eventStart = this.dateKey(new Date(event.starts_at), event.is_all_day);
        const eventEnd = event.ends_at
          ? this.dateKey(new Date(event.ends_at), event.is_all_day)
          : eventStart;
        const visibleStart = eventStart > weekStart ? eventStart : weekStart;
        const visibleEnd = eventEnd < weekEnd ? eventEnd : weekEnd;
        const startColumn = this.daysBetween(weekStart, visibleStart) + 1;
        const span = this.daysBetween(visibleStart, visibleEnd) + 1;
        let row = occupiedRows.findIndex((occupied) =>
          occupied.slice(startColumn - 1, startColumn - 1 + span).every((value) => !value),
        );
        if (row === -1) {
          row = occupiedRows.length;
          occupiedRows.push(Array(7).fill(false));
        }
        occupiedRows[row].fill(true, startColumn - 1, startColumn - 1 + span);
        return {
          key: `${weekIndex}-${event.id}`,
          event,
          startColumn,
          span,
          row,
        };
      });
  }

  private daysBetween(first: string, second: string): number {
    const firstDate = new Date(`${first}T12:00:00`);
    const secondDate = new Date(`${second}T12:00:00`);
    return Math.round((secondDate.getTime() - firstDate.getTime()) / 86_400_000);
  }

  private startOfMonth(date: Date): Date {
    return new Date(date.getFullYear(), date.getMonth(), 1);
  }

  private startOfDay(value: string): string {
    return new Date(`${value}T00:00:00`).toISOString();
  }

  private endOfDay(value: string): string {
    return new Date(`${value}T23:59:59.999`).toISOString();
  }

  private defaultEndDate(): string {
    const date = new Date();
    date.setFullYear(date.getFullYear() + 1);
    return this.toDateInput(date);
  }

  private toDateInput(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private dateKey(date: Date, isAllDay: boolean): string {
    const year = isAllDay ? date.getUTCFullYear() : date.getFullYear();
    const month = isAllDay ? date.getUTCMonth() + 1 : date.getMonth() + 1;
    const day = isAllDay ? date.getUTCDate() : date.getDate();
    return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }

  private handleError(error: HttpErrorResponse): void {
    this.error.set(error.error?.detail ?? 'Die Termine konnten nicht geladen werden.');
    this.loading.set(false);
  }
}
