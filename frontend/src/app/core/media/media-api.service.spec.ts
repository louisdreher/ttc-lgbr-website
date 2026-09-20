import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MediaApiService } from './media-api.service';

describe('MediaApiService', () => {
  it('sends multipart without setting a boundary and requests previews as blobs', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const api = TestBed.inject(MediaApiService);
    const http = TestBed.inject(HttpTestingController);
    const file = new File(['image'], 'a.png', { type: 'image/png' });
    api.upload(file).subscribe();
    const upload = http.expectOne('/api/admin/media/images');
    expect(upload.request.body.get('file')).toBe(file);
    expect(upload.request.headers.has('Content-Type')).toBe(false);
    upload.flush({ id: 7 });
    api.image(7).subscribe();
    const preview = http.expectOne('/api/admin/media/images/7');
    expect(preview.request.responseType).toBe('blob');
    preview.flush(new Blob());
    http.verify();
  });
});
