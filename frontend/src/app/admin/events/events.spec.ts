import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { AdminEvents } from './events';
import { EventApiService } from './event-api.service';

describe('AdminEvents', () => {
  let component: AdminEvents;
  let fixture: ComponentFixture<AdminEvents>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminEvents],
      providers: [
        provideRouter([]),
        {
          provide: EventApiService,
          useValue: {
            getEvents: () =>
              of([
                {
                  id: 1,
                  title: 'Vereinsabend',
                  starts_at: '2026-09-01T18:00:00Z',
                  category_id: 2,
                  status: 'PLANNED',
                  team_match_id: null,
                },
              ]),
            getCategories: () => of([{ id: 2, name: 'Verein', slug: 'verein', is_active: true }]),
            getEventYears: () => of([2026]),
            eventsChanged: signal(0),
            categoryCreated: signal(null),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminEvents);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('renders loaded events with their category', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Vereinsabend');
    expect(fixture.nativeElement.textContent).toContain('Verein');
  });
});
