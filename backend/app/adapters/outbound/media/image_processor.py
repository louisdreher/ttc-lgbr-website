from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.content.media.application.dto import ProcessedImage
from app.core.content.media.application.errors import InvalidImage


class PillowImageProcessor:
    """Process image bytes in memory; no filesystem or database side effects."""

    def __init__(
        self,
        *,
        max_file_size: int = 20 * 1024 * 1024,
        max_pixels: int = 40_000_000,
        max_edge: int = 2560,
        quality: int = 85,
    ) -> None:
        if min(max_file_size, max_pixels, max_edge) < 1:
            raise ValueError("Image limits must be positive.")
        if not 1 <= quality <= 100:
            raise ValueError("WebP quality must be between 1 and 100.")
        self.max_file_size = max_file_size
        self.max_pixels = max_pixels
        self.max_edge = max_edge
        self.quality = quality

    def process(self, data: bytes) -> ProcessedImage:
        if not data or len(data) > self.max_file_size:
            raise InvalidImage("Image is empty or exceeds the file size limit.")

        try:
            # Identify by content, not by a supplied filename or MIME type.
            with Image.open(BytesIO(data), formats=("JPEG", "PNG", "WEBP")) as source:
                if source.width * source.height > self.max_pixels:
                    raise InvalidImage("Image exceeds the pixel limit.")
                if getattr(source, "is_animated", False):
                    raise InvalidImage("Animated images are not supported.")
                source.verify()

            # verify() consumes the decoder; reopen before reading pixel data.
            with Image.open(BytesIO(data), formats=("JPEG", "PNG", "WEBP")) as source:
                source.load()
                with ImageOps.exif_transpose(source) as oriented:
                    has_alpha = "A" in oriented.getbands() or "transparency" in oriented.info
                    with oriented.convert("RGBA" if has_alpha else "RGB") as image:
                        image.thumbnail(
                            (self.max_edge, self.max_edge), Image.Resampling.LANCZOS
                        )
                        # Do not carry EXIF, XMP, ICC or PNG text into the master.
                        image.info.clear()
                        with BytesIO() as output:
                            image.save(output, format="WEBP", quality=self.quality)
                            return ProcessedImage(
                                data=output.getvalue(),
                                width=image.width,
                                height=image.height,
                                mime_type="image/webp",
                            )
        except Image.DecompressionBombError as exc:
            raise InvalidImage("Image exceeds the decoder pixel limit.") from exc
        except (UnidentifiedImageError, OSError, SyntaxError) as exc:
            raise InvalidImage("Expected an intact JPEG, PNG or WebP image.") from exc
