import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize } from 'rxjs';
import { userError } from '../../admin/users/user-api.service';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-set-password',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './set-password.html',
  styleUrls: ['../../admin/articles/cms.css', './set-password.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SetPassword {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly document = inject(DOCUMENT);
  private token = '';
  readonly available = signal(false);
  readonly busy = signal(false);
  readonly done = signal(false);
  readonly error = signal('');
  readonly form = inject(NonNullableFormBuilder).group({
    password: ['', [Validators.required, Validators.minLength(12), Validators.maxLength(128)]],
    confirmation: ['', Validators.required],
  });
  constructor() {
    const browser = this.document.defaultView;
    this.token = new URLSearchParams(browser?.location.hash.slice(1)).get('token') ?? '';
    this.available.set(this.token.length >= 32);
    if (browser)
      browser.history.replaceState(
        browser.history.state,
        '',
        browser.location.pathname + browser.location.search,
      );
  }
  submit(): void {
    if (this.busy() || !this.available()) return;
    this.error.set('');
    const { password, confirmation } = this.form.getRawValue();
    if (this.form.invalid || password !== confirmation) {
      this.form.markAllAsTouched();
      this.error.set(
        password !== confirmation
          ? 'Die Passwörter stimmen nicht überein.'
          : 'Bitte wähle ein Passwort mit 12 bis 128 Zeichen.',
      );
      return;
    }
    this.busy.set(true);
    this.http
      .post<void>('/api/auth/set-password', { token: this.token, password })
      .pipe(
        finalize(() => this.busy.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: () => {
          this.done.set(true);
          this.token = '';
          this.form.reset();
          this.auth.clearSession();
        },
        error: (error) => this.error.set(userError(error)),
      });
  }
}
