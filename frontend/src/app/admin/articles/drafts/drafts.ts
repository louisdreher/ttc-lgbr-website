import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ArticleList } from '../article-list';
@Component({
  selector: 'app-drafts',
  imports: [ArticleList],
  template: '<app-article-list />',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminArticleDrafts {}
