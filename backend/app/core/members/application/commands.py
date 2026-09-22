from app.core.members.application.dto import AssignPlayerImageCommand
from app.core.members.application.errors import (
    PlayerImageAssignmentNotFound,
    PlayerImageForbidden,
    PlayerImageMediaNotFound,
)
from app.core.members.application.ports import PlayerImageUnitOfWork
from app.core.members.domain.player_image import PlayerImage


class AssignPlayerImage:
    def __init__(self, uow: PlayerImageUnitOfWork):
        self.uow = uow

    def execute(self, command: AssignPlayerImageCommand) -> None:
        if not command.can_manage:
            raise PlayerImageForbidden("Keine Berechtigung zum Ändern von Spielerbildern.")
        with self.uow:
            period = self.uow.assignment_period(command.team_id, command.player_id)
            if period is None or not self.uow.images.lock_player(command.player_id):
                raise PlayerImageAssignmentNotFound("Der Spieler ist dieser Mannschaft nicht zugeordnet.")
            if not self.uow.image_available(command.media_id):
                raise PlayerImageMediaNotFound("Das Bild wurde nicht gefunden oder ist kein verwendbares Spielerbild.")
            self.uow.images.save(PlayerImage(
                command.player_id, period.start_year, period.half, command.media_id,
            ))
            self.uow.commit()
