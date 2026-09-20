import { TestBed } from '@angular/core/testing';
import { of, Subject, throwError } from 'rxjs';
import { MediaUpload } from './media-upload';
import { MediaApiService, UploadedImage } from '../../core/media/media-api.service';

describe('MediaUpload', () => {
  const result: UploadedImage = { id: 42, width: 10, height: 10, file_size: 50, mime_type: 'image/webp' };
  function setup(maxFiles = 20) {
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: vi.fn() });
    Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: vi.fn() });
    const api = { upload: vi.fn(() => of(result)) };
    TestBed.configureTestingModule({ providers: [{ provide: MediaApiService, useValue: api }] });
    const fixture = TestBed.createComponent(MediaUpload);
    fixture.componentRef.setInput('maxFiles', maxFiles);
    fixture.detectChanges();
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    vi.spyOn(URL, 'revokeObjectURL');
    return { fixture, component: fixture.componentInstance, api };
  }
  const file = (name: string) => new File(['image'], name, { type: 'image/png' });

  it('selects locally, removes previews and cancels without uploading', () => {
    const { component, api } = setup();
    component.add([file('one.png'), file('two.png')]);
    expect(component.items()).toHaveLength(2);
    component.remove(component.items()[0].key);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test');
    component.cancel();
    expect(api.upload).not.toHaveBeenCalled();
  });
  it('enforces single selection and rejects unsupported formats', () => {
    const { component } = setup(1);
    component.add([new File(['text'], 'test.txt', { type: 'text/plain' })]);
    expect(component.items()).toHaveLength(0);
    component.add([file('one.png'), file('two.png')]);
    expect(component.items()).toHaveLength(1);
    expect(component.message()).toContain('höchstens 1');
  });
  it('keeps successes and retries only failed files', async () => {
    const { component, api } = setup();
    const done = vi.fn();
    component.completed.subscribe(done);
    api.upload.mockReturnValueOnce(of(result)).mockReturnValueOnce(throwError(() => new Error()));
    component.add([file('one.png'), file('two.png')]);
    await component.upload();
    expect(component.successful()).toBe(1);
    expect(done).not.toHaveBeenCalled();
    await component.upload();
    expect(api.upload).toHaveBeenCalledTimes(3);
    expect(done).toHaveBeenCalledWith([result, result]);
  });
  it('blocks close and removal during an active upload', async () => {
    const { component, api } = setup();
    const request = new Subject<UploadedImage>();
    api.upload.mockReturnValue(request);
    const cancelled = vi.fn();
    component.cancelled.subscribe(cancelled);
    component.add([file('one.png')]);
    const pending = component.upload();
    component.cancel();
    component.remove(component.items()[0].key);
    expect(cancelled).not.toHaveBeenCalled();
    expect(component.items()).toHaveLength(1);
    request.next(result);
    await pending;
  });
});
