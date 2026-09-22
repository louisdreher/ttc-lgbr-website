import { Subscription, switchMap, map, Observable } from 'rxjs';
import { GalleryDetails } from '../../core/media/gallery-api.service';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  inject,
  signal,
} from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  GalleryApiService,
  CreatedGallery,
  galleryError,
} from '../../core/media/gallery-api.service';
import { UploadedImage } from '../../core/media/media-api.service';
import { MediaUpload } from '../../shared/media-upload/media-upload';
import { MediaPreview } from '../../shared/media-upload/media-preview';
import { EditorialEvent } from '../../shared/editorial-event/editorial-event';
import {
  createEditorialEventForm,
  editorialEventInput,
} from '../../shared/editorial-event/editorial-event-form';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-gallery-form',
  imports: [ReactiveFormsModule, RouterLink, MediaUpload, MediaPreview, EditorialEvent],
  templateUrl: './form.html',
  styleUrls: ['./create.css', './form.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(window:beforeunload)': 'beforeUnload($event)' },
})
export class GalleryForm {
  private readonly api = inject(GalleryApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly auth = inject(AuthService);
  readonly galleryId = signal<number | null>(null);
  readonly detail = signal<GalleryDetails | null>(null);
  readonly loading = signal(false);
  readonly loadFailed = signal(false);
  readonly cover = signal<number | null>(null);
  readonly notice = signal('');
  private readRequest?: Subscription;
  readonly eventId = signal<number | null>(null);
  readonly eventTitle = signal('');
  readonly images = signal<number[]>([]);
  readonly creatingEvent = signal(false);
  readonly uploadOpen = signal(false);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly saved = signal<CreatedGallery | null>(null);
  readonly form = new FormGroup({
    title: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/\S/)],
    }),
    gallery_date: new FormControl('', { nonNullable: true }),
    show_date: new FormControl(false, { nonNullable: true }),
  });
  readonly eventForm = createEditorialEventForm();

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      this.readRequest?.unsubscribe();
      const galleryId = params.get('id');
      this.galleryId.set(galleryId === null ? null : Number(galleryId));
      this.detail.set(null);
      this.cover.set(null);
      this.notice.set('');
      this.loadFailed.set(false);
      if (galleryId !== null) {
        this.loadGallery();
        return;
      }
      const raw = params.get('eventId');
      const id = raw === null ? null : Number(raw);
      this.eventId.set(id);
      this.saved.set(null);
      this.images.set([]);
      this.creatingEvent.set(false);
      this.eventForm.reset();
      this.error.set(
        id !== null && (!Number.isSafeInteger(id) || id <= 0) ? 'Ungültiger Termin.' : '',
      );
      // URL values are editable suggestions; the API checks event identity and access.
      const title = id === null ? '' : (this.route.snapshot.queryParamMap.get('title') ?? '');
      const date = id === null ? '' : (this.route.snapshot.queryParamMap.get('date') ?? '');
      this.eventTitle.set(title);
      this.form.reset({ title, gallery_date: date, show_date: id !== null });
    });
    afterNextRender(() => this.element.nativeElement.querySelector('h1')?.focus());
  }

  loadGallery(): void {
    const id = this.galleryId();
    if (id === null) return;
    this.readRequest?.unsubscribe();
    this.loading.set(true);
    this.error.set('');
    this.loadFailed.set(false);
    this.readRequest = this.api
      .get(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (gallery) => {
          this.acceptGallery(gallery);
          this.loading.set(false);
        },
        error: (error: unknown) => {
          this.error.set(galleryError(error));
          this.loadFailed.set(true);
          this.loading.set(false);
        },
      });
  }
  reload(): void {
    if (this.confirmLeave()) this.loadGallery();
  }
  private acceptGallery(gallery: GalleryDetails): void {
    this.detail.set(gallery);
    this.eventId.set(gallery.event_id);
    this.eventTitle.set('');
    this.images.set(gallery.media_ids);
    this.cover.set(gallery.cover_image_id);
    this.creatingEvent.set(false);
    this.saved.set(null);
    this.form.reset({
      title: gallery.title,
      gallery_date: gallery.gallery_date,
      show_date: gallery.show_date,
    });
    this.eventForm.reset();
  }
  previewGallery(id: number): number | null {
    return this.detail()?.media_ids.includes(id) ? this.galleryId() : null;
  }
  setCover(id: number): void {
    this.cover.set(id);
    this.form.markAsDirty();
  }
  moveImage(index: number, direction: number): void {
    const ids = [...this.images()];
    const target = index + direction;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    this.images.set(ids);
    this.form.markAsDirty();
  }

  toggleEvent(enabled: boolean): void {
    this.creatingEvent.set(enabled);
    if (!this.form.controls.show_date.dirty) this.form.controls.show_date.setValue(enabled);
    if (enabled && !this.eventForm.controls.title.value)
      this.eventForm.controls.title.setValue(this.form.controls.title.value);
    this.form.markAsDirty();
  }
  addImages(images: UploadedImage[]): void {
    this.images.update((ids) => [...new Set([...ids, ...images.map((image) => image.id)])]);
    if (this.cover() === null) this.cover.set(this.images()[0] ?? null);
    this.uploadOpen.set(false);
    this.form.markAsDirty();
  }
  removeImage(id: number): void {
    this.images.update((ids) => ids.filter((value) => value !== id));
    if (this.cover() === id) this.cover.set(this.images()[0] ?? null);
    this.form.markAsDirty();
  }
  save(): void {
    if (this.saving() || this.saved() || this.uploadOpen() || this.loading() || this.loadFailed())
      return;
    this.error.set('');
    this.notice.set('');
    this.form.markAllAsTouched();
    const value = this.form.getRawValue();
    const id = this.eventId();
    if (this.form.invalid || (id !== null && (!Number.isSafeInteger(id) || id <= 0))) {
      this.error.set('Bitte prüfe Titel und Eventzuordnung.');
      return;
    }
    const newEvent = this.creatingEvent() ? editorialEventInput(this.eventForm) : null;
    if (this.creatingEvent() && !newEvent) {
      this.error.set('Bitte prüfe Titel, Kategorie und Zeitraum des Events.');
      return;
    }
    if (!value.gallery_date && (this.galleryId() !== null || (id === null && newEvent === null))) {
      this.error.set('Bitte gib ein Galeriedatum an.');
      return;
    }
    this.saving.set(true);
    const existing = this.detail();
    const request: Observable<
      { gallery: GalleryDetails; created: null } | { gallery: null; created: CreatedGallery }
    > = existing
      ? this.api
          .update(existing.id, {
            ...value,
            media_ids: this.images(),
            cover_image_id: this.cover(),
            updated_at: existing.updated_at,
          })
          .pipe(
            switchMap(() => this.api.get(existing.id)),
            map((gallery) => ({ gallery, created: null })),
          )
      : this.api
          .create({
            ...value,
            title: value.title.trim(),
            gallery_date: value.gallery_date || null,
            event_id: id,
            new_event: newEvent,
            media_ids: this.images(),
          })
          .pipe(map((created) => ({ gallery: null, created })));
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (result) => {
        if (result.gallery !== null) {
          this.acceptGallery(result.gallery);
          this.notice.set('Die Änderungen wurden gespeichert.');
        } else this.saved.set(result.created);
        this.saving.set(false);
        this.form.markAsPristine();
        this.eventForm.markAsPristine();
      },
      error: (error: unknown) => {
        this.error.set(galleryError(error));
        this.saving.set(false);
      },
    });
  }
  cancel(): void {
    void this.router.navigate(['/admin/galleries']);
  }
  private dirty(): boolean {
    return !this.saved() && (this.form.dirty || (this.creatingEvent() && this.eventForm.dirty));
  }
  confirmLeave(): boolean {
    if (this.saving() || this.uploadOpen()) return false;
    return (
      !this.dirty() ||
      window.confirm(
        'Deine Änderungen sind noch nicht gespeichert. Möchtest du die Seite trotzdem verlassen?',
      )
    );
  }
  beforeUnload(event: BeforeUnloadEvent): void {
    if (this.dirty() || this.saving() || this.uploadOpen()) {
      event.preventDefault();
      event.returnValue = '';
    }
  }
}
