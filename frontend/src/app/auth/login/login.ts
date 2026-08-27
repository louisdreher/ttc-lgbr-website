import { Component, inject, signal } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';

import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators
} from '@angular/forms';


@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {

  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly isLoading = signal(false);
  readonly loginError = signal<string | null>(null);


  loginForm = new FormGroup({

    email: new FormControl('', {
      nonNullable: true,
      validators: [
        Validators.required,
        Validators.email
      ]
    }),

    password: new FormControl('', {
      nonNullable: true,
      validators: [
        Validators.required
      ]
    }),

  });


  onSubmit(): void {

    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }

    this.isLoading.set(true);
    this.loginError.set(null);

    const credentials = this.loginForm.getRawValue();

    this.authService.login(credentials).subscribe({

      next: () => {

        this.isLoading.set(false);

        const returnUrl =
          this.route.snapshot.queryParamMap.get('returnUrl');

        void this.router.navigateByUrl(
          returnUrl ?? '/intern'
        );
      },

      error: () => {

        this.isLoading.set(false);

        this.loginError.set(
          'E-Mail-Adresse oder Passwort ist falsch.'
        );
      }

    });
  }
}