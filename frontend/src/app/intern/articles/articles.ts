import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ArticleFeed } from '../../core/articles/article-feed';
@Component({
  selector: 'app-articles',
  imports: [ArticleFeed],
  template: '<app-article-feed [members]="true" />',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InternArticles {}
