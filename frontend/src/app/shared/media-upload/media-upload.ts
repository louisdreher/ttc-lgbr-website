import { AfterViewInit, ChangeDetectionStrategy, Component, DestroyRef, ElementRef, computed, inject, input, output, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';
import { MediaApiService, UploadedImage, mediaError } from '../../core/media/media-api.service';

interface Selection {
  key: number;
  file: File;
  url: string;
  result?: UploadedImage;
  error?: string;
  uploading?: boolean;
}

@Component({
  selector: 'app-media-upload',
  templateUrl: './media-upload.html',
  styleUrl: './media-upload.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MediaUpload implements AfterViewInit {
  readonly maxFiles = input(20);
  readonly completed = output<UploadedImage[]>();
  readonly cancelled = output<void>();
  readonly items = signal<Selection[]>([]);
  readonly busy = signal(false);
  readonly message = signal('');
  readonly dragging = signal(false);
  readonly pending = computed(() => this.items().filter(item => !item.result).length);
  readonly successful = computed(() => this.items().filter(item => item.result).length);
  readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');
  private readonly api = inject(MediaApiService);
  private readonly destroyRef = inject(DestroyRef);
  private key = 0;
  private alive = true;

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.alive = false;
      this.items().forEach(item => URL.revokeObjectURL(item.url));
    });
  }
  ngAfterViewInit(): void { this.dialog().nativeElement.showModal(); }
  choose(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.add(Array.from(input.files ?? []));
    input.value = '';
  }
  drag(event: DragEvent): void {
    event.preventDefault();
    if (!this.busy()) this.dragging.set(true);
  }
  drop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    this.add(Array.from(event.dataTransfer?.files ?? []));
  }
  add(files: File[]): void {
    if (this.busy()) return;
    this.message.set('');
    for (const file of files) {
      if (this.items().length >= this.maxFiles()) {
        this.message.set(`Bitte höchstens ${this.maxFiles()} ${this.maxFiles() === 1 ? 'Bild' : 'Bilder'} auswählen.`);
        break;
      }
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        this.message.set('Bitte JPEG-, PNG- oder WebP-Bilder auswählen.');
        continue;
      }
      if (this.items().some(item => item.file.name === file.name && item.file.size === file.size && item.file.lastModified === file.lastModified)) continue;
      this.items.update(items => [...items, { key: ++this.key, file, url: URL.createObjectURL(file) }]);
    }
  }
  remove(key: number): void {
    if (this.busy()) return;
    const item = this.items().find(item => item.key === key);
    if (item) URL.revokeObjectURL(item.url);
    this.items.update(items => items.filter(item => item.key !== key));
  }
  cancel(event?: Event): void {
    event?.preventDefault();
    if (this.busy()) return;
    this.dialog().nativeElement.close();
    this.cancelled.emit();
  }
  finish(): void {
    this.dialog().nativeElement.close();
    this.completed.emit(this.items().flatMap(item => item.result ? [item.result] : []));
  }
  async upload(): Promise<void> {
    if (this.busy() || !this.pending()) return;
    this.busy.set(true);
    // Sequential requests keep memory use bounded; successes are never uploaded again.
    for (const item of this.items().filter(item => !item.result)) {
      this.update(item.key, { uploading: true, error: undefined });
      try {
        const result = await firstValueFrom(this.api.upload(item.file).pipe(takeUntilDestroyed(this.destroyRef)));
        if (!this.alive) return;
        this.update(item.key, { result, uploading: false });
      } catch (error) {
        if (!this.alive) return;
        this.update(item.key, { error: mediaError(error), uploading: false });
      }
    }
    this.busy.set(false);
    if (!this.pending()) this.finish();
  }
  private update(key: number, changes: Partial<Selection>): void {
    this.items.update(items => items.map(item => item.key === key ? { ...item, ...changes } : item));
  }
}
