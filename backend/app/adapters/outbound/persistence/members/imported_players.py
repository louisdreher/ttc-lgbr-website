from sqlmodel import Session, select

from app.adapters.outbound.persistence.members.models import Member, Player
from app.core.competition.public import ImportedPlayer


class SqlImportedPlayers:
    """Bridge to the existing Members tables using an explicit import contract."""

    def __init__(self, session: Session):
        self.session = session

    def resolve(self, data: ImportedPlayer, *, update_names: bool = False) -> int:
        session = self.session
        if not data.registration_id and not data.external_id:
            raise ValueError("Spieler besitzt weder NUID noch externe ID.")
        by_registration = (
            session.exec(
                select(Player).where(Player.nuid == data.registration_id)
            ).first()
            if data.registration_id
            else None
        )
        by_external = (
            session.exec(
                select(Player).where(Player.mytt_person_id == data.external_id)
            ).first()
            if data.external_id
            else None
        )
        if (
            not data.absent
            and by_registration
            and by_external
            and by_registration.id != by_external.id
        ):
            raise ValueError(
                "Spieler-ID-Konflikt: IDs zeigen auf verschiedene Spieler."
            )
        player = by_registration if data.absent else by_registration or by_external
        if player is None:
            if (
                not update_names
                and not data.absent
                and (not data.first_name or not data.last_name)
            ):
                raise ValueError("Neuer Spieler: Vor- oder Nachname fehlt.")
            member = Member(
                first_name="Nicht" if data.absent else data.first_name,
                last_name="anwesend" if data.absent else data.last_name,
                is_active=not data.absent,
            )
            session.add(member)
            session.flush()
            player = Player(
                member_id=member.id,
                nuid=data.registration_id,
                mytt_person_id=data.external_id,
            )
        else:
            if not player.nuid:
                player.nuid = data.registration_id
            if not player.mytt_person_id:
                player.mytt_person_id = data.external_id
            if update_names:
                member = session.get(Member, player.member_id)
                if member is None:
                    raise RuntimeError("Spieler verweist auf ein fehlendes Mitglied.")
                if data.first_name:
                    member.first_name = data.first_name
                if data.last_name:
                    member.last_name = data.last_name
        session.add(player)
        session.flush()
        if player.id is None:
            raise RuntimeError("Gespeicherter Spieler besitzt keine ID.")
        return player.id
