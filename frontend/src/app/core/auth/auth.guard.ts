import { inject } from '@angular/core';
import {
  CanActivateFn,
  Router
} from '@angular/router';

import { AuthService } from './auth.service';


export const authGuard: CanActivateFn = (
  route,
  state
) => {

  const authService = inject(AuthService);
  const router = inject(Router);


  if (authService.isAuthenticated()) {
    return true;
  }


  return router.createUrlTree(
    ['/login'],
    {
      queryParams: {
        returnUrl: state.url
      }
    }
  );
};

export const roleGuard = (
  ...allowedRoles: string[]
): CanActivateFn => {

  return () => {

    const authService = inject(AuthService);
    const router = inject(Router);

    const user = authService.user();


    if (user === null) {
      return router.createUrlTree(['/login']);
    }


    const hasRole = allowedRoles.some(
      role => user.roles.includes(role)
    );


    if (hasRole) {
      return true;
    }


    return router.createUrlTree(['/']);
  };
};