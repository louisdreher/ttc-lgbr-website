import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { forkJoin } from 'rxjs';

import { EventApiService } from '../event-api.service';
import {
  AdminEvent,
  EventCategory,
  EventStatus,
  EventUpdate,
  EventVisibility,
  EventWrite,
} from '../event.models';

const SYNCED_FIELDS = [
  'title',
  'starts_at',
  'ends_at',
  'is_all_day',
  'category_id',
  'status',
  'location',
] as const;

function validPeriod(control: AbstractControl): ValidationErrors | null {
  const start = control.get('starts_at')?.value as string | undefined;
  const end = control.get('ends_at')?.value as string | undefined;
  return start && end && new Date(end) < new Date(start) ? { invalidPeriod: true } : null;
}

@Component({
  selector: 'app-event-form',
  imports: [ReactiveFormsModule],
  templateUrl: './event-form.html',
  styleUrl: './event-form.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EventForm {
  private readonly eventApi = inject(EventApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly eventId = Number(this.route.snapshot.paramMap.get('id')) || null;

  readonly event = signal<AdminEvent | null>(null);
  readonly categories = signal<EventCategory[]>([]);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly categoryDialogOpen = signal(false);
  readonly isEditing = this.eventId !== null;
  readonly isSynced = computed(() => this.event()?.team_match_id != null);
  readonly heading = this.isEditing ? 'Event bearbeiten' : 'Event erstellen';

  readonly form = new FormGroup(
    {
      title: new FormControl('', {
        nonNullable: true,
        validators: [Validators.required, Validators.maxLength(200)],
      }),
      starts_at: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
      ends_at: new FormControl('', { nonNullable: true }),
      is_all_day: new FormControl(false, { nonNullable: true }),
      category_id: new FormControl<number | null>(null, { validators: [Validators.required] }),
      status: new FormControl<EventStatus>('PLANNED', {
        nonNullable: true,
        validators: [Validators.required],
      }),
      visibility: new FormControl<EventVisibility>('PUBLIC', {
        nonNullable: true,
        validators: [Validators.required],
      }),
      report_expected: new FormControl(true, { nonNullable: true }),
      location: new FormControl('', { nonNullable: true, validators: [Validators.maxLength(300)] }),
      description: new FormControl('', { nonNullable: true }),
    },
    { validators: [validPeriod] },
  );

  readonly categoryForm = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(100)],
    }),
    slug: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)],
    }),
    default_report_expected: new FormControl(true, { nonNullable: true }),
  });

  constructor() {
    if (this.eventId === null) {
      this.eventApi.getCategories().subscribe({
        next: (categories) => {
          this.categories.set(categories);
          this.form.controls.category_id.setValue(
            categories.find((category) => category.is_active)?.id ?? null,
          );
          this.loading.set(false);
        },
        error: (error) => this.handleLoadError(error),
      });
      return;
    }

    forkJoin({
      categories: this.eventApi.getCategories(),
      event: this.eventApi.getEvent(this.eventId),
    }).subscribe({
      next: ({ categories, event }) => {
        this.categories.set(categories);
        this.event.set(event);
        this.form.patchValue({
          ...event,
          starts_at: event.is_all_day
            ? event.starts_at.slice(0, 10)
            : this.toLocalDateTime(event.starts_at),
          ends_at: event.ends_at
            ? event.is_all_day
              ? event.ends_at.slice(0, 10)
              : this.toLocalDateTime(event.ends_at)
            : '',
          location: event.location ?? '',
          description: event.description ?? '',
        });
        if (event.team_match_id !== null) {
          for (const field of SYNCED_FIELDS) {
            this.form.controls[field].disable();
          }
        }
        this.loading.set(false);
      },
      error: (error) => this.handleLoadError(error),
    });
  }

  availableCategories(): EventCategory[] {
    const selectedId = this.event()?.category_id;
    return this.categories().filter((category) => category.is_active || category.id === selectedId);
  }

  setCategorySlug(): void {
    if (this.categoryForm.controls.slug.dirty) return;
    this.categoryForm.controls.slug.setValue(
      this.categoryForm.controls.name.value
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, ''),
    );
  }

  toggleAllDay(allDay: boolean): void {
    for (const control of [this.form.controls.starts_at, this.form.controls.ends_at]) {
      const value = control.value;
      if (!value) continue;
      control.setValue(allDay ? value.slice(0, 10) : `${value.slice(0, 10)}T00:00`);
    }
  }

  createCategory(): void {
    if (this.categoryForm.invalid) {
      this.categoryForm.markAllAsTouched();
      return;
    }
    this.eventApi
      .createCategory({ ...this.categoryForm.getRawValue(), is_active: true, sort_order: 0 })
      .subscribe({
        next: (category) => {
          this.categories.update((items) => [...items, category]);
          this.eventApi.categoryCreated.set(category);
          this.form.controls.category_id.setValue(category.id);
          this.categoryDialogOpen.set(false);
          this.categoryForm.reset({ name: '', slug: '', default_report_expected: true });
        },
        error: (error: HttpErrorResponse) =>
          this.error.set(error.error?.detail ?? 'Die Kategorie konnte nicht erstellt werden.'),
      });
  }

  close(): void {
    void this.router.navigate(['/admin/events']);
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const raw = this.form.getRawValue();
    if (raw.category_id === null) return;

    const payload: EventWrite = {
      ...raw,
      category_id: raw.category_id,
      starts_at: raw.is_all_day
        ? `${raw.starts_at.slice(0, 10)}T00:00:00.000Z`
        : new Date(raw.starts_at).toISOString(),
      ends_at: raw.ends_at
        ? raw.is_all_day
          ? `${raw.ends_at.slice(0, 10)}T00:00:00.000Z`
          : new Date(raw.ends_at).toISOString()
        : null,
      location: raw.location.trim() || null,
      description: raw.description.trim() || null,
    };
    const request =
      this.eventId === null
        ? this.eventApi.createEvent(payload)
        : this.eventApi.updateEvent(
            this.eventId,
            this.isSynced() ? this.editorialChanges(payload) : payload,
          );

    this.saving.set(true);
    this.error.set(null);
    request.subscribe({
      next: () => {
        this.eventApi.notifyEventChanged();
        void this.router.navigate(['/admin/events']);
      },
      error: (error: HttpErrorResponse) => {
        this.error.set(error.error?.detail ?? 'Das Event konnte nicht gespeichert werden.');
        this.saving.set(false);
      },
    });
  }

  private editorialChanges(payload: EventWrite): EventUpdate {
    return {
      visibility: payload.visibility,
      report_expected: payload.report_expected,
      description: payload.description,
    };
  }

  private toLocalDateTime(value: string): string {
    const date = new Date(value);
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
    return local.toISOString().slice(0, 16);
  }

  private handleLoadError(error: HttpErrorResponse): void {
    this.error.set(error.error?.detail ?? 'Die Formulardaten konnten nicht geladen werden.');
    this.loading.set(false);
  }
}
