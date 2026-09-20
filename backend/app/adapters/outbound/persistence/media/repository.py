from dataclasses import replace

from sqlmodel import Session

from app.adapters.outbound.persistence.media.models import MediaAsset as MediaAssetRow
from app.core.content.media.domain.asset import MediaAsset


class SqlMediaRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, asset: MediaAsset) -> MediaAsset:
        if asset.id is not None:
            raise ValueError("This repository only inserts new media assets.")
        row = MediaAssetRow(
            storage_key=asset.storage_key,
            original_filename=asset.original_filename,
            mime_type=asset.mime_type,
            file_size=asset.file_size,
            width=asset.width,
            height=asset.height,
            uploaded_by_user_id=asset.uploaded_by_user_id,
            caption=asset.caption,
        )
        self.session.add(row)
        self.session.flush()
        return replace(asset, id=row.id)

    def get(self, media_id: int) -> MediaAsset | None:
        row = self.session.get(MediaAssetRow, media_id)
        if row is None or row.mime_type != "image/webp":
            return None
        return MediaAsset(
            id=row.id, storage_key=row.storage_key, original_filename=row.original_filename,
            mime_type=row.mime_type, file_size=row.file_size, width=row.width,
            height=row.height, uploaded_by_user_id=row.uploaded_by_user_id, caption=row.caption,
        )

    def update_caption(self, asset: MediaAsset) -> None:
        from sqlalchemy import update

        self.session.execute(
            update(MediaAssetRow).where(MediaAssetRow.id == asset.id).values(caption=asset.caption)
        )
