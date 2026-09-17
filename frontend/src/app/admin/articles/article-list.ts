import { ArticleFocus } from '../../core/articles/article-focus';
import { VisibilityIcon } from '../../core/articles/visibility-icon';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ArticleApiService, articleError } from '../../core/articles/article-api.service';
import {
  Article,
  ArticleStatus,
  ArticleType,
  ArticleVisibility,
  ARTICLE_TYPES,
  Page,
  STATUS_LABELS,
  articleTypeLabel,
} from '../../core/articles/article.models';
import { Observable } from 'rxjs';

@Component({
  selector: 'app-article-list',
  imports: [DatePipe, RouterLink, FormsModule, ArticleFocus, VisibilityIcon],
  templateUrl: './article-list.html',
  styleUrls: ['./cms.css', './article-list.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ArticleList {
  readonly editorial = input(false);
  private readonly api = inject(ArticleApiService);
  private readonly destroyRef = inject(DestroyRef);
  readonly page = signal<Page<Article> | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly busyId = signal<number | null>(null);
  readonly notice = signal('');
  readonly view = signal<'drafts' | 'published'>('drafts');
  readonly status = signal<ArticleStatus | ''>('IN_REVIEW');
  readonly reviewCount = signal<number | null>(null);
  readonly visibilities: ArticleVisibility[] = ['PUBLIC', 'MEMBERS_ONLY', 'HIDDEN'];
  readonly statuses: { value: ArticleStatus | ''; label: string }[] = [
    { value: 'IN_REVIEW', label: 'Eingereicht' },
    { value: 'DRAFT', label: 'Entwürfe' },
    { value: 'PUBLISHED', label: 'Veröffentlicht' },
    { value: 'ARCHIVED', label: 'Archiviert' },
    { value: '', label: 'Alle' },
  ];
  readonly type = signal<ArticleType | ''>('');
  readonly period = signal('14');
  readonly labels = STATUS_LABELS;
  readonly types = ARTICLE_TYPES;
  readonly typeLabel = articleTypeLabel;
  readonly visibilityLabels = {
    PUBLIC: 'Öffentlich',
    MEMBERS_ONLY: 'Nur Mitglieder',
    HIDDEN: 'Verborgen',
  };
  ngOnInit(): void {
    this.load(0);
    if (this.editorial()) this.loadReviewCount();
  }
  private loadReviewCount(): void {
    this.api
      .list('editorial', ['IN_REVIEW'])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => this.reviewCount.set(page.total),
        error: () => this.reviewCount.set(null),
      });
  }
  selectStatus(status: ArticleStatus | ''): void {
    this.status.set(status);
    this.load(0);
  }
  closeMenu(event: FocusEvent, menu: HTMLDetailsElement): void {
    if (!(event.relatedTarget instanceof Node) || !menu.contains(event.relatedTarget))
      menu.open = false;
  }
  selectView(view: 'drafts' | 'published'): void {
    this.view.set(view);
    this.load(0);
  }
  load(offset = this.page()?.offset ?? 0): void {
    if (this.loading()) return;
    const statuses: ArticleStatus[] = this.editorial()
      ? this.status()
        ? [this.status() as ArticleStatus]
        : []
      : this.view() === 'drafts'
        ? ['DRAFT', 'IN_REVIEW']
        : ['PUBLISHED'];
    this.loading.set(true);
    this.error.set('');
    this.api
      .list(
        this.editorial() ? 'editorial' : 'mine',
        statuses,
        offset,
        this.type(),
        this.editorial() && this.status() !== 'IN_REVIEW' && this.period() !== 'all'
          ? new Date(Date.now() - Number(this.period()) * 86400000).toISOString()
          : undefined,
      )
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

  changeVisibility(article: Article, value: ArticleVisibility): void {
    if (!['PUBLIC', 'MEMBERS_ONLY', 'HIDDEN'].includes(value)) return;
    this.run(article, this.api.visibility(article.id, value), 'Sichtbarkeit geändert.');
  }
  publish(article: Article): void {
    this.run(article, this.api.publish(article.id), 'Beitrag veröffentlicht.');
  }
  archive(article: Article): void {
    this.run(article, this.api.archive(article.id), 'Beitrag archiviert.');
  }
  restore(article: Article): void {
    this.run(article, this.api.restore(article.id), 'Beitrag als Entwurf wiederhergestellt.');
  }
  remove(article: Article): void {
    if (
      !window.confirm(
        '„' +
          article.title +
          '“ endgültig löschen? Der zugehörige Event und Medien bleiben erhalten.',
      )
    )
      return;
    this.run(article, this.api.delete(article.id), 'Beitrag gelöscht.');
  }
  private run(
    article: Article,
    request: Observable<Article | void>,
    message: string,
    onError?: () => void,
  ): void {
    if (!this.editorial() || this.busyId() !== null || this.loading()) return;
    this.busyId.set(article.id);
    this.error.set('');
    this.notice.set('');
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.busyId.set(null);
        this.notice.set(message);
        this.loadReviewCount();
        const page = this.page();
        this.load(
          page && page.items.length === 1
            ? Math.max(0, page.offset - page.limit)
            : (page?.offset ?? 0),
        );
      },
      error: (error) => {
        this.busyId.set(null);
        this.error.set(articleError(error));
        onError?.();
      },
    });
  }
}
