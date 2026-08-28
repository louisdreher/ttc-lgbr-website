import argparse
import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path

import httpx
from app.integrations.mytischtennis.api import MyTischtennisClient

REQUEST_DELAY = 1.0


# ---------------------------------------------------------------------------
# OUTPUT-ORDNER
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output/mytt_tests")

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ---------------------------------------------------------------------------
# HILFSFUNKTION
# ---------------------------------------------------------------------------


async def run_test(
    name: str,
    request: Callable[[], Awaitable[dict]],
):
    print(f"\n{name}")

    try:
        data = await request()

    except httpx.HTTPStatusError as exc:
        print(f"  FEHLER: HTTP {exc.response.status_code}")

        print(f"  URL: {exc.request.url}")

        error_file = OUTPUT_DIR / f"{name}_error.txt"

        error_file.write_text(
            exc.response.text,
            encoding="utf-8",
        )

        print(f"  Response gespeichert: {error_file}")

        return None

    except Exception as exc:
        print(f"  FEHLER: {type(exc).__name__}: {exc}")

        return None

    output_file = OUTPUT_DIR / f"{name}.json"

    output_file.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print("  OK")

    print(f"  Gespeichert: {output_file}")

    if isinstance(data, dict):
        print(f"  Keys: {list(data.keys())}")

    await asyncio.sleep(REQUEST_DELAY)

    return data


# ---------------------------------------------------------------------------
# TESTS
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ruft myTT-Endpunkte ab und speichert Antworten zur Diagnose."
    )
    parser.add_argument("season", help="myTT-Saison, zum Beispiel 26--27")
    parser.add_argument("team_id", type=int, help="myTT-Team-ID")
    parser.add_argument("meeting_id", type=int, help="myTT-Begegnungs-ID")
    parser.add_argument("date_start", type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("date_end", type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--group-id", type=int)
    parser.add_argument("--league-slug")
    parser.add_argument("--team-name")
    args = parser.parse_args()

    api = MyTischtennisClient()

    # -----------------------------------------------------------------------
    # 01 - Vereins-Spielplan
    # -----------------------------------------------------------------------

    await run_test(
        "01_club_schedule",
        lambda: api.get_club_schedule_data(
            date_start=args.date_start,
            date_end=args.date_end,
            season=args.season,
        ),
    )

    # -----------------------------------------------------------------------
    # 02 - Aktuelle Mannschaften
    # -----------------------------------------------------------------------

    await run_test(
        "02_current_teams",
        lambda: api.get_current_teams(),
    )

    # -----------------------------------------------------------------------
    # 03 - Vereins-Mannschaften
    # -----------------------------------------------------------------------

    await run_test(
        "03_club_teams",
        lambda: api.get_club_teams_data(
            season=args.season,
        ),
    )

    # -----------------------------------------------------------------------
    # 04 - Spieler einer Mannschaft
    # -----------------------------------------------------------------------

    await run_test(
        "04_team_players",
        lambda: api.get_team_players(
            team_id=args.team_id,
        ),
    )

    # -----------------------------------------------------------------------
    # 05 - Einfacher Mannschaftsspielplan
    # -----------------------------------------------------------------------

    await run_test(
        "05_team_schedule",
        lambda: api.get_team_schedule(
            team_id=args.team_id,
            season=args.season,
        ),
    )

    # -----------------------------------------------------------------------
    # Gruppenabhängige Endpoints
    # -----------------------------------------------------------------------

    if (
        args.group_id is not None
        and args.league_slug is not None
        and args.team_name is not None
    ):
        # -------------------------------------------------------------------
        # 06 - Ausführlicher Mannschaftsspielplan
        # -------------------------------------------------------------------

        await run_test(
            "06_team_schedule_data",
            lambda: api.get_team_schedule_data(
                season=args.season,
                league_slug=args.league_slug,
                group_id=args.group_id,
                team_id=args.team_id,
                team_name=args.team_name,
            ),
        )

        # -------------------------------------------------------------------
        # 07 - Spielerbilanzen
        # -------------------------------------------------------------------

        await run_test(
            "07a_team_player_balances",
            lambda: api.get_team_player_balances(
                season=args.season,
                league_slug=args.league_slug,
                group_id=args.group_id,
                team_id=args.team_id,
                team_name=args.team_name,
                round_filter="vr",
            ),
        )

        await run_test(
            "07b_team_player_balances",
            lambda: api.get_team_player_balances(
                season=args.season,
                league_slug=args.league_slug,
                group_id=args.group_id,
                team_id=args.team_id,
                team_name=args.team_name,
                round_filter="rr",
            ),
        )

        # -------------------------------------------------------------------
        # 08 - Mannschaftsinformationen
        # -------------------------------------------------------------------

        await run_test(
            "08_team_info",
            lambda: api.get_team_info(
                season=args.season,
                league_slug=args.league_slug,
                group_id=args.group_id,
                team_id=args.team_id,
                team_name=args.team_name,
            ),
        )

    else:
        print("\n06-08 übersprungen: GROUP_ID / LEAGUE_SLUG / TEAM_NAME fehlen.")

    # -----------------------------------------------------------------------
    # 09 - Begegnungsdetails
    # -----------------------------------------------------------------------

    await run_test(
        "09_meeting",
        lambda: api.get_meeting(
            meeting_id=args.meeting_id,
        ),
    )

    # -----------------------------------------------------------------------
    # 10 - Ligatabelle
    # -----------------------------------------------------------------------

    if args.group_id is not None:
        await run_test(
            "10_league_table",
            lambda: api.get_league_table(
                group_id=args.group_id,
            ),
        )

    else:
        print("\n10 übersprungen: GROUP_ID fehlt.")

    # -----------------------------------------------------------------------
    # 11 + 12 - Historische Mannschaftsmeldungen
    # -----------------------------------------------------------------------

    if args.group_id is not None and args.league_slug is not None:
        # Vorrunde
        await run_test(
            "11_team_registrations_vr",
            lambda: api.get_team_registrations(
                season=args.season,
                league_slug=args.league_slug,
                group_id=args.group_id,
                round_filter="vr",
            ),
        )

        # Rückrunde
        await run_test(
            "12_team_registrations_rr",
            lambda: api.get_team_registrations(
                season=args.season,
                league_slug=args.league_slug,
                group_id=args.group_id,
                round_filter="rr",
            ),
        )

    else:
        print("\n11-12 übersprungen: GROUP_ID / LEAGUE_SLUG fehlen.")


if __name__ == "__main__":
    asyncio.run(main())
