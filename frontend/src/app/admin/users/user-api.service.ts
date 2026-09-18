import { inject, Injectable, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { ManagedUser, Member, MemberOption, UserPage, UserWrite } from './user.models';

@Injectable({ providedIn: 'root' })
export class UserApi {
  private readonly http = inject(HttpClient);
  private readonly url = '/api/admin/users';
  readonly notice = signal('');
  list(search = '', role = '', active = '', offset = 0) {
    let params = new HttpParams().set('search', search).set('offset', offset).set('limit', 25);
    if (role) params = params.set('role', role);
    if (active) params = params.set('active', active);
    return this.http.get<UserPage>(this.url, { params });
  }
  get(id: number) {
    return this.http.get<ManagedUser>(`${this.url}/${id}`);
  }
  members() {
    return this.http.get<MemberOption[]>(`${this.url}/members`);
  }
  member(id: number) {
    return this.http.get<Member>(`${this.url}/members/${id}`);
  }
  create(data: UserWrite) {
    return this.http.post<{ id: number }>(this.url, data);
  }
  update(id: number, data: UserWrite) {
    return this.http.put<void>(`${this.url}/${id}`, data);
  }
  active(id: number, active: boolean) {
    return this.http.patch<void>(`${this.url}/${id}/active`, { is_active: active });
  }
  delete(id: number) {
    return this.http.delete<void>(`${this.url}/${id}`);
  }
  passwordLink(id: number) {
    return this.http.post<void>(`${this.url}/${id}/password-link`, {});
  }
}

export function userError(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const detail: unknown = error.error?.detail;
    if (typeof detail === 'string') return detail;
    if (error.status === 422)
      return 'Bitte prüfe die Eingaben, insbesondere E-Mail-Adressen und Datumsangaben.';
    if (error.status === 403) return 'Für diese Aktion werden Administratorrechte benötigt.';
  }
  return 'Die Anfrage ist fehlgeschlagen. Bitte versuche es erneut.';
}
