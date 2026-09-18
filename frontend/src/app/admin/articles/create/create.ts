import { ArticleFocus } from '../../../core/articles/article-focus';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ArticleApiService, articleError } from '../../../core/articles/article-api.service';
import { Opportunities, OpportunityGroup } from '../../../core/articles/article.models';

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
  readonly groups = [
    {
      key: 'team_matches' as const,
      title: 'Mannschaftsspiele',
      page: signal<Opportunities | null>(null),
      loading: signal(false),
      error: signal(''),
    },
    {
      key: 'other_events' as const,
      title: 'Andere Events',
      page: signal<Opportunities | null>(null),
      loading: signal(false),
      error: signal(''),
    },
  ];
  constructor() {
    for (const group of this.groups) this.load(group.key);
  }
  load(key: OpportunityGroup, offset?: number): void {
    const group = this.groups.find((group) => group.key === key)!;
    if (group.loading()) return;
    group.loading.set(true);
    group.error.set('');
    this.api
      .opportunities(offset ?? group.page()?.offset ?? 0, key)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          group.page.set(page);
          group.loading.set(false);
        },
        error: (error) => {
          group.error.set(articleError(error));
          group.loading.set(false);
        },
      });
  }
}
