import { FormControl, FormGroup, Validators } from '@angular/forms';
import { EditorialEventInput } from '../../core/events/editorial-event.models';

export function createEditorialEventForm() {
  return new FormGroup({
    title: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(255), Validators.pattern(/\S/)],
    }),
    starts_at: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    ends_at: new FormControl('', { nonNullable: true }),
    category_id: new FormControl<number | null>(null, Validators.required),
    location: new FormControl('', { nonNullable: true }),
    description: new FormControl('', { nonNullable: true }),
  });
}

export type EditorialEventForm = ReturnType<typeof createEditorialEventForm>;

export function editorialEventInput(form: EditorialEventForm): EditorialEventInput | null {
  form.markAllAsTouched();
  const event = form.getRawValue();
  const start = new Date(event.starts_at);
  const end = event.ends_at ? new Date(event.ends_at) : null;
  if (
    form.invalid ||
    event.category_id === null ||
    !Number.isFinite(start.getTime()) ||
    (end !== null && (!Number.isFinite(end.getTime()) || end < start))
  )
    return null;
  return {
    ...event,
    category_id: event.category_id,
    starts_at: start.toISOString(),
    ends_at: end?.toISOString() ?? null,
    location: event.location.trim() || null,
    description: event.description.trim() || null,
  };
}
