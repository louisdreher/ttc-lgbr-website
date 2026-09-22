import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import axe from 'axe-core';
import { PublicEventApiService } from '../../pages/events/public-event-api.service';
import { EditorialEvent } from './editorial-event';
import { createEditorialEventForm, editorialEventInput } from './editorial-event-form';

describe('Shared editorial event', () => {
  function setup() {
    const api = { getCategories: vi.fn(() => of([{ id: 2, name: 'Verein', slug: 'verein' }])) };
    TestBed.configureTestingModule({
      imports: [EditorialEvent],
      providers: [{ provide: PublicEventApiService, useValue: api }],
    });
    const fixture = TestBed.createComponent(EditorialEvent);
    const form = createEditorialEventForm();
    fixture.componentRef.setInput('form', form);
    fixture.componentRef.setInput('idPrefix', 'test');
    fixture.detectChanges();
    return { fixture, form, api };
  }

  it('loads categories only when expanded and preserves values across toggles', () => {
    const { fixture, form, api } = setup();
    expect(api.getCategories).not.toHaveBeenCalled();
    const enabled = vi.fn();
    fixture.componentInstance.enabledChange.subscribe(enabled);
    fixture.nativeElement.querySelector('input[type=checkbox]').click();
    expect(enabled).toHaveBeenCalledWith(true);
    fixture.componentRef.setInput('enabled', true);
    fixture.detectChanges();
    form.controls.title.setValue('Vereinsfest');
    fixture.componentRef.setInput('enabled', false);
    fixture.detectChanges();
    fixture.componentRef.setInput('enabled', true);
    fixture.detectChanges();
    expect(form.controls.title.value).toBe('Vereinsfest');
    expect(api.getCategories).toHaveBeenCalledTimes(1);
  });

  it('allows retrying a failed category load', () => {
    const { fixture, api } = setup();
    api.getCategories.mockReturnValueOnce(throwError(() => new Error('offline')));
    fixture.componentRef.setInput('enabled', true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=alert]')).not.toBeNull();
    fixture.nativeElement.querySelector('button').click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=alert]')).toBeNull();
    expect(fixture.nativeElement.querySelector('option:last-child').textContent).toContain('Verein');
  });

  it('serializes valid local dates and normalizes optional values', () => {
    const form = createEditorialEventForm();
    form.patchValue({ title: 'Fest', starts_at: '2026-09-17T12:00', category_id: 2, location: '  Halle  ' });
    expect(editorialEventInput(form)).toEqual({
      title: 'Fest', starts_at: new Date('2026-09-17T12:00').toISOString(), ends_at: null,
      category_id: 2, location: 'Halle', description: null,
    });
  });

  it('has accessible labels in the expanded form', async () => {
    const { fixture } = setup();
    fixture.componentRef.setInput('enabled', true);
    fixture.detectChanges();
    const result = await axe.run(fixture.nativeElement, {
      rules: { 'color-contrast': { enabled: false } }, // jsdom has no layout engine
    });
    expect(result.violations).toEqual([]);
  });
});
