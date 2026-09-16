export interface SyncSettings {
  enabled: boolean;
  nightly_hour: number;
  nightly_minute: number;
  result_delay_minutes: number;
  result_retry_minutes: number;
  result_retry_window_hours: number;
  include_tables: boolean;
  include_registrations: boolean;
}

export interface SyncRun {
  kind: 'nightly' | 'manual' | 'match';
  started_at: string;
  match_id: number | null;
  finished_at: string | null;
  status: 'running' | 'succeeded' | 'partial' | 'failed' | 'waiting';
  imported: number;
  skipped: number;
  errors: string[];
}

export interface SyncStatus {
  settings: SyncSettings;
  state: {
    requested: boolean;
    last_nightly_slot: string | null;
    last_nightly_success_at: string | null;
    last_run: SyncRun | null;
    nightly_run: SyncRun | null;
    last_error: string | null;
    last_error_at: string | null;
  };
  heartbeat_at: string | null;
  worker_online: boolean;
  running: boolean;
  stale_run: boolean;
  next_nightly_at: string | null;
  next_match_at: string | null;
}

export interface OutboxMessage {
  event_id: string;
  event_type: string;
  deduplication_key: string;
  occurred_at: string;
  processed_at: string | null;
  attempts: number;
  last_error: string | null;
  next_attempt_at: string | null;
  locked_until: string | null;
  failed_at: string | null;
}

export interface MatchReload {
  team_match_id: number;
  status: 'requested' | 'running' | 'succeeded' | 'failed';
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  last_error: string | null;
}

export interface SyncMatch {
  id: number;
  team_id: number;
  team_name: string;
  opponent_name: string;
  is_home: boolean;
  scheduled_at: string;
  is_completed: boolean;
  details_imported_at: string | null;
  reload: MatchReload | null;
  can_reload: boolean;
  reload_blocked_reason: string | null;
}

export interface SyncMatchOverview {
  imported: SyncMatch[];
  missing_details: SyncMatch[];
  upcoming: SyncMatch[];
}
