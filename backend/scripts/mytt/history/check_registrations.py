from app.core.database import engine
from sqlalchemy import text


def main():

    # -----------------------------------------------------------------------
    # Übersicht pro Saison / Halbserie
    # -----------------------------------------------------------------------

    summary_query = text(
        """
        SELECT
            s.id AS season_id,
            s.start_year,
            s.end_year,
            s.half,

            COUNT(DISTINCT t.id) AS teams,

            COUNT(
                DISTINCT CASE
                    WHEN t.team_number IS NOT NULL
                    THEN t.id
                END
            ) AS teams_with_number,

            COUNT(
                DISTINCT tm.team_id
            ) AS teams_with_memberships,

            COUNT(
                tm.player_id
            ) AS memberships,

            COUNT(
                DISTINCT tm.player_id
            ) AS players

        FROM season s

        LEFT JOIN team t
            ON t.season_id = s.id

        LEFT JOIN team_membership tm
            ON tm.team_id = t.id

        GROUP BY
            s.id,
            s.start_year,
            s.end_year,
            s.half

        ORDER BY
            s.start_year,
            s.half;
        """
    )

    # -----------------------------------------------------------------------
    # Teams, bei denen etwas auffällig ist
    # -----------------------------------------------------------------------

    details_query = text(
        """
        SELECT
            s.start_year,
            s.end_year,
            s.half,

            t.id AS team_id,
            t.name,
            t.mytt_team_id,
            t.team_number,

            COUNT(
                tm.player_id
            ) AS memberships

        FROM team t

        JOIN season s
            ON s.id = t.season_id

        LEFT JOIN team_membership tm
            ON tm.team_id = t.id

        GROUP BY
            s.start_year,
            s.end_year,
            s.half,
            t.id,
            t.name,
            t.mytt_team_id,
            t.team_number

        HAVING
            t.team_number IS NULL
            OR COUNT(tm.player_id) = 0

        ORDER BY
            s.start_year,
            s.half,
            t.name;
        """
    )

    with engine.connect() as connection:
        summary = connection.execute(summary_query).mappings().all()

        details = connection.execute(details_query).mappings().all()

    # -----------------------------------------------------------------------
    # Ausgabe
    # -----------------------------------------------------------------------

    print()
    print("=" * 100)

    print("MYTT REGISTRATION IMPORT - DATENBANKCHECK")

    print("=" * 100)

    print()

    print(
        f"{'Saison':<12}"
        f"{'Halb':<7}"
        f"{'Teams':>7}"
        f"{'Nr.':>7}"
        f"{'mit Spielern':>15}"
        f"{'Memberships':>15}"
        f"{'Spieler':>10}"
        f"{'Status':>15}"
    )

    print("-" * 100)

    for row in summary:
        season = f"{row['start_year']}/{str(row['end_year'])[-2:]}"

        half = str(row["half"]).upper()

        teams = row["teams"]

        teams_with_number = row["teams_with_number"]

        teams_with_memberships = row["teams_with_memberships"]

        # ---------------------------------------------------------------
        # Status bestimmen
        # ---------------------------------------------------------------

        if teams == 0:
            status = "KEINE TEAMS"

        elif teams_with_number == 0 and teams_with_memberships == 0:
            status = "NICHT GELADEN"

        elif teams_with_number == teams and teams_with_memberships == teams:
            status = "OK"

        else:
            status = "TEILWEISE"

        print(
            f"{season:<12}"
            f"{half:<7}"
            f"{teams:>7}"
            f"{teams_with_number:>7}"
            f"{teams_with_memberships:>15}"
            f"{row['memberships']:>15}"
            f"{row['players']:>10}"
            f"{status:>15}"
        )

    # -----------------------------------------------------------------------
    # Auffällige Teams
    # -----------------------------------------------------------------------

    print()
    print()
    print("=" * 100)

    print("AUFFÄLLIGE TEAMS")

    print("=" * 100)

    if not details:
        print()
        print("Keine auffälligen Teams gefunden.")

        return

    current_season = None

    for row in details:
        season = (
            f"{row['start_year']}/"
            f"{str(row['end_year'])[-2:]} "
            f"{str(row['half']).upper()}"
        )

        if season != current_season:
            current_season = season

            print()
            print(season)

            print("-" * len(season))

        problems = []

        if row["team_number"] is None:
            problems.append("keine team_number")

        if row["memberships"] == 0:
            problems.append("keine Memberships")

        problem_text = ", ".join(problems)

        print(f"  {row['name']} (myTT {row['mytt_team_id']}): {problem_text}")


if __name__ == "__main__":
    main()
