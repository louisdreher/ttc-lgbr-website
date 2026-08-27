import { inject } from '@angular/core';
import {
  HttpErrorResponse,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest
} from '@angular/common/http';

import {
  Observable,
  catchError,
  finalize,
  shareReplay,
  switchMap,
  throwError
} from 'rxjs';

import { Router } from '@angular/router';

import { AuthService } from './auth.service';


let refreshRequest$: Observable<string> | null = null;


export const authInterceptor: HttpInterceptorFn = (req, next) => {

  const authService = inject(AuthService);
  const router = inject(Router);


  // Login / Refresh / Logout nicht selbst intercepten.
  if (isAuthRequest(req.url)) {
    return next(req);
  }


  const accessToken = authService.accessToken();

  const authenticatedRequest = accessToken
    ? addAccessToken(req, accessToken)
    : req;


  return next(authenticatedRequest).pipe(

    catchError((error: HttpErrorResponse) => {

      if (error.status !== 401) {
        return throwError(() => error);
      }


      if (refreshRequest$ === null) {

        refreshRequest$ = authService.refreshAccessToken().pipe(

          catchError(refreshError => {

            authService.clearSession();

            void router.navigate(['/login']);

            return throwError(() => refreshError);
          }),

          finalize(() => {
            refreshRequest$ = null;
          }),

          shareReplay({
            bufferSize: 1,
            refCount: false
          })
        );
      }


      return refreshRequest$.pipe(

        switchMap(newAccessToken => {

          const retryRequest = addAccessToken(
            req,
            newAccessToken
          );

          return next(retryRequest);
        })
      );
    })
  );
};


function addAccessToken(
  req: HttpRequest<unknown>,
  accessToken: string
): HttpRequest<unknown> {

  return req.clone({
    setHeaders: {
      Authorization: `Bearer ${accessToken}`
    }
  });
}


function isAuthRequest(url: string): boolean {

  return (
    url.endsWith('/auth/login') ||
    url.endsWith('/auth/refresh') ||
    url.endsWith('/auth/logout')
  );
}