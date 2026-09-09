from app.bootstrap.competition import build_registration_report


def main():
    summary, details = build_registration_report().execute()
    print()
    print("=" * 100)
    print("MYTT REGISTRATION IMPORT - DATENBANKCHECK")
    print("=" * 100)
    print()
    print(
        f"{'Saison':<12}{'Halb':<7}{'Teams':>7}{'Nr.':>7}{'mit Spielern':>15}{'Memberships':>15}{'Spieler':>10}{'Status':>15}"
    )
    print("-" * 100)
    for row in summary:
        season = f"{row['start_year']}/{str(row['end_year'])[-2:]}"
        half = str(row["half"]).upper()
        teams = row["teams"]
        teams_with_number = row["teams_with_number"]
        teams_with_memberships = row["teams_with_memberships"]
        if teams == 0:
            status = "KEINE TEAMS"
        elif teams_with_number == 0 and teams_with_memberships == 0:
            status = "NICHT GELADEN"
        elif teams_with_number == teams and teams_with_memberships == teams:
            status = "OK"
        else:
            status = "TEILWEISE"
        print(
            f"{season:<12}{half:<7}{teams:>7}{teams_with_number:>7}{teams_with_memberships:>15}{row['memberships']:>15}{row['players']:>10}{status:>15}"
        )
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
        season = f"{row['start_year']}/{str(row['end_year'])[-2:]} {str(row['half']).upper()}"
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
