from dataclasses import replace
from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

import app.model_registry  # noqa: F401 -- register foreign key targets
from app.adapters.outbound.persistence.media.models import MediaAsset
from app.adapters.outbound.persistence.media.unit_of_work import SqlMediaUnitOfWork
from app.adapters.outbound.persistence.members.models import Member
from app.adapters.outbound.persistence.users.models import User
from app.bootstrap.media import build_upload_image
from app.core.content.media.application.commands import UploadImage
from app.core.content.media.application.dto import ProcessedImage, UploadImageCommand
from app.core.content.media.application.errors import InvalidImage, MediaStorageError


class FakeUnitOfWork:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.committed = False
        self.rolled_back = False
        self.media = Mock()
        self.media.save.side_effect = self.save

    def save(self, asset):
        if self.fail_at == "save":
            raise RuntimeError("database failed")
        return replace(asset, id=42)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.rolled_back = not self.committed

    def commit(self):
        if self.fail_at == "commit":
            raise RuntimeError("database failed")
        self.committed = True


def dependencies(fail_at=None):
    uow = FakeUnitOfWork(fail_at)
    processor = Mock()
    processor.process.return_value = ProcessedImage(b"webp", 20, 10, "image/webp")
    storage = Mock()
    storage.save.return_value = "images/test.webp"
    return uow, processor, storage


def command(data=b"source", user_id=1):
    return UploadImageCommand(data, "team.jpg", user_id)


def test_upload_commits_processed_metadata():
    uow, processor, storage = dependencies()
    result = UploadImage(uow, processor, storage).execute(command())
    assert result.id == 42
    assert (result.width, result.height, result.file_size) == (20, 10, 4)
    asset = uow.media.save.call_args.args[0]
    assert asset.original_filename == "team.jpg"
    assert asset.uploaded_by_user_id == 1
    assert asset.storage_key == "images/test.webp"
    assert asset.mime_type == "image/webp"
    processor.process.assert_called_once_with(b"source")
    storage.save.assert_called_once_with(processor.process.return_value)
    storage.delete.assert_not_called()
    assert uow.committed


@pytest.mark.parametrize("fail_at", ["save", "commit"])
def test_database_failure_removes_file(fail_at):
    uow, processor, storage = dependencies(fail_at)
    with pytest.raises(RuntimeError, match="database failed"):
        UploadImage(uow, processor, storage).execute(command())
    storage.delete.assert_called_once_with("images/test.webp")
    assert uow.rolled_back


def test_cleanup_failure_preserves_database_error(caplog):
    uow, processor, storage = dependencies("commit")
    storage.delete.side_effect = MediaStorageError("cannot delete")
    with pytest.raises(RuntimeError, match="database failed") as raised:
        UploadImage(uow, processor, storage).execute(command())
    assert "cleanup failed" in raised.value.__notes__[0]
    assert "images/test.webp" in caplog.text


def test_invalid_image_does_not_write_anything():
    uow, processor, storage = dependencies()
    processor.process.side_effect = InvalidImage("bad image")
    with pytest.raises(InvalidImage):
        UploadImage(uow, processor, storage).execute(command())
    storage.save.assert_not_called()
    uow.media.save.assert_not_called()


def test_storage_failure_does_not_write_database():
    uow, processor, storage = dependencies()
    storage.save.side_effect = MediaStorageError("disk full")
    with pytest.raises(MediaStorageError):
        UploadImage(uow, processor, storage).execute(command())
    uow.media.save.assert_not_called()
    storage.delete.assert_not_called()


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(
        engine, tables=[Member.__table__, User.__table__, MediaAsset.__table__]
    )
    with Session(engine) as session:
        session.add(User(id=1, email="media@example.test", name="Editor", password_hash="test"))
        session.commit()
    yield engine
    engine.dispose()


def png_bytes():
    with Image.new("RGB", (80, 40), "red") as image, BytesIO() as output:
        image.save(output, format="PNG")
        return output.getvalue()


def test_real_processing_storage_and_sql_roundtrip(engine, tmp_path):
    with Session(engine) as session:
        result = build_upload_image(session, media_directory=tmp_path).execute(command(png_bytes()))
    with Session(engine) as session:
        row = session.get(MediaAsset, result.id)
        assert row is not None
        assert row.original_filename == "team.jpg"
        assert row.uploaded_by_user_id == 1
        data = (tmp_path / row.storage_key).read_bytes()
        assert len(data) == row.file_size == result.file_size
        with Image.open(BytesIO(data)) as image:
            assert image.format == "WEBP"
            assert image.size == (row.width, row.height) == (80, 40)


def test_sql_foreign_key_failure_rolls_back_and_removes_real_file(engine, tmp_path):
    with Session(engine) as session:
        with pytest.raises(IntegrityError):
            build_upload_image(session, media_directory=tmp_path).execute(command(png_bytes(), 999))
        assert session.exec(select(MediaAsset)).all() == []
    assert list((tmp_path / "images").iterdir()) == []


def test_uncommitted_unit_of_work_rolls_back(engine):
    from app.core.content.media.domain.asset import MediaAsset as DomainAsset

    with Session(engine) as session:
        with SqlMediaUnitOfWork(session) as uow:
            saved = uow.media.save(DomainAsset("images/test.webp", "test.jpg", "image/webp", 4, 20, 10, 1))
            assert saved.id is not None
    with Session(engine) as session:
        assert session.exec(select(MediaAsset)).all() == []


def test_commit_failure_rolls_back_insert_and_removes_file(engine, tmp_path):
    with Session(engine) as session:
        @event.listens_for(session, "before_commit")
        def fail_commit(session):
            raise RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            build_upload_image(session, media_directory=tmp_path).execute(command(png_bytes()))
        assert session.exec(select(MediaAsset)).all() == []
    assert list((tmp_path / "images").iterdir()) == []
