"""Import table definitions so Alembic and tests see complete SQLModel metadata."""

# ruff: noqa: F401 -- these imports intentionally register tables through module loading
from app.adapters.outbound.persistence.articles.models import Article, ArticleTag, Tag
from app.adapters.outbound.persistence.auth.models import RefreshSession
from app.adapters.outbound.persistence.competition.leagues import (
    LeagueGroup,
    LeagueTableEntry,
)
from app.adapters.outbound.persistence.competition.matches import (
    Match,
    MatchLineup,
    MatchParticipant,
    SetResult,
    TeamMatch,
    TeamMatchNotice,
)
from app.adapters.outbound.persistence.competition.seasons import Season, SeasonHalf
from app.adapters.outbound.persistence.competition.teams import (
    Team,
    TeamAssignment,
    TeamMembership,
)
from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.media.models import (
    Gallery,
    GalleryMedia,
    MediaAsset,
)
from app.adapters.outbound.persistence.members.models import (
    Member,
    Player,
    PlayerRating,
)
from app.adapters.outbound.persistence.messaging.models import OutboxMessage
from app.adapters.outbound.persistence.users.models import User
