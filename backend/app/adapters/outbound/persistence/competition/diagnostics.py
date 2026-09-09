from sqlalchemy import text


class SqlRegistrationReportReader:
    def __init__(self, engine):
        self.engine = engine

    def read(self) -> tuple[list[dict], list[dict]]:
        summary_query = text("""
            SELECT s.id AS season_id, s.start_year, s.end_year, s.half,
                COUNT(DISTINCT t.id) AS teams,
                COUNT(DISTINCT CASE WHEN t.team_number IS NOT NULL THEN t.id END)
                    AS teams_with_number,
                COUNT(DISTINCT tm.team_id) AS teams_with_memberships,
                COUNT(tm.player_id) AS memberships,
                COUNT(DISTINCT tm.player_id) AS players
            FROM season s
            LEFT JOIN team t ON t.season_id = s.id
            LEFT JOIN team_membership tm ON tm.team_id = t.id
            GROUP BY s.id, s.start_year, s.end_year, s.half
            ORDER BY s.start_year, s.half
        """)
        details_query = text("""
            SELECT s.start_year, s.end_year, s.half, t.id AS team_id, t.name,
                t.mytt_team_id, t.team_number, COUNT(tm.player_id) AS memberships
            FROM team t
            JOIN season s ON s.id = t.season_id
            LEFT JOIN team_membership tm ON tm.team_id = t.id
            GROUP BY s.start_year, s.end_year, s.half, t.id, t.name,
                t.mytt_team_id, t.team_number
            HAVING t.team_number IS NULL OR COUNT(tm.player_id) = 0
            ORDER BY s.start_year, s.half, t.name
        """)
        with self.engine.connect() as connection:
            summary = connection.execute(summary_query).mappings().all()
            details = connection.execute(details_query).mappings().all()
        return [dict(row) for row in summary], [dict(row) for row in details]
