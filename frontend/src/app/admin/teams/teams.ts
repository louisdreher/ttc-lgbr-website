import { afterNextRender, ChangeDetectionStrategy, Component, computed, effect, ElementRef, inject, signal, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { CompetitionApiService, Season, Team } from '../../core/competition/competition-api.service';

@Component({
  selector: 'app-teams',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './teams.html',
  styleUrl: './teams.css',
})
export class AdminTeams {
  private readonly api = inject(CompetitionApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly params = toSignal(this.route.queryParamMap, { initialValue: this.route.snapshot.queryParamMap });
  private readonly heading = viewChild<ElementRef<HTMLHeadingElement>>('heading');
  readonly seasons = signal<Season[]>([]);
  readonly seasonId = computed(() => {
    const requested = Number(this.params().get('season'));
    return this.seasons().find(season => season.id === requested)?.id ?? this.seasons()[0]?.id ?? null;
  });
  readonly teams = signal<Team[]>([]);
  readonly seasonsLoading = signal(true);
  readonly teamsLoading = signal(false);
  readonly seasonError = signal('');
  readonly teamError = signal('');
  private readonly reload = signal(0);
  private readonly teamsReload = signal(0);

  constructor() {
    afterNextRender(() => this.heading()?.nativeElement.focus());
    effect((cleanup) => {
      this.reload();
      this.seasonsLoading.set(true);
      this.seasonError.set('');
      const subscription = this.api.seasons().subscribe({
        next: (seasons) => { this.seasons.set(seasons); this.seasonsLoading.set(false); },
        error: () => { this.seasonError.set('Saisons konnten nicht geladen werden.'); this.seasonsLoading.set(false); },
      });
      cleanup(() => subscription.unsubscribe());
    });
    effect((cleanup) => {
      const id = this.seasonId();
      this.teamsReload();
      this.teams.set([]);
      this.teamError.set('');
      if (id === null) { this.teamsLoading.set(false); return; }
      this.teamsLoading.set(true);
      const subscription = this.api.teams(id).subscribe({
        next: (teams) => { this.teams.set(teams); this.teamsLoading.set(false); },
        error: () => { this.teamError.set('Mannschaften konnten nicht geladen werden.'); this.teamsLoading.set(false); },
      });
      cleanup(() => subscription.unsubscribe());
    });
  }

  selectSeason(id: number) {
    void this.router.navigate([], { relativeTo: this.route, queryParams: { season: id }, queryParamsHandling: 'merge' });
  }
  retrySeasons() { this.reload.update(value => value + 1); }
  retryTeams() { this.teamsReload.update(value => value + 1); }
}
