import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';

export interface UploadedImage {
  id: number;
  mime_type: string;
  file_size: number;
  width: number;
  height: number;
}

@Injectable({ providedIn: 'root' })
export class MediaApiService {
  private readonly http = inject(HttpClient);
  upload(file: File, caption = '') {
    const body = new FormData();
    body.append('file', file);
    if (caption.trim()) body.append('caption', caption.trim());
    return this.http.post<UploadedImage>('/api/admin/media/images', body);
  }
  image(id: number) {
    return this.http.get(`/api/admin/media/images/${id}`, { responseType: 'blob' });
  }
  caption(id: number) {
    return this.http.get<{ caption: string | null }>(`/api/admin/media/images/${id}/caption`);
  }
  updateCaption(id: number, caption: string) {
    return this.http.patch<{ caption: string | null }>(`/api/admin/media/images/${id}/caption`, { caption });
  }
}

export function mediaError(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 413) return 'Die Datei ist zu groß.';
    if (error.status === 422) return 'Das Bildformat oder die Bildgröße wird nicht unterstützt.';
    if (error.status === 401 || error.status === 403) return 'Keine Berechtigung für diesen Upload.';
  }
  return 'Upload fehlgeschlagen. Bitte erneut versuchen.';
}
