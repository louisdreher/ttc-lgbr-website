import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { vi } from 'vitest';
import { UserForm } from './user-form';
import { UserApi } from '../user-api.service';

describe('UserForm', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [UserForm],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.verify();
    vi.restoreAllMocks();
  });

  function setup() {
    const fixture = TestBed.createComponent(UserForm);
    http.expectOne('/api/admin/users/members').flush([]);
    return fixture.componentInstance;
  }

  it('does not submit an incomplete form', () => {
    const form = setup();
    form.submit();
    expect(form.error()).toContain('Pflichtfelder');
    http.expectNone('/api/admin/users');
  });

  it('saves member and account together and reports invitation failure without a second create', () => {
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const form = setup();
    form.form.patchValue({
      name: 'Anna',
      email: 'anna@example.org',
      member: { first_name: 'Anna', last_name: 'Weber' },
    });
    form.submit();
    const create = http.expectOne('/api/admin/users');
    expect(create.request.body.member.first_name).toBe('Anna');
    expect(create.request.body.member.birth_date).toBeNull();
    expect(create.request.body).not.toHaveProperty('password');
    create.flush({ id: 9 });
    http
      .expectOne('/api/admin/users/9/password-link')
      .flush({ detail: 'SMTP fehlt' }, { status: 503, statusText: 'Unavailable' });
    expect(TestBed.inject(UserApi).notice()).toContain(
      'Benutzer angelegt. Einladung nicht versendet: SMTP fehlt',
    );
    expect(navigate).toHaveBeenCalledWith(['/admin/users']);
    expect(form.form.pristine).toBe(true);
  });

  it('can create a standalone account without sending an invitation', () => {
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const form = setup();
    form.form.patchValue({
      name: 'Anna',
      email: 'anna@example.org',
      memberMode: 'none',
      sendInvitation: false,
    });
    form.submit();
    const create = http.expectOne('/api/admin/users');
    expect(create.request.body.member).toBeNull();
    create.flush({ id: 9 });
    http.expectNone('/api/admin/users/9/password-link');
  });
});
