import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError, EMPTY } from 'rxjs';
import axe from 'axe-core';
import { GalleryForm } from './form';
import { GalleryApiService } from '../../core/media/gallery-api.service';
import { MediaApiService } from '../../core/media/media-api.service';
import { AuthService } from '../../core/auth/auth.service';
import { PublicEventApiService } from '../../pages/events/public-event-api.service';

describe('Gallery form', () => {
  function setup(event = false, editing = false) {
    const params = convertToParamMap(editing ? { id: '10' } : event ? { eventId: '7' } : {});
    const api = {
      get: vi.fn(() =>
        of({
          id: 10,
          title: 'Archiv',
          event_id: 7,
          media_ids: [11, 42],
          cover_image_id: 11,
          image_count: 2,
          gallery_date: '2007-06-16',
          show_date: true,
          updated_at: '2026-01-01T00:00:00Z',
          created_by_user_id: 1,
        }),
      ),
      update: vi.fn(() => of(undefined)),
      create: vi.fn(() =>
        of({ id: 10, cover_image_id: null, gallery_date: '2007-06-16', show_date: false }),
      ),
    };
    TestBed.configureTestingModule({
      imports: [GalleryForm],
      providers: [
        provideRouter([]),
        { provide: GalleryApiService, useValue: api },
        { provide: AuthService, useValue: { hasAnyRole: () => true } },
        { provide: MediaApiService, useValue: { image: () => EMPTY } },
        {
          provide: PublicEventApiService,
          useValue: { getCategories: () => of([{ id: 1, name: 'Verein' }]) },
        },
        {
          provide: ActivatedRoute,
          useValue: {
            paramMap: of(params),
            snapshot: {
              queryParamMap: convertToParamMap(event ? { title: 'Fest', date: '2007-06-16' } : {}),
            },
          },
        },
      ],
    });
    const fixture = TestBed.createComponent(GalleryForm);
    fixture.detectChanges();
    return { fixture, form: fixture.componentInstance, api };
  }

  it('requires a date for a standalone gallery and saves the selected images', () => {
    const { form, api } = setup();
    form.form.controls.title.setValue('Archiv');
    form.save();
    expect(api.create).not.toHaveBeenCalled();
    form.form.controls.gallery_date.setValue('2007-06-16');
    form.addImages([{ id: 42, width: 1, height: 1, file_size: 10, mime_type: 'image/webp' }]);
    form.save();
    expect(api.create).toHaveBeenCalledWith({
      title: 'Archiv',
      event_id: null,
      gallery_date: '2007-06-16',
      show_date: false,
      media_ids: [42],
      new_event: null,
    });
    expect(form.saved()?.id).toBe(10);
    expect(form.confirmLeave()).toBe(true);
    form.save();
    expect(api.create).toHaveBeenCalledTimes(1);
  });

  it('prefills an event gallery and keeps the event association fixed', () => {
    const { form, fixture, api } = setup(true);
    expect(form.form.getRawValue()).toEqual({
      title: 'Fest',
      gallery_date: '2007-06-16',
      show_date: true,
    });
    expect(fixture.nativeElement.querySelector('app-editorial-event')).toBeNull();
    form.save();
    expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({ event_id: 7, show_date: true }),
    );
  });

  it('creates a new hidden event through the shared form and validates its period', () => {
    const { form, api } = setup();
    form.form.controls.title.setValue('Fest');
    form.toggleEvent(true);
    form.eventForm.patchValue({
      starts_at: '2007-06-16T12:00',
      ends_at: '2007-06-15T12:00',
      category_id: 1,
    });
    form.save();
    expect(api.create).not.toHaveBeenCalled();
    form.eventForm.controls.ends_at.setValue('');
    form.save();
    expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({
        gallery_date: null,
        show_date: true,
        new_event: expect.objectContaining({ title: 'Fest', category_id: 1, ends_at: null }),
      }),
    );
  });

  it('preserves inputs after conflicts and protects unsaved changes', () => {
    const { form, api } = setup(true);
    api.create.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 409 })));
    form.addImages([{ id: 42, width: 1, height: 1, file_size: 10, mime_type: 'image/webp' }]);
    form.save();
    expect(form.images()).toEqual([42]);
    expect(form.saved()).toBeNull();
    expect(form.error()).toContain('inzwischen');
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    expect(form.confirmLeave()).toBe(false);
    confirm.mockRestore();
    form.removeImage(42);
    expect(form.images()).toEqual([]);
  });

  it('has labelled form controls and actions', async () => {
    const { fixture } = setup();
    const result = await axe.run(fixture.nativeElement, {
      rules: { 'color-contrast': { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });

  it('loads saved galleries and sends metadata, order and cover with the loaded version', () => {
    const { form, api, fixture } = setup(false, true);
    expect(api.get).toHaveBeenCalledWith(10);
    expect(fixture.nativeElement.querySelector('app-editorial-event')).toBeNull();
    form.moveImage(1, -1);
    form.setCover(42);
    form.form.controls.title.setValue('Neu');
    form.save();
    expect(api.create).not.toHaveBeenCalled();
    expect(api.update).toHaveBeenCalledWith(
      10,
      expect.objectContaining({
        title: 'Neu',
        media_ids: [42, 11],
        cover_image_id: 42,
        updated_at: '2026-01-01T00:00:00Z',
      }),
    );
    expect(form.notice()).toContain('gespeichert');
  });

  it('keeps edit conflicts intact and selects a replacement when removing the cover', () => {
    const { form, api } = setup(false, true);
    api.update.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 409 })));
    form.removeImage(11);
    expect(form.cover()).toBe(42);
    form.save();
    expect(form.images()).toEqual([42]);
    expect(form.form.dirty).toBe(true);
    expect(form.error()).toContain('inzwischen');
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it('hides the editable form when loading fails', () => {
    const { form, api, fixture } = setup(false, true);
    api.get.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 404 })));
    form.loadGallery();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('form')).toBeNull();
    form.save();
    expect(api.update).not.toHaveBeenCalled();
  });
});
