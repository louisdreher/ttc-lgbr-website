import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { ArticleVisibility } from './article.models';

@Component({
  selector: 'app-visibility-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { 'aria-hidden': 'true' },
  template: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      @switch (visibility()) {
        @case ('PUBLIC') {
          <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
        }
        @case ('MEMBERS_ONLY') {
          <circle cx="9" cy="8" r="3" />
          <circle cx="16.5" cy="9" r="2.5" />
          <path d="M3 19c.5-4 2.5-6 6-6s5.5 2 6 6M14 14c3.7-.8 6.2 1 7 5" />
        }
        @case ('HIDDEN') {
          <path
            d="M3 3l18 18M10.5 6.2A12 12 0 0 1 12 6c6.5 0 10 6 10 6a15 15 0 0 1-3 3.7M6.2 6.2C3.5 8 2 12 2 12s3.5 6 10 6c1 0 1.9-.1 2.7-.4M9.9 9.9a3 3 0 0 0 4.2 4.2"
          />
        }
      }
    </svg>
  `,
  styles: `
    :host {
      display: inline-flex;
      align-items: center;
      flex-shrink: 0;
    }
    svg {
      width: 20px;
      height: 20px;
      fill: none;
      stroke: currentColor;
      stroke-width: 1.7;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
  `,
})
export class VisibilityIcon {
  readonly visibility = input.required<ArticleVisibility>();
}
