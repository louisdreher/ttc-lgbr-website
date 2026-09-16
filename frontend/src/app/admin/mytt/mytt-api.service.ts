import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { OutboxMessage, SyncSettings, SyncStatus } from './mytt.models';

@Injectable({ providedIn: 'root' })
export class MyttApiService {
  private readonly http = inject(HttpClient);
  private readonly url = '/api/admin/mytt';

  getStatus() { return this.http.get<SyncStatus>(`${this.url}/status`); }
  getSettings() { return this.http.get<SyncSettings>(`${this.url}/settings`); }
  saveSettings(settings: SyncSettings) {
    return this.http.put<SyncSettings>(`${this.url}/settings`, settings);
  }
  requestSync() { return this.http.post<{ requested: boolean }>(`${this.url}/sync`, {}); }
  getOutbox() {
    return this.http.get<OutboxMessage[]>(`${this.url}/outbox`, { params: { limit: 20 } });
  }
  retry(eventId: string) {
    return this.http.post<void>(`${this.url}/outbox/${encodeURIComponent(eventId)}/retry`, {});
  }
}
