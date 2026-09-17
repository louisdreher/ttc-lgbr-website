import { ArticleFocus } from '../../../core/articles/article-focus';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ArticleApiService, articleError } from '../../../core/articles/article-api.service';
import { Opportunities } from '../../../core/articles/article.models';

@Component({
  selector: 'app-article-create',
  imports: [RouterLink, DatePipe, ArticleFocus],
  templateUrl: './create.html',
  styleUrl: '../cms.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminArticleCreate {
  private readonly api = inject(ArticleApiService);
  private readonly destroyRef = inject(DestroyRef);
  readonly page = signal<Opportunities | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  constructor() {
    this.load();
  }
  load(offset = this.page()?.offset ?? 0): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set('');
    this.api
      .opportunities(offset)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          this.page.set(page);
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(articleError(error));
          this.loading.set(false);
        },
      });
  }
}
