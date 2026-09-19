from uuid import UUID

import pytest

from app.adapters.outbound.media import local_storage
from app.adapters.outbound.media.local_storage import LocalMediaStorage
from app.core.content.media.application.dto import ProcessedImage
from app.core.content.media.application.errors import (
    InvalidImage,
    InvalidStorageKey,
    MediaStorageError,
)


@pytest.fixture
def image():
    # Storage treats the processor's bytes as opaque; decoding is tested separately.
    return ProcessedImage(data=b"processed webp bytes", width=20, height=10, mime_type="image/webp")


def test_save_creates_directory_and_returns_unique_relative_keys(tmp_path, image):
    root = tmp_path / "media"
    storage = LocalMediaStorage(root)
    assert not root.exists()
    first = storage.save(image)
    second = storage.save(image)
    assert first != second
    assert first.startswith("images/") and first.endswith(".webp")
    assert (root / first).read_bytes() == image.data
    assert (root / second).read_bytes() == image.data


def test_delete_is_idempotent_and_preserves_other_images(tmp_path, image):
    storage = LocalMediaStorage(tmp_path)
    first = storage.save(image)
    second = storage.save(image)
    storage.delete(first)
    storage.delete(first)
    assert not (tmp_path / first).exists()
    assert (tmp_path / second).read_bytes() == image.data


@pytest.mark.parametrize("key", [
    "../outside.webp", "/outside.webp", "C:/outside.webp",
    "images/../../outside.webp", "images\\test.webp", "images/test.webp", "",
])
def test_invalid_keys_cannot_delete_files(tmp_path, key):
    outside = tmp_path / "outside.webp"
    outside.write_bytes(b"keep")
    with pytest.raises(InvalidStorageKey):
        LocalMediaStorage(tmp_path / "media").delete(key)
    assert outside.read_bytes() == b"keep"


def test_collision_never_overwrites_or_deletes_existing_file(tmp_path, image, monkeypatch):
    monkeypatch.setattr(local_storage, "uuid4", lambda: UUID(int=1))
    storage = LocalMediaStorage(tmp_path)
    key = storage.save(image)
    with pytest.raises(MediaStorageError):
        storage.save(image)
    assert (tmp_path / key).read_bytes() == image.data


def test_storage_failure_is_translated(tmp_path, image):
    root = tmp_path / "not-a-directory"
    root.write_bytes(b"keep")
    with pytest.raises(MediaStorageError):
        LocalMediaStorage(root).save(image)
    assert root.read_bytes() == b"keep"


def test_partial_write_is_cleaned_up(tmp_path, image, monkeypatch):
    original_open = local_storage.Path.open

    class FailingWriter:
        def __init__(self, file):
            self.file = file

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file.close()

        def write(self, data):
            self.file.write(data[:3])
            raise OSError("Disk full")

        def close(self):
            self.file.close()

    def failing_open(path, mode, *args, **kwargs):
        return FailingWriter(original_open(path, mode, *args, **kwargs))

    monkeypatch.setattr(local_storage.Path, "open", failing_open)
    with pytest.raises(MediaStorageError):
        LocalMediaStorage(tmp_path).save(image)
    assert list((tmp_path / "images").iterdir()) == []


@pytest.mark.parametrize("data, mime_type", [(b"", "image/webp"), (b"jpeg", "image/jpeg")])
def test_storage_rejects_empty_or_wrong_output(tmp_path, data, mime_type):
    image = ProcessedImage(data=data, width=1, height=1, mime_type=mime_type)
    with pytest.raises(InvalidImage):
        LocalMediaStorage(tmp_path).save(image)
    assert list(tmp_path.iterdir()) == []
