import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  input,
  output,
  viewChild,
} from '@angular/core';
import { GalleryDetails } from '../../../core/media/gallery-api.service';
import { MediaPreview } from '../../../shared/media-upload/media-preview';

@Component({
  selector: 'app-gallery-image-picker',
  imports: [MediaPreview],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <dialog #dialog aria-labelledby="gallery-picker-title" (cancel)="close($event)">
      <h2 id="gallery-picker-title">Titelbild aus Galerie auswählen</h2>
      <p>{{ gallery().title }}</p>
      @if (!gallery().media_ids.length) {
        <p>Diese Galerie enthält noch keine Bilder.</p>
      }
      <div class="images">
        @for (id of gallery().media_ids; track id; let index = $index) {
          <button
            type="button"
            [attr.aria-label]="'Bild ' + (index + 1) + ' als Titelbild auswählen'"
            [attr.aria-pressed]="selectedId() === id"
            (click)="choose(id)"
          >
            <app-media-preview [mediaId]="id" [eventId]="eventId()" alt="" />
            Bild {{ index + 1 }}{{ selectedId() === id ? ' · ausgewählt' : '' }}
          </button>
        }
      </div>
      <button type="button" (click)="close()">Abbrechen</button>
    </dialog>
  `,
  styles: `
    dialog {
      width: min(800px, calc(100vw - 3rem));
      max-height: 85vh;
      box-sizing: border-box;
      border: 1px solid #667581;
      border-radius: 12px;
      padding: 1.5rem;
    }
    dialog::backdrop {
      background: rgb(0 0 0 / 0.5);
    }
    .images {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 1rem;
      margin: 1rem 0;
    }
    button {
      min-height: 44px;
      padding: 0.65rem 1rem;
      font: inherit;
      color: #20252b;
      background: white;
      border: 1px solid #667581;
      border-radius: 6px;
      cursor: pointer;
    }
    button[aria-pressed='true'] {
      border: 3px solid #226487;
    }
    button:focus-visible {
      outline: 3px solid #226487;
      outline-offset: 3px;
    }
  `,
})
export class GalleryImagePicker implements AfterViewInit {
  readonly gallery = input.required<GalleryDetails>();
  readonly eventId = input.required<number>();
  readonly selectedId = input<number | null>(null);
  readonly selected = output<number>();
  readonly cancelled = output<void>();
  readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');

  ngAfterViewInit(): void {
    this.dialog().nativeElement.showModal();
  }
  choose(id: number): void {
    this.dialog().nativeElement.close();
    this.selected.emit(id);
  }
  close(event?: Event): void {
    event?.preventDefault();
    this.dialog().nativeElement.close();
    this.cancelled.emit();
  }
}
