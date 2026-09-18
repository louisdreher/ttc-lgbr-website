import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import {
  Article,
  ArticleStatus,
  ArticleType,
  ArticleVisibility,
  ArticleWrite,
  Opportunities,
  OpportunityGroup,
  Page,
  PreparedArticle,
  PublicArticle,
} from './article.models';

@Injectable({ providedIn: 'root' })
export class ArticleApiService {
  private readonly http = inject(HttpClient);
  private readonly cms = '/api/admin/articles';
  list(
    scope: 'mine' | 'editorial',
    statuses: ArticleStatus[],
    offset = 0,
    type: ArticleType | '' = '',
    updatedSince?: string,
  ) {
    let params = new HttpParams().set('scope', scope).set('offset', offset).set('limit', 20);
    for (const status of statuses) params = params.append('status', status);
    if (type) params = params.set('article_type', type);
    if (updatedSince) params = params.set('updated_since', updatedSince);
    return this.http.get<Page<Article>>(this.cms, { params });
  }
  opportunities(offset = 0, group?: OpportunityGroup) {
    return this.http.get<Opportunities>(this.cms + '/opportunities', {
      params: { offset, limit: 20, ...(group ? { group } : {}) },
    });
  }
  prepare(eventId: number) {
    return this.http.get<PreparedArticle>(this.cms + '/prepare/' + eventId);
  }
  get(id: number) {
    return this.http.get<Article>(this.cms + '/' + id);
  }
  save(id: number | null, data: ArticleWrite, submit = false) {
    if (submit)
      return this.http.post<Article>(
        this.cms + (id === null ? '/submit' : '/' + id + '/submit'),
        data,
      );
    return id === null
      ? this.http.post<Article>(this.cms + '/save', data)
      : this.http.put<Article>(this.cms + '/' + id, data);
  }
  publish(id: number) {
    return this.http.post<Article>(this.cms + '/' + id + '/publish', {});
  }
  visibility(id: number, visibility: ArticleVisibility) {
    return this.http.patch<Article>(this.cms + '/' + id + '/visibility', { visibility });
  }
  archive(id: number) {
    return this.http.post<Article>(this.cms + '/' + id + '/archive', {});
  }
  restore(id: number) {
    return this.http.post<Article>(this.cms + '/' + id + '/restore', {});
  }
  delete(id: number) {
    return this.http.delete<void>(this.cms + '/' + id);
  }
  published(members: boolean, offset = 0, type: ArticleType | '' = '') {
    let params = new HttpParams().set('offset', offset).set('limit', 12);
    if (type) params = params.set('article_type', type);
    return this.http.get<Page<PublicArticle>>(members ? '/api/intern/articles' : '/api/articles', {
      params,
    });
  }
  read(slug: string, members: boolean) {
    return this.http.get<PublicArticle>(
      (members ? '/api/intern/articles/' : '/api/articles/') + encodeURIComponent(slug),
    );
  }
}
export function articleError(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 409)
      return 'Der Beitrag wurde inzwischen übernommen oder der Linkname ist bereits vergeben. Deine Eingaben bleiben erhalten. Bitte prüfe den aktuellen Stand.';
    if (error.status === 403) return 'Du hast für diese Aktion keine Berechtigung mehr.';
    if (error.status === 404) return 'Dieser Beitrag oder Termin ist nicht verfügbar.';
    if (typeof error.error?.detail === 'string') return error.error.detail;
    if (error.status === 422) return 'Bitte prüfe die Eingaben. Einige Angaben sind ungültig.';
  }
  return 'Die Anfrage ist fehlgeschlagen. Bitte versuche es erneut.';
}
