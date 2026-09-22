import { AfterViewInit, ChangeDetectionStrategy, Component, computed, ElementRef, input, output, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { PlayerCandidate } from '../../core/competition/competition-api.service';

@Component({
  selector: 'app-player-picker',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './player-picker.html',
  styleUrl: './player-picker.css',
})
export class PlayerPicker implements AfterViewInit {
  readonly candidates = input.required<PlayerCandidate[]>();
  readonly loading = input(false);
  readonly busy = input(false);
  readonly error = input('');
  readonly saveError = input('');
  readonly selected = output<number>();
  readonly cancelled = output<void>();
  readonly retry = output<void>();
  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');
  private readonly searchInput = viewChild.required<ElementRef<HTMLInputElement>>('searchInput');
  readonly search = new FormControl('', { nonNullable: true });
  private readonly searchText = toSignal(this.search.valueChanges, { initialValue: '' });
  readonly filteredCandidates = computed(() => {
    const search = this.searchText().trim().toLocaleLowerCase('de');
    return this.candidates().filter(player =>
      `${player.first_name} ${player.last_name} ${player.team_number}.${player.rank}`.toLocaleLowerCase('de').includes(search));
  });

  ngAfterViewInit() {
    this.dialog().nativeElement.showModal();
    this.searchInput().nativeElement.focus();
  }

  choose(playerId: number) {
    if (!this.busy() && !this.loading()) this.selected.emit(playerId);
  }

  close(event?: Event) {
    event?.preventDefault();
    if (this.busy()) return;
    this.dialog().nativeElement.close();
    this.cancelled.emit();
  }
}
