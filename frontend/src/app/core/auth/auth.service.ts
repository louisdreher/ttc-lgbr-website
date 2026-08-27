import { computed, inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, finalize, map, of, switchMap, tap, throwError } from 'rxjs';

import {
  CurrentUser,
  LoginCredentials,
  TokenResponse
} from './auth.models';


@Injectable({
  providedIn: 'root'
})
export class AuthService {

  private readonly http = inject(HttpClient);

  private readonly apiUrl = '/api/auth';

  private readonly _accessToken = signal<string | null>(null);
  private readonly _user = signal<CurrentUser | null>(null);

  readonly accessToken = this._accessToken.asReadonly();
  readonly user = this._user.asReadonly();

  readonly isAuthenticated = computed(
    () => this._user() !== null
  );


  login(credentials: LoginCredentials): Observable<CurrentUser> {

    return this.http.post<TokenResponse>(
      `${this.apiUrl}/login`,
      credentials,
      {
        withCredentials: true
      }
    ).pipe(

      tap(response => {
        this._accessToken.set(response.access_token);
      }),

      switchMap(() => this.loadCurrentUser()),

      catchError(error => {
        this.clearSession();
        return throwError(() => error);
      })
    );
  }


  refreshAccessToken(): Observable<string> {

    return this.http.post<TokenResponse>(
      `${this.apiUrl}/refresh`,
      {},
      {
        withCredentials: true
      }
    ).pipe(

      map(response => response.access_token),

      tap(accessToken => {
        this._accessToken.set(accessToken);
      })
    );
  }


  loadCurrentUser(): Observable<CurrentUser> {

    return this.http.get<CurrentUser>(
      `${this.apiUrl}/me`
    ).pipe(

      tap(user => {
        this._user.set(user);
      })
    );
  }


  initialize(): Observable<void> {

    return this.refreshAccessToken().pipe(

      switchMap(() => this.loadCurrentUser()),

      map(() => undefined),

      catchError(() => {
        this.clearSession();

        // Nicht eingeloggt zu sein ist beim App-Start
        // kein Fehler.
        return of(undefined);
      })
    );
  }


  logout(): Observable<void> {

    return this.http.post<void>(
      `${this.apiUrl}/logout`,
      {},
      {
        withCredentials: true
      }
    ).pipe(

      catchError(() => {
        // Auch wenn der Server nicht erreichbar ist,
        // löschen wir den lokalen Login-Zustand.
        return of(undefined);
      }),

      finalize(() => {
        this.clearSession();
      })
    );
  }


  clearSession(): void {
    this._accessToken.set(null);
    this._user.set(null);
  }

  hasAnyRole(...roles: string[]): boolean {
    const user = this._user();

    if (user === null) {
      return false;
    }

    return roles.some(
      role => user.roles.includes(role)
    );
  }

}