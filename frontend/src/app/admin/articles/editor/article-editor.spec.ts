import { GalleryApiService } from '../../../core/media/gallery-api.service';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { ArticleEditor } from './article-editor';
import { MediaApiService } from '../../../core/media/media-api.service';
import { ArticleApiService } from '../../../core/articles/article-api.service';
import { PublicEventApiService } from '../../../pages/events/public-event-api.service';
import { AuthService } from '../../../core/auth/auth.service';
import { articleFixture } from '../../../core/articles/article.fixtures';
import { Article } from '../../../core/articles/article.models';

describe('Article editor workflow', () => {
  function setup(article: Article | null = articleFixture(), event = false) {
    const params = convertToParamMap(event ? { eventId: '9' } : article ? { id: '1' } : {});
    const api = {
      get: vi.fn(() => of(article)),
      prepare: vi.fn(() =>
        of({
          ...articleFixture(),
          article_id: 1,
          event_id: 9,
          article_type: 'MATCH_REPORT',
          editable_fields: ['title', 'content'],
        }),
      ),
      save: vi.fn(() => of(articleFixture())),
      publish: vi.fn(() => of(articleFixture({ status: 'PUBLISHED' }))),
    };
    TestBed.configureTestingModule({
      imports: [ArticleEditor],
      providers: [
        { provide: GalleryApiService, useValue: { byEvent: () => of(null) } },
        {
          provide: MediaApiService,
          useValue: { image: () => of(new Blob()), caption: () => of({ caption: null }) },
        },
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: params }, paramMap: of(params) },
        },
        { provide: ArticleApiService, useValue: api },
        {
          provide: PublicEventApiService,
          useValue: { getCategories: () => of([{ id: 2, name: 'Verein' }]) },
        },
        { provide: AuthService, useValue: { hasAnyRole: () => false } },
      ],
    });
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(ArticleEditor);
    fixture.detectChanges();
    return { fixture, component: fixture.componentInstance, api };
  }
  it('keeps uploaded cover selection dirty until saving and supports removal', () => {
    const { component, api } = setup(articleFixture());
    component.selectCover([
      { id: 42, width: 10, height: 10, file_size: 20, mime_type: 'image/webp' },
    ]);
    expect(component.form.dirty).toBe(true);
    component.save('save');
    expect(api.save).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ cover_image_id: 42 }),
      false,
    );
    component.removeCover();
    expect(component.coverImageId()).toBeNull();
    expect(component.form.dirty).toBe(true);
  });
  it('saves a selected gallery image through the normal report save', () => {
    const { component, api } = setup(articleFixture({ event_id: 9 }));
    component.selectGalleryCover(11);
    expect(component.form.dirty).toBe(true);
    expect(api.save).not.toHaveBeenCalled();
    component.save('save');
    expect(api.save).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ event_id: 9, cover_image_id: 11 }),
      false,
    );
  });
  it('loads a system draft without claiming and locks its match type', () => {
    const { component, api } = setup(articleFixture(), true);
    expect(api.prepare).toHaveBeenCalledWith(9);
    expect(api.save).not.toHaveBeenCalled();
    expect(component.form.controls.article_type.disabled).toBe(true);
    component.save('save');
    expect(api.save.mock.calls[0]).toEqual([
      1,
      expect.objectContaining({ event_id: 9, article_type: 'MATCH_REPORT' }),
      false,
    ]);
  });
  it('keeps submitted contributions editable and saves the full form', () => {
    const { component, api, fixture } = setup(
      articleFixture({ status: 'IN_REVIEW', event_id: 9, cover_image_id: 5 }),
    );
    expect(component.readOnly()).toBe(false);
    component.form.controls.content.setValue('Überarbeitet');
    component.save('save');
    expect(api.save.mock.calls[0]).toEqual([
      1,
      expect.objectContaining({
        event_id: 9,
        cover_image_id: 5,
        content: 'Überarbeitet',
        tags: ['verein'],
      }),
      false,
    ]);
    expect(fixture.nativeElement.textContent).toContain('bis zur Veröffentlichung');
  });
  it('shows published own contributions as read-only', () => {
    const { component, fixture, api } = setup(
      articleFixture({ status: 'PUBLISHED', allowed_actions: [] }),
    );
    expect(fixture.nativeElement.querySelector('form')).toBeNull();
    component.save('save');
    expect(api.save).not.toHaveBeenCalled();
  });
  it('does not lose input on an ownership conflict', () => {
    const { component, api } = setup();
    api.save.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 409 })));
    component.form.controls.content.setValue('Mein Text');
    component.form.markAsDirty();
    component.save('save');
    expect(component.form.controls.content.value).toBe('Mein Text');
    expect(component.form.dirty).toBe(true);
    expect(component.error()).toContain('inzwischen');
  });
  it('saves before publishing and never publishes if saving fails', () => {
    const { component, api } = setup(
      articleFixture({ allowed_actions: ['save', 'submit', 'publish'] }),
    );
    component.form.controls.content.setValue('Letzte Änderung');
    component.save('publish');
    expect(api.save.mock.invocationCallOrder[0]).toBeLessThan(
      api.publish.mock.invocationCallOrder[0],
    );
    expect(api.save.mock.calls[0]).toEqual([
      1,
      expect.objectContaining({ content: 'Letzte Änderung' }),
      false,
    ]);
  });
  it('does not publish after a failed save', () => {
    const { component, api } = setup(articleFixture({ allowed_actions: ['save', 'publish'] }));
    api.save.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 409 })));
    component.save('publish');
    expect(api.publish).not.toHaveBeenCalled();
  });
  it('validates readiness only when submitting', () => {
    const { component, api } = setup();
    component.form.controls.content.setValue('');
    component.save('submit');
    expect(api.save).not.toHaveBeenCalled();
    expect(component.error()).toContain('Inhalt');
    component.save('save');
    expect(api.save).toHaveBeenCalled();
  });
  it('protects unsaved input when leaving', () => {
    const { component } = setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    expect(component.confirmLeave()).toBe(true);
    component.form.markAsDirty();
    expect(component.confirmLeave()).toBe(false);
    confirm.mockRestore();
  });
  it('does not display an empty editable form after a failed load', () => {
    const { component, api, fixture } = setup();
    api.get.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 404 })));
    component.load();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('form')).toBeNull();
  });
  it('validates optional event dates without sending a request', () => {
    const { component, api } = setup(null);
    component.form.patchValue({ title: 'Bericht', slug: 'bericht' });
    component.toggleEvent(true);
    component.eventForm.patchValue({
      title: 'Fest',
      starts_at: '2026-09-17T12:00',
      ends_at: '2026-09-16T12:00',
      category_id: 2,
    });
    component.save('save');
    expect(api.save).not.toHaveBeenCalled();
    expect(component.error()).toContain('Zeitraum');
  });

  it('saves event input from the shared component with the article', () => {
    const { component, fixture, api } = setup(null);
    component.form.patchValue({ title: 'Bericht', slug: 'bericht' });
    fixture.nativeElement.querySelector('app-editorial-event input[type=checkbox]').click();
    fixture.detectChanges();
    expect(component.creatingEvent()).toBe(true);
    expect(component.form.dirty).toBe(true);
    component.eventForm.patchValue({
      title: 'Fest',
      starts_at: '2026-09-17T12:00',
      category_id: 2,
    });
    component.save('save');
    expect(api.save).toHaveBeenCalledWith(
      null,
      expect.objectContaining({
        new_event: expect.objectContaining({ title: 'Fest', category_id: 2, ends_at: null }),
      }),
      false,
    );
  });
});
