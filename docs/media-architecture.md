# Media processing

## Implemented scope

The first media building block processes a single image entirely in memory.
`core/content/media/application/ports.py` defines `ImageProcessor.process(bytes)`;
the frozen `ProcessedImage` DTO contains output bytes, dimensions, MIME type and
a derived file size. `InvalidImage` represents rejected input. The core has no
Pillow dependency; `adapters/outbound/media/image_processor.py` implements the
port with Pillow.

The adapter identifies JPEG, PNG and WebP by content, checks byte and pixel limits,
rejects animations and decodes the input. It applies EXIF orientation, reduces
the longest edge without upscaling and produces a WebP master. Transparency is
preserved. EXIF, XMP and other source metadata are not copied. ICC color profile
conversion is not implemented yet; evaluate color fidelity with real club photos
before importing the archive.

Constructor options currently default to 20 MiB input, 40 million pixels,
2,560 pixels maximum output edge and WebP quality 85. Pillow's own decoder limits
also remain enabled. These defaults are initial values for evaluation, not a
guarantee of output file size. Quality and dimensions need visual review with
representative photos.

## Planned integration

The integrated upload workflow, HTTP endpoints and content associations remain planned.

## Verification

From `backend/`, in the `ttc-backend` environment:

```powershell
python -m pytest tests/test_image_processor.py tests/test_backend_architecture.py
```
