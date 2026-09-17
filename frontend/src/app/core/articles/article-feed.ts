import { ArticleFocus } from './article-focus';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ArticleApiService, articleError } from './article-api.service';
import {
  ArticleType,
  ARTICLE_TYPES,
  Page,
  PublicArticle,
  articleTypeLabel,
} from './article.models';

@Component({
  selector: 'app-article-feed',
  imports: [DatePipe, RouterLink, ReactiveFormsModule, ArticleFocus],
  templateUrl: './article-feed.html',
  styleUrls: ['../../admin/articles/cms.css', './reading.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ArticleFeed {
  readonly members = input(false);
  private readonly api = inject(ArticleApiService);
  private readonly destroyRef = inject(DestroyRef);
  readonly page = signal<Page<PublicArticle> | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly types = ARTICLE_TYPES;
  readonly type = new FormControl<ArticleType | ''>('', { nonNullable: true });
  readonly typeLabel = articleTypeLabel;
  ngOnInit(): void {
    this.type.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.load(0));
    this.load(0);
  }
  load(offset = this.page()?.offset ?? 0): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set('');
    this.type.disable({ emitEvent: false });
    this.api
      .published(this.members(), offset, this.type.value)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          this.page.set(page);
          this.loading.set(false);
          this.type.enable({ emitEvent: false });
        },
        error: (error) => {
          this.error.set(articleError(error));
          this.loading.set(false);
          this.type.enable({ emitEvent: false });
        },
      });
  }
}
