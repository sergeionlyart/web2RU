from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urldefrag

from web2ru.assets.pathing import asset_relative_path
from web2ru.models import AssetRecord
from web2ru.utils import sha256_bytes


@dataclass(slots=True)
class AssetCache:
    records: dict[str, AssetRecord] = field(default_factory=dict)
    url_to_local: dict[str, str] = field(default_factory=dict)

    def _normalize_key(self, url: str) -> str:
        no_frag, _ = urldefrag(url)
        return no_frag

    def has(self, url: str) -> bool:
        return self._normalize_key(url) in self.records

    def get(self, url: str) -> AssetRecord | None:
        return self.records.get(self._normalize_key(url))

    def put(
        self,
        *,
        url: str,
        final_url: str,
        content_type: str | None,
        data: bytes,
        source: str,
        max_asset_mb: int,
    ) -> bool:
        if len(data) > max_asset_mb * 1024 * 1024:
            return False
        key = self._normalize_key(url)
        digest = sha256_bytes(data)
        self.records[key] = AssetRecord(
            url=key,
            final_url=self._normalize_key(final_url),
            content_type=content_type,
            size=len(data),
            sha256=digest,
            data=data,
            source=source,
        )
        return True

    def ensure_local_mapping(self, url: str) -> str:
        key = self._normalize_key(url)
        if key in self.url_to_local:
            return self.url_to_local[key]
        record = self.records.get(key)
        if record is None:
            # Keep external requests blocked: map missing assets to a local target path too.
            # The file may be absent (local 404), but browser will not leak network.
            fake = AssetRecord(
                url=key,
                final_url=key,
                content_type=None,
                size=0,
                sha256=sha256_bytes(key.encode("utf-8")),
                data=b"",
                source="missing",
            )
            rel = asset_relative_path(fake)
            self.url_to_local[key] = rel
            return rel
        rel = asset_relative_path(record)
        self.url_to_local[key] = rel
        return rel

    def write_to_output(self, output_dir: Path) -> None:
        for key, record in self.records.items():
            rel = self.ensure_local_mapping(key)
            target = output_dir / rel.lstrip("./")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(record.data)
