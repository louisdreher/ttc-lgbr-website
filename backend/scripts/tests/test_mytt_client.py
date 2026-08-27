import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path

import httpx
from app.integrations.mytischtennis.api import MyTischtennisClient

# ---------------------------------------------------------------------------
# TESTDATEN
# ---------------------------------------------------------------------------

TEAM_ID = 2094640
MEETING_ID = 10971025

SEASON = "18--19"

GROUP_ID: int | None = 336737
LEAGUE_SLUG: str | None = "Kreisliga"
TEAM_NAME: str | None = "TTC Langen-Brombach"

DATE_START = date(2018, 7, 1)
DATE_END = date(2018, 12, 30)

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


async def main():

    api = MyTischtennisClient()

    # -----------------------------------------------------------------------
    # 01 - Vereins-Spielplan
    # -----------------------------------------------------------------------

    await run_test(
        "01_club_schedule",
        lambda: api.get_club_schedule_data(
            date_start=DATE_START,
            date_end=DATE_END,
            season=SEASON,
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
            season=SEASON,
        ),
    )

    # -----------------------------------------------------------------------
    # 04 - Spieler einer Mannschaft
    # -----------------------------------------------------------------------

    await run_test(
        "04_team_players",
        lambda: api.get_team_players(
            team_id=TEAM_ID,
        ),
    )

    # -----------------------------------------------------------------------
    # 05 - Einfacher Mannschaftsspielplan
    # -----------------------------------------------------------------------

    await run_test(
        "05_team_schedule",
        lambda: api.get_team_schedule(
            team_id=TEAM_ID,
            season=SEASON,
        ),
    )

    # -----------------------------------------------------------------------
    # Gruppenabhängige Endpoints
    # -----------------------------------------------------------------------

    if GROUP_ID is not None and LEAGUE_SLUG is not None and TEAM_NAME is not None:
        # -------------------------------------------------------------------
        # 06 - Ausführlicher Mannschaftsspielplan
        # -------------------------------------------------------------------

        await run_test(
            "06_team_schedule_data",
            lambda: api.get_team_schedule_data(
                season=SEASON,
                league_slug=LEAGUE_SLUG,
                group_id=GROUP_ID,
                team_id=TEAM_ID,
                team_name=TEAM_NAME,
            ),
        )

        # -------------------------------------------------------------------
        # 07 - Spielerbilanzen
        # -------------------------------------------------------------------

        await run_test(
            "07a_team_player_balances",
            lambda: api.get_team_player_balances(
                season=SEASON,
                league_slug=LEAGUE_SLUG,
                group_id=GROUP_ID,
                team_id=TEAM_ID,
                team_name=TEAM_NAME,
                round_filter="vr",
            ),
        )

        await run_test(
            "07b_team_player_balances",
            lambda: api.get_team_player_balances(
                season=SEASON,
                league_slug=LEAGUE_SLUG,
                group_id=GROUP_ID,
                team_id=TEAM_ID,
                team_name=TEAM_NAME,
                round_filter="rr",
            ),
        )

        # -------------------------------------------------------------------
        # 08 - Mannschaftsinformationen
        # -------------------------------------------------------------------

        await run_test(
            "08_team_info",
            lambda: api.get_team_info(
                season=SEASON,
                league_slug=LEAGUE_SLUG,
                group_id=GROUP_ID,
                team_id=TEAM_ID,
                team_name=TEAM_NAME,
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
            meeting_id=MEETING_ID,
        ),
    )

    # -----------------------------------------------------------------------
    # 10 - Ligatabelle
    # -----------------------------------------------------------------------

    if GROUP_ID is not None:
        await run_test(
            "10_league_table",
            lambda: api.get_league_table(
                group_id=GROUP_ID,
            ),
        )

    else:
        print("\n10 übersprungen: GROUP_ID fehlt.")

    # -----------------------------------------------------------------------
    # 11 + 12 - Historische Mannschaftsmeldungen
    # -----------------------------------------------------------------------

    if GROUP_ID is not None and LEAGUE_SLUG is not None:
        # Vorrunde
        await run_test(
            "11_team_registrations_vr",
            lambda: api.get_team_registrations(
                season=SEASON,
                league_slug=LEAGUE_SLUG,
                group_id=GROUP_ID,
                round_filter="vr",
            ),
        )

        # Rückrunde
        await run_test(
            "12_team_registrations_rr",
            lambda: api.get_team_registrations(
                season=SEASON,
                league_slug=LEAGUE_SLUG,
                group_id=GROUP_ID,
                round_filter="rr",
            ),
        )

    else:
        print("\n11-12 übersprungen: GROUP_ID / LEAGUE_SLUG fehlen.")


if __name__ == "__main__":
    asyncio.run(main())
