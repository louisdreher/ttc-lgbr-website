import { ArticleFocus } from '../../../core/articles/article-focus';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, Subscription, of, switchMap, tap } from 'rxjs';
import { ArticleApiService, articleError } from '../../../core/articles/article-api.service';
import {
  Article,
  ArticleType,
  ArticleVisibility,
  ArticleWrite,
  ARTICLE_TYPES,
  PreparedArticle,
  STATUS_LABELS,
} from '../../../core/articles/article.models';
import { PublicEventApiService } from '../../../pages/events/public-event-api.service';
import { PublicEventCategory } from '../../../pages/events/public-event.models';
import { AuthService } from '../../../core/auth/auth.service';

@Component({
  selector: 'app-article-editor',
  imports: [ReactiveFormsModule, RouterLink, DatePipe, ArticleFocus],
  templateUrl: './article-editor.html',
  styleUrls: ['../cms.css', './article-editor.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(window:beforeunload)': 'beforeUnload($event)' },
})
export class ArticleEditor {
  private readonly api = inject(ArticleApiService);
  private readonly eventApi = inject(PublicEventApiService);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  readonly article = signal<Article | null>(null);
  readonly articleId = signal<number | null>(null);
  readonly eventId = signal<number | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly categories = signal<PublicEventCategory[]>([]);
  readonly categoryError = signal('');
  readonly creatingEvent = signal(false);
  readonly labels = STATUS_LABELS;
  readonly readOnly = computed(
    () => this.article() !== null && !this.article()!.allowed_actions.includes('save'),
  );
  readonly canPublish = computed(() =>
    this.article()
      ? this.article()!.allowed_actions.includes('publish')
      : this.auth.hasAnyRole('ADMIN', 'EDITOR'),
  );
  readonly canSubmit = computed(() =>
    this.article() ? this.article()!.allowed_actions.includes('submit') : true,
  );
  readonly types = ARTICLE_TYPES;
  private coverImageId: number | null = null;
  private request?: Subscription;
  readonly loaded = signal(false);

  readonly form = new FormGroup({
    title: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(255), Validators.pattern(/\S/)],
    }),
    slug: new FormControl('', {
      nonNullable: true,
      validators: [
        Validators.required,
        Validators.maxLength(255),
        Validators.pattern(/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/),
      ],
    }),
    teaser: new FormControl('', { nonNullable: true }),
    content: new FormControl('', { nonNullable: true }),
    article_type: new FormControl<ArticleType>('NEWS', { nonNullable: true }),
    visibility: new FormControl<ArticleVisibility>('PUBLIC', { nonNullable: true }),
    tags: new FormControl('', { nonNullable: true }),
  });
  readonly eventForm = new FormGroup({
    title: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(255), Validators.pattern(/\S/)],
    }),
    starts_at: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    ends_at: new FormControl('', { nonNullable: true }),
    category_id: new FormControl<number | null>(null, Validators.required),
    location: new FormControl('', { nonNullable: true }),
    description: new FormControl('', { nonNullable: true }),
  });

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.load());
  }
  load(): void {
    this.request?.unsubscribe();
    this.loaded.set(false);
    this.error.set('');
    this.loading.set(true);
    const id = this.route.snapshot.paramMap.get('id');
    const event = this.route.snapshot.paramMap.get('eventId');
    let request: Observable<Article | PreparedArticle | null> = of(null);
    if (id !== null) request = this.api.get(Number(id));
    else if (event !== null) request = this.api.prepare(Number(event));
    this.request = request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (data) => {
        this.form.enable();
        this.article.set(null);
        this.articleId.set(null);
        this.eventId.set(null);
        this.form.reset({
          title: '',
          slug: '',
          teaser: '',
          content: '',
          article_type: 'NEWS',
          visibility: 'PUBLIC',
          tags: '',
        });
        if (data) {
          this.form.patchValue({ ...data, tags: data.tags.join(', ') });
          this.eventId.set(data.event_id);
          this.coverImageId = data.cover_image_id;
          if ('id' in data) this.accept(data);
          else {
            this.articleId.set(data.article_id);
            if (!data.editable_fields.includes('article_type'))
              this.form.controls.article_type.disable();
            // Own published articles reached from an old event link use the normal detail view.
            if (data.article_id !== null && data.editable_fields.length === 0) {
              void this.router.navigate(['/admin/articles', data.article_id, 'edit'], {
                replaceUrl: true,
              });
            }
          }
        }
        if (this.form.controls.article_type.value === 'MATCH_REPORT') {
          this.form.controls.article_type.disable();
          this.form.controls.slug.disable();
        }
        this.form.markAsPristine();
        this.loading.set(false);
        this.loaded.set(true);
      },
      error: (error) => {
        this.error.set(articleError(error));
        this.loading.set(false);
      },
    });
  }
  private accept(article: Article): void {
    this.article.set(article);
    this.articleId.set(article.id);
    this.eventId.set(article.event_id);
    this.coverImageId = article.cover_image_id;
    this.form.patchValue({ ...article, tags: article.tags.join(', ') });
    this.form.markAsPristine();
    this.eventForm.markAsPristine();
    this.creatingEvent.set(false);
  }
  setSlug(): void {
    if (
      this.form.controls.article_type.value === 'MATCH_REPORT' ||
      this.articleId() !== null ||
      this.form.controls.slug.dirty
    )
      return;
    this.form.controls.slug.setValue(
      this.form.controls.title.value
        .toLowerCase()
        .replace(/ß/g, 'ss')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, ''),
    );
  }
  toggleEvent(enabled: boolean): void {
    this.creatingEvent.set(enabled);
    this.form.markAsDirty();
    if (enabled && this.categories().length === 0) this.loadCategories();
  }
  loadCategories(): void {
    this.categoryError.set('');
    this.eventApi
      .getCategories()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (categories) => this.categories.set(categories),
        error: (error) => this.categoryError.set(articleError(error)),
      });
  }
  save(action: 'save' | 'submit' | 'publish'): void {
    if (!this.loaded() || this.saving() || this.loading() || this.readOnly()) return;
    if (action === 'publish' && !this.canPublish()) return;
    if (action === 'submit' && !this.canSubmit()) return;
    this.error.set('');
    this.notice.set('');
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.error.set('Bitte gib einen Titel und einen gültigen Linknamen ein.');
      return;
    }
    const raw = this.form.getRawValue();
    if (action !== 'save' && !raw.content.trim()) {
      this.error.set('Zum Einreichen oder Veröffentlichen ist ein Inhalt erforderlich.');
      return;
    }
    const tags = raw.tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    if (tags.length > 30) {
      this.error.set('Bitte verwende höchstens 30 Tags.');
      return;
    }
    const payload: ArticleWrite = {
      ...raw,
      tags,
      event_id: this.eventId(),
      cover_image_id: this.coverImageId,
      new_event: null,
    };
    if (this.creatingEvent()) {
      this.eventForm.markAllAsTouched();
      const event = this.eventForm.getRawValue();
      const start = new Date(event.starts_at);
      const end = event.ends_at ? new Date(event.ends_at) : null;
      if (
        this.eventForm.invalid ||
        event.category_id === null ||
        !Number.isFinite(start.getTime()) ||
        (end !== null && (!Number.isFinite(end.getTime()) || end < start))
      ) {
        this.error.set(
          'Bitte prüfe Titel, Kategorie und Zeitraum des Events. Das Ende darf nicht vor dem Beginn liegen.',
        );
        return;
      }
      payload.new_event = {
        ...event,
        category_id: event.category_id,
        starts_at: start.toISOString(),
        ends_at: end?.toISOString() ?? null,
        location: event.location.trim() || null,
        description: event.description.trim() || null,
      };
    }
    this.saving.set(true);
    this.api
      .save(this.articleId(), payload, action === 'submit')
      .pipe(
        tap((article) => this.accept(article)),
        switchMap((article) => (action === 'publish' ? this.api.publish(article.id) : of(article))),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (article) => {
          this.accept(article);
          this.saving.set(false);
          this.notice.set(
            action === 'publish'
              ? 'Der Beitrag ist veröffentlicht.'
              : action === 'submit'
                ? 'Dein Beitrag ist eingereicht. Du kannst ihn bis zur Veröffentlichung weiter bearbeiten.'
                : 'Dein Beitrag ist gespeichert.',
          );
          if (this.route.snapshot.paramMap.get('id') !== String(article.id)) {
            void this.router.navigate(['/admin/articles', article.id, 'edit'], {
              replaceUrl: true,
            });
          }
        },
        error: (error) => {
          this.saving.set(false);
          this.error.set(articleError(error));
        },
      });
  }
  confirmLeave(): boolean {
    return (
      !(this.form.dirty || (this.creatingEvent() && this.eventForm.dirty)) ||
      window.confirm(
        'Deine Änderungen sind noch nicht gespeichert. Möchtest du die Seite trotzdem verlassen?',
      )
    );
  }
  beforeUnload(event: BeforeUnloadEvent): void {
    if (this.form.dirty || (this.creatingEvent() && this.eventForm.dirty)) {
      event.preventDefault();
      event.returnValue = '';
    }
  }
}
