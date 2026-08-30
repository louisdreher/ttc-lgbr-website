import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';
import { vi } from 'vitest';

import { EventApiService } from '../event-api.service';
import { EventForm } from './event-form';

describe('EventForm', () => {
  let fixture: ComponentFixture<EventForm>;
  const updateEvent = vi.fn(() => of({}));
  const syncedEvent = {
    id: 5,
    title: 'TTC – Gast',
    starts_at: '2026-09-01T18:00:00Z',
    ends_at: null,
    is_all_day: false,
    category_id: 1,
    team_match_id: 9,
    status: 'PLANNED',
    visibility: 'PUBLIC',
    report_expected: true,
    location: 'Halle',
    description: null,
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
  };

  beforeEach(async () => {
    updateEvent.mockClear();
    await TestBed.configureTestingModule({
      imports: [EventForm],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => '5' } } } },
        {
          provide: EventApiService,
          useValue: {
            getCategories: () => of([{ id: 1, name: 'Mannschaftsspiel', is_active: true }]),
            getEvent: () => of(syncedEvent),
            updateEvent,
            notifyEventChanged: vi.fn(),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(EventForm);
    await fixture.whenStable();
  });

  it('disables externally synchronized fields', () => {
    const component = fixture.componentInstance;
    expect(component.isSynced()).toBe(true);
    expect(component.form.controls.title.disabled).toBe(true);
    expect(component.form.controls.location.disabled).toBe(true);
    expect(component.form.controls.description.enabled).toBe(true);
  });

  it('only patches editorial fields for synchronized events', () => {
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    fixture.componentInstance.form.controls.description.setValue('Spielbericht folgt');
    fixture.componentInstance.submit();

    expect(updateEvent).toHaveBeenCalledWith(5, {
      visibility: 'PUBLIC',
      report_expected: true,
      description: 'Spielbericht folgt',
    });
  });
});
