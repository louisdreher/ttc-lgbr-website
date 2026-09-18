import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { AdminArticleCreate } from './create';

describe('AdminArticleCreate', () => {
  let component: AdminArticleCreate;
  let fixture: ComponentFixture<AdminArticleCreate>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
      imports: [AdminArticleCreate],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminArticleCreate);
    component = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
    for (const group of ['team_matches', 'other_events']) {
      http
        .expectOne(
          (request) =>
            request.url.endsWith('/opportunities') && request.params.get('group') === group,
        )
        .flush({
          team_matches: [],
          other_events: [],
          total: group === 'team_matches' ? 40 : 1,
          offset: 0,
          limit: 20,
        });
    }
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
  afterEach(() => http.verify());

  it('paginates matches without reloading or advancing other events', () => {
    component.load('team_matches', 20);
    const request = http.expectOne((request) => request.params.get('group') === 'team_matches');
    expect(request.request.params.get('offset')).toBe('20');
    http.expectNone((request) => request.params.get('group') === 'other_events');
    expect(component.groups[1].loading()).toBe(false);
    request.flush({ team_matches: [], other_events: [], total: 40, offset: 20, limit: 20 });
    expect(component.groups[0].page()?.offset).toBe(20);
    expect(component.groups[1].page()?.offset).toBe(0);
  });
});
