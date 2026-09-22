import { NgOptimizedImage } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MediaPreview } from '../media-upload/media-preview';

@Component({
  selector: 'app-player-portrait',
  imports: [NgOptimizedImage, MediaPreview],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (mediaId(); as id) {
      <app-media-preview [mediaId]="id" [alt]="playerName()" />
    } @else {
      <img ngSrc="/images/player-placeholder.png" width="692" height="865"
        alt="Kein Spielerfoto vorhanden" />
    }
  `,
  styles: `
    :host { display: grid; align-items: center; width: 100%; min-height: 140px; }
    img { display: block; width: 100%; height: auto; object-fit: contain; }
  `,
})
export class PlayerPortrait {
  readonly mediaId = input<number | null>(null);
  readonly playerName = input('Spielerfoto');
}
