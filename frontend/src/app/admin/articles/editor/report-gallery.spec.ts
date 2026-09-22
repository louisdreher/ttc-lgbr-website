import { TestBed } from '@angular/core/testing';
import axe from 'axe-core';
import { of, Subject, throwError } from 'rxjs';
import { GalleryApiService, GalleryDetails } from '../../../core/media/gallery-api.service';
import { MediaApiService } from '../../../core/media/media-api.service';
import { ReportGallery } from './report-gallery';

const gallery: GalleryDetails = {
  id: 3,
  event_id: 7,
  title: 'Vereinsfest',
  gallery_date: '2026-09-20',
  show_date: true,
  media_ids: [11, 42],
  image_count: 2,
  cover_image_id: 42,
  created_by_user_id: 2,
  updated_at: '2026-09-20T12:00:00Z',
};
const upload = { id: 11, width: 10, height: 10, mime_type: 'image/webp', file_size: 20 };

describe('Report gallery', () => {
  function setup(current: GalleryDetails | null = null, articleId: number | null = 5) {
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
      configurable: true,
      value: function (this: HTMLDialogElement) {
        this.setAttribute('open', '');
      },
    });
    Object.defineProperty(HTMLDialogElement.prototype, 'close', {
      configurable: true,
      value: function (this: HTMLDialogElement) {
        this.removeAttribute('open');
      },
    });
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    vi.spyOn(URL, 'revokeObjectURL');
    const api = { byEvent: vi.fn(() => of(current)), create: vi.fn(() => of(gallery)) };
    TestBed.configureTestingModule({
      providers: [
        { provide: GalleryApiService, useValue: api },
        { provide: MediaApiService, useValue: { image: () => of(new Blob()) } },
      ],
    });
    const fixture = TestBed.createComponent(ReportGallery);
    fixture.componentRef.setInput('eventId', 7);
    fixture.componentRef.setInput('articleId', articleId);
    fixture.componentRef.setInput('title', 'Vereinsfest');
    fixture.detectChanges();
    return { fixture, component: fixture.componentInstance, api };
  }

  it('offers gallery creation only after saving the report and current changes', () => {
    const { fixture, component, api } = setup(null, null);
    expect(api.byEvent).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Speichere den Bericht zuerst');
    fixture.componentRef.setInput('articleId', 5);
    fixture.componentRef.setInput('dirty', true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
    component.openUpload();
    expect(component.uploadOpen()).toBe(false);
  });

  it('offers existing gallery and emits a selection without modifying the gallery', () => {
    const { fixture, component, api } = setup(gallery);
    const selection = vi.fn();
    component.selected.subscribe(selection);
    expect(fixture.nativeElement.textContent).toContain('Aus Galerie');
    expect(fixture.nativeElement.textContent).not.toContain('Galerie anlegen');
    component.choose(11);
    expect(selection).toHaveBeenCalledWith(11);
    expect(api.create).not.toHaveBeenCalled();
  });

  it('opens an accessible picker and selects an image with a native button', async () => {
    const { fixture, component } = setup(gallery);
    const selection = vi.fn();
    component.selected.subscribe(selection);
    fixture.nativeElement.querySelector('button').click();
    fixture.detectChanges();
    const dialog: HTMLDialogElement = fixture.nativeElement.querySelector('dialog');
    expect(dialog.open).toBe(true);
    const result = await axe.run(dialog, { rules: { 'color-contrast': { enabled: false } } });
    expect(result.violations).toEqual([]);
    dialog
      .querySelector<HTMLButtonElement>('[aria-label="Bild 1 als Titelbild auswählen"]')!
      .click();
    fixture.detectChanges();
    expect(selection).toHaveBeenCalledWith(11);
    expect(fixture.nativeElement.querySelector('dialog')).toBeNull();
  });

  it('closing the picker leaves the report cover unchanged', () => {
    const { fixture, component } = setup(gallery);
    const selection = vi.fn();
    component.selected.subscribe(selection);
    component.pickerOpen.set(true);
    fixture.detectChanges();
    fixture.nativeElement
      .querySelector('dialog')
      .dispatchEvent(new Event('cancel', { cancelable: true }));
    fixture.detectChanges();
    expect(component.pickerOpen()).toBe(false);
    expect(selection).not.toHaveBeenCalled();
  });

  it('creates the event gallery with uploaded IDs and reloads it', () => {
    const { fixture, component, api } = setup();
    api.byEvent.mockReturnValue(of(gallery));
    component.uploaded([upload, { ...upload, id: 42 }]);
    fixture.detectChanges();
    expect(api.create).toHaveBeenCalledWith({
      title: 'Vereinsfest',
      event_id: 7,
      gallery_date: null,
      show_date: true,
      media_ids: [11, 42],
      new_event: null,
    });
    expect(component.gallery()).toEqual(gallery);
    expect(component.pending()).toEqual([]);
  });

  it('keeps uploaded images on failure and retries without another upload', () => {
    const { component, api } = setup();
    api.create.mockReturnValueOnce(throwError(() => new Error()));
    component.uploaded([upload]);
    expect(component.pending()).toEqual([11]);
    expect(component.error()).not.toBe('');
    component.create();
    expect(api.create).toHaveBeenCalledTimes(2);
    expect(component.pending()).toEqual([]);
  });

  it('prevents duplicate creation while a request is running', () => {
    const { component, api } = setup();
    api.create.mockReturnValue(new Subject<GalleryDetails>());
    component.uploaded([upload]);
    component.create();
    expect(api.create).toHaveBeenCalledTimes(1);
    expect(component.saving()).toBe(true);
  });
  it('reloads gallery membership after saving a new report cover', () => {
    const { fixture, component, api } = setup(gallery);
    api.byEvent.mockReturnValue(of({ ...gallery, media_ids: [11, 42, 99], cover_image_id: 99 }));
    fixture.componentRef.setInput('savedCoverId', 99);
    fixture.detectChanges();
    expect(api.byEvent).toHaveBeenCalledTimes(2);
    expect(component.gallery()?.media_ids).toContain(99);
    expect(component.gallery()?.cover_image_id).toBe(99);
  });
});
