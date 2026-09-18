import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { SetPassword } from './set-password';

describe('SetPassword', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    history.replaceState({}, '', '/passwort-festlegen#token=' + 't'.repeat(43));
    TestBed.configureTestingModule({
      imports: [SetPassword],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.verify();
    history.replaceState({}, '', '/');
  });
  it('removes the token from the URL and rejects mismatched passwords', () => {
    const component = TestBed.createComponent(SetPassword).componentInstance;
    expect(location.hash).toBe('');
    component.form.setValue({ password: 'a-secure-password', confirmation: 'different-password' });
    component.submit();
    expect(component.error()).toContain('nicht überein');
    http.expectNone('/api/auth/set-password');
  });
  it('submits the token once and clears password fields on success', () => {
    const component = TestBed.createComponent(SetPassword).componentInstance;
    component.form.setValue({ password: 'a-secure-password', confirmation: 'a-secure-password' });
    component.submit();
    const request = http.expectOne('/api/auth/set-password');
    expect(request.request.body.token).toBe('t'.repeat(43));
    request.flush(null);
    expect(component.done()).toBe(true);
    expect(component.form.controls.password.value).toBe('');
  });
});
