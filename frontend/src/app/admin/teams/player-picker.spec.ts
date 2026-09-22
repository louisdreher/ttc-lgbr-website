import { TestBed } from '@angular/core/testing';
import { PlayerPicker } from './player-picker';

describe('PlayerPicker', () => {
  beforeEach(() => {
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
      configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); },
    });
    Object.defineProperty(HTMLDialogElement.prototype, 'close', {
      configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); },
    });
  });

  async function setup() {
    const fixture = TestBed.createComponent(PlayerPicker);
    fixture.componentRef.setInput('candidates', [
      { player_id: 1, first_name: 'Anna', last_name: 'Test', team_number: 3, rank: '2' },
      { player_id: 2, first_name: 'Ben', last_name: 'Test', team_number: 3, rank: '10' },
    ]);
    await fixture.whenStable();
    return fixture;
  }

  it('opens a dialog with visible rows and filters them directly', async () => {
    const fixture = await setup();
    expect(fixture.nativeElement.querySelector('dialog').open).toBe(true);
    expect(fixture.nativeElement.querySelector('select')).toBeNull();
    expect(fixture.nativeElement.querySelectorAll('li').length).toBe(2);
    const search = fixture.nativeElement.querySelector('input');
    expect(document.activeElement).toBe(search);
    search.value = '3.10';
    search.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelectorAll('li').length).toBe(1);
    expect(fixture.nativeElement.querySelector('li').textContent).toContain('Ben Test');
    let chosen = 0;
    fixture.componentInstance.selected.subscribe(id => chosen = id);
    fixture.nativeElement.querySelector('[aria-label="Ben Test hinzufügen"]').click();
    expect(chosen).toBe(2);
    expect(fixture.nativeElement.querySelector('dialog').open).toBe(true); // close only after save succeeds
  });

  it('supports Escape but prevents closing during save', async () => {
    const fixture = await setup();
    let cancelled = 0;
    fixture.componentInstance.cancelled.subscribe(() => cancelled++);
    fixture.componentRef.setInput('busy', true);
    await fixture.whenStable();
    fixture.nativeElement.querySelector('input').dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    expect(cancelled).toBe(0);
    expect(fixture.nativeElement.querySelector('dialog').open).toBe(true);
    fixture.componentRef.setInput('busy', false);
    await fixture.whenStable();
    fixture.nativeElement.querySelector('dialog').dispatchEvent(new Event('cancel', { cancelable: true }));
    expect(cancelled).toBe(1);
    expect(fixture.nativeElement.querySelector('dialog').open).toBe(false);
  });

  it('shows no-results and save errors inside the dialog', async () => {
    const fixture = await setup();
    fixture.componentInstance.search.setValue('Nobody');
    fixture.componentRef.setInput('saveError', 'Zuordnung nicht erlaubt');
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain('Keine Spieler für diese Suche');
    expect(fixture.nativeElement.querySelector('dialog [role="alert"]').textContent).toContain('Zuordnung nicht erlaubt');
  });
});
