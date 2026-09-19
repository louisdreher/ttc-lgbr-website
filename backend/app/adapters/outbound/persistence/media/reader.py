from sqlmodel import Session, select

from app.adapters.outbound.persistence.media.models import MediaAsset
from app.core.content.media.application.dto import ImageReference


class SqlMediaReader:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_image(self, media_id: int) -> ImageReference | None:
        row = self.session.exec(
            select(MediaAsset.storage_key, MediaAsset.uploaded_by_user_id).where(
                MediaAsset.id == media_id, MediaAsset.mime_type == "image/webp"
            )
        ).first()
        return None if row is None else ImageReference(*row)
