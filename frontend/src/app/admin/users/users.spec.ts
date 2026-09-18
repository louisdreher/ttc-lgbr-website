import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { AdminUsers } from './users';

describe('AdminUsers', () => {
  let component: AdminUsers;
  let fixture: ComponentFixture<AdminUsers>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminUsers],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminUsers);
    component = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
    http.expectOne((request) => request.url === '/api/admin/users').flush({ items: [], total: 0 });
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
  afterEach(() => {
    http.verify();
    vi.restoreAllMocks();
  });

  it('sends filters and resets pagination', () => {
    component.offset.set(25);
    component.filters.setValue({ search: 'Anna', role: 'EDITOR', active: 'false' });
    component.search();
    const request = http.expectOne((request) => request.url === '/api/admin/users');
    expect(request.request.params.get('search')).toBe('Anna');
    expect(request.request.params.get('role')).toBe('EDITOR');
    expect(request.request.params.get('active')).toBe('false');
    expect(request.request.params.get('offset')).toBe('0');
    request.flush({ items: [], total: 0 });
  });

  it('shows backend protection errors without hiding the existing rows', async () => {
    const user = {
      id: 1,
      name: 'Admin',
      email: 'admin@example.org',
      roles: ['ADMIN'] as const,
      is_active: true,
      member_id: null,
      member: null,
      created_at: '',
    };
    const row = { ...user, roles: [...user.roles] };
    component.users.set([row]);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    component.toggleActive(row);
    http
      .expectOne('/api/admin/users/1/active')
      .flush({ detail: 'Letzter Administrator' }, { status: 409, statusText: 'Conflict' });
    await fixture.whenStable();
    expect(component.error()).toBe('Letzter Administrator');
    expect(component.users()).toHaveLength(1);
    expect(component.users()[0].is_active).toBe(true);
  });
});
