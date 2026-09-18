import { CanDeactivateFn } from '@angular/router';
import type { UserForm } from './user-form';
export const userFormLeaveGuard: CanDeactivateFn<UserForm> = (component) => component.canLeave();
