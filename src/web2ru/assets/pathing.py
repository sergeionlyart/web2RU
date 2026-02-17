from __future__ import annotations

import mimetypes
import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

from web2ru.models import AssetRecord

_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _clean_segment(value: str) -> str:
    cleaned = _SEGMENT_RE.sub("-", value.strip())
    return cleaned.strip("-") or "asset"


def _extension_from_record(record: AssetRecord) -> str:
    parsed = urlparse(record.final_url)
    suffix = PurePosixPath(parsed.path).suffix
    if suffix:
        return suffix
    if record.content_type:
        ctype = record.content_type.split(";", 1)[0].strip().lower()
        guessed = mimetypes.guess_extension(ctype)
        if guessed:
            return guessed
    return ".bin"


def asset_relative_path(record: AssetRecord) -> str:
    parsed = urlparse(record.final_url)
    host = _clean_segment(parsed.hostname or "unknown-host")
    raw_path = parsed.path or "/index"
    p = PurePosixPath(raw_path)
    parent = [seg for seg in p.parts[:-1] if seg not in {"", "/"}]
    stem = _clean_segment(p.stem or "index")
    ext = _extension_from_record(record)
    filename = f"{stem}__{record.sha256[:10]}{ext}"
    folder = "/".join(_clean_segment(seg) for seg in parent if seg not in {"."})
    if folder:
        return f"./assets/{host}/{folder}/{filename}"
    return f"./assets/{host}/{filename}"
