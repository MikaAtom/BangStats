"""Generate and cache JPEG thumbnails for screenshot and upload image routes."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from loguru import logger

from bangstats_server.core.config import ENV_STORAGE_ROOT

THUMB_CACHE_ROOT = ENV_STORAGE_ROOT / "cache" / "image_thumbnails"
THUMB_MAX_EDGE_PX = 256
THUMB_JPEG_QUALITY = 82


def _source_fingerprint(path: Path) -> str:
    st = path.stat()
    raw = f"{path.resolve()}:{st.st_mtime_ns}:{st.st_size}".encode()
    return hashlib.sha256(raw).hexdigest()


def _register_heif_opener() -> None:
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except ImportError:
        pass


def get_or_create_thumbnail(source: Path) -> Path:
    """
    Return path to a cached JPEG thumbnail for ``source``.

    Cache key includes resolved path, mtime, and size so edits invalidate entries.
    """
    if not source.is_file():
        raise FileNotFoundError(str(source))

    THUMB_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    fp = _source_fingerprint(source)
    sub = THUMB_CACHE_ROOT / fp[:2] / fp[2:4]
    sub.mkdir(parents=True, exist_ok=True)
    dest = sub / f"{fp}.jpg"

    if dest.exists():
        return dest

    _render_thumbnail_jpeg(source, dest)
    return dest


def _render_thumbnail_jpeg(source: Path, dest: Path) -> None:
    from PIL import Image

    _register_heif_opener()
    with Image.open(source) as im:
        if im.mode in ("RGBA", "LA"):
            background = Image.new("RGB", im.size, (255, 255, 255))
            background.paste(im, mask=im.split()[-1])
            im = background
        elif im.mode != "RGB":
            im = im.convert("RGB")

        im.thumbnail((THUMB_MAX_EDGE_PX, THUMB_MAX_EDGE_PX), Image.Resampling.LANCZOS)

        fd, tmp_name = tempfile.mkstemp(suffix=".jpg", dir=dest.parent)
        try:
            os.close(fd)
            tmp_path = Path(tmp_name)
            im.save(tmp_path, format="JPEG", quality=THUMB_JPEG_QUALITY, optimize=True)
            tmp_path.replace(dest)
        except Exception:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise


def try_thumbnail_path(source: Path) -> Path | None:
    """
    Build a thumbnail path, or return None if generation fails.

    Callers can fall back to serving the original file.
    """
    try:
        return get_or_create_thumbnail(source)
    except Exception as exc:
        logger.warning("Thumbnail generation failed for {}: {}", source, exc)
        return None
