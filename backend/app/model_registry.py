# import nötig für db erstellung
from app.auth.model import RefreshSession
from app.domains.content.articles.model import Article, ArticleTag, Tag
from app.domains.content.events.model import Event, EventCategory
from app.domains.content.media.model import Gallery, GalleryMedia, MediaAsset
from app.domains.competition.league.model import LeagueGroup, LeagueTableEntry
from app.domains.competition.matches.models import (
    Match,
    MatchLineup,
    MatchParticipant,
    SetResult,
    TeamMatch,
    TeamMatchNotice,
)
from app.domains.competition.season.model import Season, SeasonHalf
from app.domains.competition.teams.model import (
    Team,
    TeamAssignment,
    TeamMembership,
)
from app.domains.members.model import Member, Player, PlayerRating
from app.domains.users.model import User, create_default_roles
