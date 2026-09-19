from io import BytesIO

import pytest
from PIL import Image

from app.adapters.outbound.media.image_processor import PillowImageProcessor
from app.core.content.media.application.errors import InvalidImage


def image_bytes(size=(80, 40), *, format="PNG", mode="RGB", **options):
    with Image.new(mode, size, "red") as image, BytesIO() as output:
        image.save(output, format=format, **options)
        return output.getvalue()


@pytest.mark.parametrize("format", ["JPEG", "PNG", "WEBP"])
def test_supported_formats_produce_webp_without_upscaling(format):
    result = PillowImageProcessor().process(image_bytes(format=format))
    assert (result.width, result.height) == (80, 40)
    assert result.mime_type == "image/webp"
    assert result.file_size == len(result.data)
    with Image.open(BytesIO(result.data)) as image:
        image.load()
        assert image.format == "WEBP"
        assert image.size == (80, 40)


@pytest.mark.parametrize(
    "size, expected",
    [((3000, 1500), (2560, 1280)), ((1500, 3000), (1280, 2560))],
)
def test_default_size_limit_preserves_aspect_ratio(size, expected):
    result = PillowImageProcessor().process(image_bytes(size))
    assert (result.width, result.height) == expected


def test_orientation_is_applied_before_resizing_and_exif_is_removed():
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise.
    exif[315] = "Private photographer metadata"
    result = PillowImageProcessor(max_edge=60).process(image_bytes(exif=exif))
    assert (result.width, result.height) == (30, 60)
    with Image.open(BytesIO(result.data)) as image:
        assert not image.getexif()
        assert "exif" not in image.info


def test_transparency_is_preserved():
    with Image.new("RGBA", (20, 20), (255, 0, 0, 0)) as source, BytesIO() as output:
        source.save(output, format="PNG")
        result = PillowImageProcessor().process(output.getvalue())
    with Image.open(BytesIO(result.data)) as image:
        assert image.getpixel((0, 0))[3] == 0


@pytest.mark.parametrize(
    "data",
    [b"", b"not an image", image_bytes(format="GIF"), image_bytes()[:50]],
)
def test_invalid_unsupported_and_truncated_images_are_rejected(data):
    with pytest.raises(InvalidImage):
        PillowImageProcessor().process(data)


def test_file_size_limit():
    data = image_bytes()
    with pytest.raises(InvalidImage, match="file size"):
        PillowImageProcessor(max_file_size=len(data) - 1).process(data)
    PillowImageProcessor(max_file_size=len(data)).process(data)


def test_pixel_limit_is_checked_before_decoding(monkeypatch):
    data = image_bytes()

    def unexpected_load(*args, **kwargs):
        pytest.fail("Oversized pixel data must not be decoded")

    monkeypatch.setattr(Image.Image, "load", unexpected_load)
    with pytest.raises(InvalidImage, match="pixel limit"):
        PillowImageProcessor(max_pixels=3199).process(data)


@pytest.mark.parametrize("format", ["PNG", "WEBP"])
def test_animated_images_are_rejected(format):
    with (
        Image.new("RGB", (20, 20), "red") as first,
        Image.new("RGB", (20, 20), "blue") as second,
        BytesIO() as output,
    ):
        first.save(
            output, format=format, save_all=True, append_images=[second], duration=100
        )
        with pytest.raises(InvalidImage, match="Animated"):
            PillowImageProcessor().process(output.getvalue())


@pytest.mark.parametrize(
    "options",
    [
        {"max_edge": 0},
        {"max_pixels": 0},
        {"max_file_size": 0},
        {"quality": 0},
        {"quality": 101},
    ],
)
def test_invalid_configuration_is_rejected(options):
    with pytest.raises(ValueError):
        PillowImageProcessor(**options)
