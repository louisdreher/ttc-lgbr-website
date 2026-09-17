import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ArticleApiService } from './article-api.service';
import { ArticleWrite } from './article.models';

describe('Article API contract', () => {
  let api: ArticleApiService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(ArticleApiService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());
  it('sends the time filter to the backend', () => {
    api.list('editorial', [], 0, '', '2026-09-03T12:00:00Z').subscribe();
    const request = http.expectOne((req) => req.url === '/api/admin/articles');
    expect(request.request.params.get('updated_since')).toBe('2026-09-03T12:00:00Z');
    request.flush({});
  });
  it('requests both unpublished statuses and paginates on the server', () => {
    api.list('mine', ['DRAFT', 'IN_REVIEW'], 20).subscribe();
    const request = http.expectOne((req) => req.url === '/api/admin/articles');
    expect(request.request.params.getAll('status')).toEqual(['DRAFT', 'IN_REVIEW']);
    expect(request.request.params.get('offset')).toBe('20');
    request.flush({});
  });
  it('prepares without writes and submits the full form including event and media references', () => {
    api.prepare(2).subscribe();
    const prepare = http.expectOne('/api/admin/articles/prepare/2');
    expect(prepare.request.method).toBe('GET');
    prepare.flush({});
    const data: ArticleWrite = {
      title: 'Fest',
      slug: 'fest',
      teaser: 'T',
      content: 'C',
      article_type: 'EVENT_REPORT',
      visibility: 'PUBLIC',
      event_id: 2,
      tags: ['verein'],
      cover_image_id: 4,
      new_event: null,
    };
    api.save(3, data, true).subscribe();
    const submit = http.expectOne('/api/admin/articles/3/submit');
    expect(submit.request.method).toBe('POST');
    expect(submit.request.body).toEqual(data);
    submit.flush({});
  });
  it('keeps public and member read endpoints separate', () => {
    api.read('fest', false).subscribe();
    http.expectOne('/api/articles/fest').flush({});
    api.read('fest', true).subscribe();
    http.expectOne('/api/intern/articles/fest').flush({});
  });
});
