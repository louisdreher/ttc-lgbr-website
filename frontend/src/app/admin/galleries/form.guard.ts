import { CanDeactivateFn } from '@angular/router';
import type { GalleryForm } from './form';
export const galleryLeaveGuard: CanDeactivateFn<GalleryForm> = (component) =>
  component.confirmLeave();
