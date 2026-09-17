import { CanDeactivateFn } from '@angular/router';
import type { ArticleEditor } from './article-editor';

export const articleLeaveGuard: CanDeactivateFn<ArticleEditor> = (component) =>
  component.confirmLeave();
