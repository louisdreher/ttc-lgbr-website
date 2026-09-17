import { Directive, ElementRef, afterNextRender, inject } from '@angular/core';

/** Move keyboard focus to a newly opened page or validation summary. */
@Directive({ selector: '[articleFocus]', host: { tabindex: '-1' } })
export class ArticleFocus {
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  constructor() {
    afterNextRender(() => this.element.nativeElement.focus({ preventScroll: true }));
  }
}
