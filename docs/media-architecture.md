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

## Local storage

`MediaStorage` defines `save(ProcessedImage) -> str` and `delete(storage_key)`.
`adapters/outbound/media/local_storage.py` implements this port using a directory
passed to `LocalMediaStorage` at construction. It creates the directory on the
first save and stores the processor's WebP bytes under `images/<uuid>.webp`.
Only the relative key is returned; server paths are not part of the core contract.
Decoding remains the processor's responsibility.

Files are created exclusively, so an existing asset is never overwritten.
Failed writes attempt to remove partial files. Deletion is idempotent for missing
files. Invalid keys and paths escaping the resolved storage root are rejected;
I/O errors become `MediaStorageError`. The configured directory must be private
and controlled by the application, not writable by untrusted local processes.
Process crashes or cleanup failures can still leave orphan files; reconciliation
remains a future concern.

## Upload application use case

`UploadImage.execute(UploadImageCommand)` now coordinates processing, storage and
metadata insertion. The command carries input bytes, the original filename and
the authenticated uploader's ID. The filename is descriptive metadata only; it
never becomes a filesystem path. The result contains the assigned media ID,
output MIME type, byte size and dimensions, without exposing local paths.

The use case depends on `ImageProcessor`, `MediaStorage` and `MediaUnitOfWork`.
It writes a framework-free domain `MediaAsset` through `MediaRepository`.
`SqlMediaRepository` maps it to the existing SQLModel table and flushes to obtain
the ID without committing. `SqlMediaUnitOfWork` commits or rolls back; the caller
owns a dedicated session and its lifetime. No schema migration is needed.
`bootstrap/media.py:build_upload_image` composes the adapters with an explicitly
provided media directory.

On a database failure, the use case attempts to delete the saved file. If cleanup
also fails, it logs the storage key and preserves the original exception with a
cleanup note. It does not remove files after an acknowledged successful commit.
This is best-effort compensation, not an atomic filesystem/database transaction:
a process crash can leave an orphan, and a lost database connection during commit
can leave the commit outcome uncertain. Durable reconciliation is not implemented.

## HTTP upload

`POST /api/admin/media/images` accepts exactly one multipart file named `file`.
ADMIN, EDITOR and TEAM_REPORTER may upload; the uploader ID is taken from the
authenticated user, not from form data. Extra form fields and additional files
are rejected. A successful request returns 201 with `id`, `mime_type`, `file_size`,
`width` and `height`. It creates an unassigned media asset; article, gallery and
player associations are not changed.

The endpoint authenticates before parsing multipart data. It counts streamed
request bytes, including requests without Content-Length, allowing the configured
file limit plus 64 KiB for multipart overhead. It then reads at most the file
limit plus one byte from the spooled file. The same file limit is passed to the
image processor. Processing and synchronous database work run in a thread pool.
The upload uses a separate session from authentication.

Responses: 401 for missing authentication, 403 for insufficient role, 400 for
malformed multipart or wrong fields, 413 for excessive request/file bytes, 415 for
non-multipart requests, 422 for rejected images (including pixel limits), and 500
for storage/database failures. Internal persistence details are logged, not
returned in the response.

`MEDIA_DIRECTORY` defaults to `output/media`, resolved against `backend/`
independently of the current working directory. It may be an absolute path to
persistent storage. `MEDIA_MAX_UPLOAD_BYTES` defaults to 20971520 (20 MiB).
The local default is covered by the existing `backend/output/` Git ignore rule.
No static mount exposes this directory. `python-multipart` is an explicit backend
dependency; FastAPI's multipart schema also exposes the upload in API docs.

## Planned integration

Protected image retrieval, the media picker and additional image sizes are not yet
implemented. The upload permission does not grant permission to change a report,
gallery or player-photo assignment; those operations require their own checks.
The intended storage policy keeps the reduced master rather than the camera
original; the image processor itself neither writes nor deletes any files.
Gallery, article and historical player-photo associations remain
separate from image processing.

## Verification

From `backend/`, in the `ttc-backend` environment:

```powershell
python -m pytest tests/test_image_processor.py tests/test_media_storage.py tests/test_media_upload.py tests/test_media_http.py tests/test_backend_architecture.py
```

Pillow is listed in `environment.yml`. For an existing environment, install it
with `python -m pip install Pillow`.

Upload tests use doubles for failure paths and real Pillow/local storage with a
temporary directory and SQLite with foreign keys enabled. They do not access the
application database. PostgreSQL-specific transaction behavior is not covered.
