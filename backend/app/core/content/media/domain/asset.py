from dataclasses import dataclass, replace


class InvalidCaption(ValueError):
    pass


def normalize_caption(value: str | None) -> str | None:
    value = value.strip() if value else None
    if value and len(value) > 1000:
        raise InvalidCaption("Die Bildunterschrift darf höchstens 1000 Zeichen enthalten.")
    return value or None


@dataclass(frozen=True)
class MediaAsset:
    storage_key: str
    original_filename: str
    mime_type: str
    file_size: int
    width: int
    height: int
    uploaded_by_user_id: int
    id: int | None = None
    caption: str | None = None

    def with_caption(self, caption: str | None) -> "MediaAsset":
        return replace(self, caption=normalize_caption(caption))
