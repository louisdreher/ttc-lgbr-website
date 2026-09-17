import { ArticleFocus } from './article-focus';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ArticleApiService, articleError } from './article-api.service';
import { PublicArticle, articleTypeLabel } from './article.models';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-article-detail',
  imports: [DatePipe, RouterLink, ArticleFocus],
  template: ` <a [routerLink]="members ? '/intern/articles' : '/news'">← Alle Beiträge</a>
    @if (loading()) {
      <p role="status">Beitrag wird geladen …</p>
    }
    @if (error()) {
      <p class="error" role="alert" articleFocus>{{ error() }}</p>
      <button type="button" (click)="load()">Erneut versuchen</button>
    }
    @if (article(); as article) {
      <article>
        <header class="heading">
          <p class="eyebrow">{{ typeLabel(article.article_type) }}</p>
          <h1 articleFocus>{{ article.title }}</h1>
          <div class="meta">
            <span>{{ article.author_name }}</span
            ><time [attr.datetime]="article.published_at">{{
              article.published_at | date: 'dd.MM.yyyy'
            }}</time>
          </div>
        </header>
        <p class="teaser">{{ article.teaser }}</p>
        <div class="read-content">{{ article.content }}</div>
        @if (article.tags.length) {
          <p class="meta">{{ article.tags.join(' · ') }}</p>
        }
      </article>
    }`,
  styleUrls: ['../../admin/articles/cms.css', './reading.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ArticleDetail {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(ArticleApiService);
  private readonly destroyRef = inject(DestroyRef);
  private request?: Subscription;
  readonly members = this.route.snapshot.data['members'] === true;
  readonly article = signal<PublicArticle | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly typeLabel = articleTypeLabel;
  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.load());
  }
  load(): void {
    this.request?.unsubscribe();
    this.article.set(null);
    this.loading.set(true);
    this.error.set('');
    this.request = this.api
      .read(this.route.snapshot.paramMap.get('slug') ?? '', this.members)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (article) => {
          this.article.set(article);
          this.loading.set(false);
        },
        error: (error) => {
          this.error.set(articleError(error));
          this.loading.set(false);
        },
      });
  }
}
