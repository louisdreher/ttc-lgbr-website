import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { MediaCaption } from './media-caption';
import { MediaApiService } from '../../core/media/media-api.service';

describe('MediaCaption', () => {
  function setup() {
    const api = {
      caption: vi.fn(() => of({ caption: 'Original' })),
      updateCaption: vi.fn(() => of({ caption: 'Neu' })),
    };
    TestBed.configureTestingModule({ providers: [{ provide: MediaApiService, useValue: api }] });
    const fixture = TestBed.createComponent(MediaCaption);
    fixture.componentRef.setInput('mediaId', 42);
    fixture.detectChanges();
    return { fixture, component: fixture.componentInstance, api };
  }
  it('loads caption and saves it separately', () => {
    const { component, api } = setup();
    expect(component.caption.value).toBe('Original');
    component.caption.setValue('Neu');
    component.caption.markAsDirty();
    component.save();
    expect(api.updateCaption).toHaveBeenCalledWith(42, 'Neu');
    expect(component.caption.pristine).toBe(true);
    expect(component.notice()).toContain('gespeichert');
  });
  it('keeps input after failed save for retry', () => {
    const { component, api } = setup();
    component.caption.setValue('Entwurf');
    component.caption.markAsDirty();
    api.updateCaption.mockReturnValueOnce(throwError(() => new Error()));
    component.save();
    expect(component.caption.value).toBe('Entwurf');
    expect(component.caption.dirty).toBe(true);
    expect(component.error()).not.toBe('');
    expect(component.saving()).toBe(false);
  });
});
