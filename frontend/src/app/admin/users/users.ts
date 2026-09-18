import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, Subject, catchError, finalize, of, switchMap, tap } from 'rxjs';
import { UserApi, userError } from './user-api.service';
import { ManagedUser, USER_ROLES } from './user.models';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-users',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './users.html',
  styleUrls: ['../articles/cms.css', './users.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminUsers {
  readonly api = inject(UserApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  readonly roles = USER_ROLES;
  readonly users = signal<ManagedUser[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly filters = new FormGroup({
    search: new FormControl('', { nonNullable: true }),
    role: new FormControl('', { nonNullable: true }),
    active: new FormControl('', { nonNullable: true }),
  });
  private readonly reload = new Subject<void>();
  constructor() {
    this.reload
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set('');
        }),
        switchMap(() => {
          const f = this.filters.getRawValue();
          return this.api.list(f.search, f.role, f.active, this.offset()).pipe(
            catchError((error) => {
              this.error.set(userError(error));
              return of(null);
            }),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((page) => {
        if (page) {
          if (this.offset() > 0 && this.offset() >= page.total) {
            this.offset.set(Math.floor(Math.max(0, page.total - 1) / 25) * 25);
            this.reload.next();
            return;
          }
          this.users.set(page.items);
          this.total.set(page.total);
        }
        this.loading.set(false);
      });
    this.reload.next();
  }
  search(): void {
    this.offset.set(0);
    this.reload.next();
  }
  page(delta: number): void {
    this.offset.update((value) => Math.max(0, value + delta));
    this.reload.next();
  }
  retry(): void {
    this.reload.next();
  }
  roleSummary(user: ManagedUser): string {
    return (
      user.roles
        .map((value) => this.roles.find((role) => role.value === value)?.label ?? value)
        .join(', ') || 'Keine CMS-Rolle'
    );
  }
  toggleActive(user: ManagedUser): void {
    if (
      !user.is_active ||
      window.confirm(`Zugang für ${user.name} deaktivieren? Bestehende Sitzungen werden beendet.`)
    ) {
      this.run(
        this.api.active(user.id, !user.is_active),
        user.is_active ? 'Zugang deaktiviert.' : 'Zugang aktiviert.',
        user.id,
      );
    }
  }
  sendLink(user: ManagedUser): void {
    if (
      window.confirm(`Passwort-Link an ${user.email} senden? Ein vorheriger Link wird ungültig.`)
    ) {
      this.run(this.api.passwordLink(user.id), `Passwort-Link wurde an ${user.email} gesendet.`);
    }
  }
  delete(user: ManagedUser): void {
    if (
      window.confirm(
        `Benutzerkonto „${user.name}“ endgültig löschen? Mitgliedsdaten bleiben erhalten. Konten mit verknüpften Inhalten können nur deaktiviert werden.`,
      )
    ) {
      this.run(
        this.api.delete(user.id),
        'Benutzerkonto gelöscht. Mitgliedsdaten bleiben erhalten.',
        user.id,
      );
    }
  }
  private run(request: Observable<unknown>, message: string, changedUserId?: number): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.api.notice.set('');
    request
      .pipe(
        finalize(() => this.busy.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: () => {
          this.api.notice.set(message);
          if (changedUserId === this.auth.user()?.id) {
            this.auth
              .loadCurrentUser()
              .pipe(takeUntilDestroyed(this.destroyRef))
              .subscribe({
                next: (me) => {
                  if (!me.roles.includes('ADMIN')) void this.router.navigate(['/intern']);
                  else this.reload.next();
                },
                error: () => {
                  this.auth.clearSession();
                  void this.router.navigate(['/login']);
                },
              });
          } else {
            this.reload.next();
          }
        },
        error: (error) => this.error.set(userError(error)),
      });
  }
}
