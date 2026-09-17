import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ArticleFeed } from '../../core/articles/article-feed';
@Component({
  selector: 'app-news',
  imports: [ArticleFeed],
  template: '<app-article-feed />',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class News {}
