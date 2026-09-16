import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { ActivatedRouteSnapshot, CanActivateFn, provideRouter, Router, RouterStateSnapshot } from '@angular/router';
import { routes } from '../../app.routes';
import { AuthService } from '../../core/auth/auth.service';
import { AdminSidebarComponent } from '../../layout/admin-sidebar/admin-sidebar';

describe('MyTischtennis access', () => {
  const user = signal<{ roles: string[] } | null>(null);
  beforeEach(() => {
    user.set(null);
    TestBed.configureTestingModule({
      imports: [AdminSidebarComponent],
      providers: [provideRouter(routes), { provide: AuthService, useValue: {
        user, isAuthenticated: () => user() !== null,
        hasAnyRole: (...roles: string[]) => roles.some(role => user()?.roles.includes(role)),
      } }],
    });
  });

  it('lazy loads the ADMIN-only route and rejects other roles and anonymous users', () => {
    const route = routes.find(route => route.path === 'admin')!.children!.find(route => route.path === 'mytt')!;
    expect(route.loadComponent).toBeDefined();
    const guard = route.canActivate![0] as CanActivateFn;
    const check = () => TestBed.runInInjectionContext(() => guard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot));
    const router = TestBed.inject(Router);
    expect(check()).toEqual(router.createUrlTree(['/login']));
    for (const role of ['EDITOR', 'TEAM_REPORTER', 'MEMBER']) {
      user.set({ roles: [role] });
      expect(check()).toEqual(router.createUrlTree(['/']));
    }
    user.set({ roles: ['ADMIN'] });
    expect(check()).toBe(true);
  });

  it('shows navigation only to admins', () => {
    const fixture = TestBed.createComponent(AdminSidebarComponent);
    user.set({ roles: ['EDITOR'] });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('a[href="/admin/mytt"]')).toBeNull();
    user.set({ roles: ['ADMIN'] });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('a[href="/admin/mytt"]').textContent).toContain('MyTischtennis');
  });
});
