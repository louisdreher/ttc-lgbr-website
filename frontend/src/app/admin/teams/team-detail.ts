import { afterNextRender, ChangeDetectionStrategy, Component, computed, effect, ElementRef, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { DestroyRef, Injector, untracked, viewChildren } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CompetitionApiService, PlayerCandidate, Season, TeamLineup } from '../../core/competition/competition-api.service';
import { PlayerPortrait } from '../../shared/player-portrait/player-portrait';
import { PlayerPicker } from './player-picker';
import { MediaUpload } from '../../shared/media-upload/media-upload';
import { UploadedImage } from '../../core/media/media-api.service';

@Component({
  selector: 'app-team-detail',
  imports: [RouterLink, PlayerPortrait, PlayerPicker, MediaUpload],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './team-detail.html',
  styleUrl: './teams.css',
})
export class TeamDetail {
  private readonly api = inject(CompetitionApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly params = toSignal(this.route.paramMap, { initialValue: this.route.snapshot.paramMap });
  private readonly queryParams = toSignal(this.route.queryParamMap, { initialValue: this.route.snapshot.queryParamMap });
  private readonly heading = viewChild<ElementRef<HTMLHeadingElement>>('heading');
  private readonly reload = signal(0);
  readonly lineup = signal<TeamLineup | null>(null);
  readonly seasons = signal<Season[]>([]);
  readonly season = computed(() => this.seasons().find(item => item.id === this.lineup()?.season_id));
  readonly backSeason = computed(() => {
    const requested = Number(this.queryParams().get('season'));
    return this.lineup()?.season_id ?? (Number.isInteger(requested) && requested > 0 ? requested : null);
  });
  readonly loading = signal(true);
  readonly error = signal('');
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly addButton = viewChild<ElementRef<HTMLButtonElement>>('addButton');
  private readonly candidatesReload = signal(0);
  readonly choosingPlayer = signal(false);
  readonly candidates = signal<PlayerCandidate[]>([]);
  readonly candidatesLoading = signal(false);
  readonly candidatesError = signal('');
  readonly busy = signal(false);
  readonly mutationError = signal('');
  readonly notice = signal('');
  readonly confirmRemoval = signal<number | null>(null);
  readonly imageTarget = signal<{ teamId: number; playerId: number } | null>(null);
  readonly pendingImage = signal<{ teamId: number; playerId: number; mediaId: number } | null>(null);
  readonly imageError = signal('');
  private readonly imageButtons = viewChildren<ElementRef<HTMLButtonElement>>('imageButton');
  private imageFocusAfterLoad: number | null = null;

  constructor() {
    afterNextRender(() => this.heading()?.nativeElement.focus());
    effect((cleanup) => {
      const id = Number(this.params().get('teamId'));
      this.reload();
      if (untracked(this.lineup)?.team_id !== id) {
        this.lineup.set(null);
        this.choosingPlayer.set(false);
        this.confirmRemoval.set(null);
        this.notice.set('');
        this.mutationError.set('');
        this.busy.set(false);
        this.imageTarget.set(null);
        this.pendingImage.set(null);
        this.imageError.set('');
        this.imageFocusAfterLoad = null;
      }
      this.error.set('');
      if (!Number.isInteger(id) || id < 1) {
        this.error.set('Ungültige Mannschaftsnummer.');
        this.loading.set(false);
        return;
      }
      this.loading.set(true);
      const subscription = this.api.lineup(id).subscribe({
        next: lineup => {
          this.lineup.set(lineup);
          this.loading.set(false);
          if (this.imageFocusAfterLoad !== null) {
            this.focusImageButton(this.imageFocusAfterLoad);
            this.imageFocusAfterLoad = null;
          }
        },
        error: error => {
          this.error.set(error.status === 404 ? 'Die Mannschaft wurde nicht gefunden.' : 'Die Aufstellung konnte nicht geladen werden.');
          this.loading.set(false);
        },
      });
      cleanup(() => subscription.unsubscribe());
    });
    effect(cleanup => {
      const subscription = this.api.seasons().subscribe({
        next: seasons => this.seasons.set(seasons),
        error: () => this.seasons.set([]),
      });
      cleanup(() => subscription.unsubscribe());
    });
    effect(cleanup => {
      const open = this.choosingPlayer();
      const teamId = this.lineup()?.team_id;
      this.candidatesReload();
      this.candidates.set([]);
      this.candidatesError.set('');
      if (!open || !teamId) { this.candidatesLoading.set(false); return; }
      this.candidatesLoading.set(true);
      const subscription = this.api.candidates(teamId).subscribe({
        next: candidates => { this.candidates.set(candidates); this.candidatesLoading.set(false); },
        error: () => { this.candidatesError.set('Die Spielerauswahl konnte nicht geladen werden.'); this.candidatesLoading.set(false); },
      });
      cleanup(() => subscription.unsubscribe());
    });
  }

  retry() { this.reload.update(value => value + 1); }
  retryCandidates() { this.candidatesReload.update(value => value + 1); }

  openImageUpload(playerId: number) {
    const teamId = this.lineup()?.team_id;
    if (!teamId || this.busy() || this.loading()) return;
    this.imageError.set('');
    this.pendingImage.set(null);
    this.imageTarget.set({ teamId, playerId });
  }

  cancelImageUpload() {
    const target = this.imageTarget();
    this.imageTarget.set(null);
    if (target) this.focusImageButton(target.playerId);
  }

  imageUploaded(images: UploadedImage[]) {
    const target = this.imageTarget();
    this.imageTarget.set(null);
    if (!target || target.teamId !== this.lineup()?.team_id || !images[0]) return;
    this.pendingImage.set({ ...target, mediaId: images[0].id });
    this.savePlayerImage();
  }

  savePlayerImage() {
    const pending = this.pendingImage();
    if (!pending || this.busy() || pending.teamId !== this.lineup()?.team_id) return;
    this.busy.set(true);
    this.imageError.set('');
    this.notice.set('');
    this.api.setPlayerImage(pending.teamId, pending.playerId, pending.mediaId)
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: () => {
          if (pending.teamId !== this.lineup()?.team_id) return;
          this.busy.set(false);
          this.pendingImage.set(null);
          this.notice.set('Spielerbild ab dieser Mannschaftshalbserie gespeichert.');
          this.imageFocusAfterLoad = pending.playerId;
          this.retry();
        },
        error: (error: HttpErrorResponse) => {
          if (pending.teamId !== this.lineup()?.team_id) return;
          this.busy.set(false);
          this.imageError.set(typeof error.error?.detail === 'string' ? error.error.detail : 'Das Bild wurde hochgeladen, aber die Zuordnung konnte nicht gespeichert werden.');
        },
      });
  }

  private focusImageButton(playerId: number) {
    afterNextRender(() => this.imageButtons().find(button =>
      button.nativeElement.dataset['playerId'] === String(playerId))?.nativeElement.focus(),
      { injector: this.injector });
  }

  openPicker() {
    this.mutationError.set('');
    this.choosingPlayer.set(true);
  }

  closePicker() {
    this.choosingPlayer.set(false);
    afterNextRender(() => this.addButton()?.nativeElement.focus(), { injector: this.injector });
  }

  addPlayer(playerId: number) {
    const teamId = this.lineup()?.team_id;
    if (!teamId || !playerId || this.busy() || this.loading() ||
        !this.candidates().some(player => player.player_id === playerId)) return;
    this.saveAssignment(teamId, playerId, false);
  }

  removePlayer(playerId: number) {
    const teamId = this.lineup()?.team_id;
    if (!teamId || this.busy() || this.loading()) return;
    this.saveAssignment(teamId, playerId, true);
  }

  private saveAssignment(teamId: number, playerId: number, remove: boolean) {
    this.busy.set(true);
    this.mutationError.set('');
    this.notice.set('');
    const request = remove ? this.api.removePlayer(teamId, playerId) : this.api.assignPlayer(teamId, playerId);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        if (this.lineup()?.team_id !== teamId) return;
        this.busy.set(false);
        this.confirmRemoval.set(null);
        this.closePicker();
        this.notice.set(remove ? 'Spieler aus der Mannschaft entfernt.' : 'Spieler zur Mannschaft hinzugefügt.');
        this.retry();
      },
      error: (error: HttpErrorResponse) => {
        if (this.lineup()?.team_id !== teamId) return;
        this.busy.set(false);
        this.mutationError.set(typeof error.error?.detail === 'string' ? error.error.detail : 'Die Zuordnung konnte nicht gespeichert werden. Bitte erneut versuchen.');
      },
    });
  }
}
