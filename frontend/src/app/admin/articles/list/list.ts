import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ArticleList } from '../article-list';
@Component({
  selector: 'app-article-editorial',
  imports: [ArticleList],
  template: '<app-article-list [editorial]="true" />',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminArticleList {}
