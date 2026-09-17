import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { ArticleList } from './article-list';
import { ArticleApiService } from '../../core/articles/article-api.service';
import { articleFixture } from '../../core/articles/article.fixtures';

describe('Article lists', () => {
  function setup(editorial = false) {
    const api = {
      list: vi.fn(() =>
        of({ items: [articleFixture({ status: 'IN_REVIEW' })], total: 1, offset: 0, limit: 20 }),
      ),
    };
    TestBed.configureTestingModule({
      imports: [ArticleList],
      providers: [provideRouter([]), { provide: ArticleApiService, useValue: api }],
    });
    const fixture = TestBed.createComponent(ArticleList);
    fixture.componentRef.setInput('editorial', editorial);
    fixture.detectChanges();
    return { fixture, api, component: fixture.componentInstance };
  }
  it('includes submitted articles in drafts and switches to published', () => {
    const { component, fixture, api } = setup();
    expect(api.list).toHaveBeenCalledWith('mine', ['DRAFT', 'IN_REVIEW'], 0, '', undefined);
    expect(fixture.nativeElement.textContent).toContain('Eingereicht');
    component.selectView('published');
    expect(api.list).toHaveBeenLastCalledWith('mine', ['PUBLISHED'], 0, '', undefined);
  });
  it('uses editorial scope for the editorial page', () => {
    const { api, component, fixture } = setup(true);
    expect(api.list).toHaveBeenCalledWith('editorial', ['IN_REVIEW'], 0, '', undefined);
    expect(component.reviewCount()).toBe(1);
    expect(fixture.nativeElement.textContent).not.toContain('Neuer Beitrag');
    expect(fixture.nativeElement.querySelector('#article-period')).toBeNull();
    component.selectStatus('PUBLISHED');
    const since = api.list.mock.lastCall as unknown as unknown[];
    expect(Date.now() - Date.parse(since[4] as string)).toBeCloseTo(14 * 86400000, -3);
    component.period.set('all');
    component.selectStatus('');
    expect(api.list).toHaveBeenLastCalledWith('editorial', [], 0, '', undefined);
  });
});
