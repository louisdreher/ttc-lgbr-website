import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface Season { id: number; start_year: number; end_year: number; half: 'vr' | 'rr'; }
export interface Team { id: number; name: string; team_number: number | null; category: string | null; }
export interface PlayerCandidate {
  player_id: number; first_name: string; last_name: string;
  team_number: number; rank: string;
}
export interface TeamLineup {
  team_id: number;
  team_name: string;
  season_id: number;
  category: string | null;
  players: { player_id: number; first_name: string; last_name: string;
    position: number | null; status: string | null; media_id: number | null }[];
}

@Injectable({ providedIn: 'root' })
export class CompetitionApiService {
  private readonly http = inject(HttpClient);
  seasons() { return this.http.get<Season[]>('/api/competition/seasons'); }
  teams(seasonId: number) {
    return this.http.get<Team[]>('/api/competition/teams', { params: { season_id: seasonId } });
  }
  lineup(teamId: number) {
    return this.http.get<TeamLineup>(`/api/competition/teams/${teamId}/lineup`);
  }
  candidates(teamId: number) {
    return this.http.get<PlayerCandidate[]>(`/api/competition/teams/${teamId}/candidates`);
  }
  assignPlayer(teamId: number, playerId: number) {
    return this.http.put<void>(`/api/competition/teams/${teamId}/lineup/${playerId}`, null);
  }
  removePlayer(teamId: number, playerId: number) {
    return this.http.delete<void>(`/api/competition/teams/${teamId}/lineup/${playerId}`);
  }
  setPlayerImage(teamId: number, playerId: number, mediaId: number) {
    return this.http.put<void>(`/api/competition/teams/${teamId}/lineup/${playerId}/image`, { media_id: mediaId });
  }
}
