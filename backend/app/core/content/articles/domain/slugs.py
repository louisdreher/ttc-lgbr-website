import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def match_report_slug(
    team_name: str, team_number: int | None, scheduled_at: datetime
) -> str:
    """Build a report address from the team and local match date."""
    name = unicodedata.normalize("NFKD", team_name.lower().replace("ß", "ss"))
    name = name.encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-") or "mannschaft"
    if team_number is not None and not name.endswith(f"-{team_number}"):
        name += f"-{team_number}"
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    day = scheduled_at.astimezone(ZoneInfo("Europe/Berlin")).date().isoformat()
    return f"{name[:220]}-{day}"
