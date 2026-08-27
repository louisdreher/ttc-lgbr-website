import asyncio
import json
from pathlib import Path
from typing import Awaitable, Callable

import httpx

from app.integrations.mytischtennis.api import MyTischtennisClient


# ---------------------------------------------------------------------------
# TESTDATEN
# ---------------------------------------------------------------------------

# Aktuelle Saison 2026/27
SEASON = "20--21"

# Erwachsene I
GROUP_ID = 385903
LEAGUE_SLUG = "Kreisliga"

REQUEST_DELAY = 1.0

# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output/mytt_tests/registrations")

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ---------------------------------------------------------------------------
# TEST-HILFSFUNKTION
# ---------------------------------------------------------------------------

async def run_test(
    name: str,
    request: Callable[[], Awaitable[dict]],
):
    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    try:
        data = await request()

    except httpx.HTTPStatusError as exc:
        print(
            f"HTTP-FEHLER: {exc.response.status_code}"
        )

        print(
            f"URL: {exc.request.url}"
        )

        error_file = OUTPUT_DIR / f"{name}_http_error.txt"

        error_file.write_text(
            exc.response.text,
            encoding="utf-8",
        )

        print(
            f"Response gespeichert: {error_file}"
        )

        return None

    except Exception as exc:
        print(
            f"FEHLER: {type(exc).__name__}: {exc}"
        )

        return None


    # -----------------------------------------------------------------------
    # Response speichern
    # -----------------------------------------------------------------------

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

    print(
        f"Response gespeichert: {output_file}"
    )


    # -----------------------------------------------------------------------
    # myTT kann Fehler im JSON zurückgeben,
    # obwohl HTTP 200 geliefert wurde.
    # -----------------------------------------------------------------------

    api_error = (
        data.get("error")
        if isinstance(data, dict)
        else None
    )

    if api_error:
        print("MYTT-API-FEHLER")

        print(
            f"Code:    {api_error.get('code')}"
        )

        print(
            f"Message: {api_error.get('message')}"
        )

    else:
        print("ERFOLGREICH")

        if isinstance(data, dict):
            print(
                f"Keys: {list(data.keys())}"
            )


    await asyncio.sleep(
        REQUEST_DELAY
    )

    return data


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

async def main():

    api = MyTischtennisClient()


    # -----------------------------------------------------------------------
    # Vorrunde
    # -----------------------------------------------------------------------

    await run_test(
        "registrations_26_27_vr",
        lambda: api.get_team_registrations(
            season=SEASON,
            league_slug=LEAGUE_SLUG,
            group_id=GROUP_ID,
            round_filter="vr",
        ),
    )


    # -----------------------------------------------------------------------
    # Rückrunde
    # -----------------------------------------------------------------------

    await run_test(
        "registrations_26_27_rr",
        lambda: api.get_team_registrations(
            season=SEASON,
            league_slug=LEAGUE_SLUG,
            group_id=GROUP_ID,
            round_filter="rr",
        ),
    )


if __name__ == "__main__":
    asyncio.run(main())