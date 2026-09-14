class TeamNotFoundError(ValueError):
    def __init__(self, team_id: int):
        super().__init__(f"Team {team_id} wurde nicht gefunden.")


class PlayerNotFoundError(ValueError):
    def __init__(self, player_id: int):
        super().__init__(f"Spieler {player_id} wurde nicht gefunden.")


class MatchNotFoundError(ValueError):
    def __init__(self, team_match_id: int):
        super().__init__(f"Begegnung {team_match_id} wurde nicht gefunden.")
