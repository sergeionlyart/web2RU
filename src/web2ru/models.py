from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AssetRecord:
    url: str
    final_url: str
    content_type: str | None
    size: int
    sha256: str
    data: bytes
    source: str


@dataclass(slots=True)
class ShadowDomStats:
    enabled: bool = False
    open_roots_found: int = 0
    templates_inserted: int = 0
    adopted_stylesheets_extracted: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OnlineRenderResult:
    final_url: str
    html_dump: str
    shadow_dom: ShadowDomStats
    scroll_steps: int
    height_before: int
    height_after: int


@dataclass(slots=True)
class NodeRef:
    xpath: str
    field: str  # text|tail|attr
    attr_name: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass(slots=True)
class Part:
    id: str
    raw: str
    lead_ws: str
    core: str
    trail_ws: str
    node_ref: NodeRef
    block_id: str
    translated_core: str | None = None
    protected_core: str | None = None
    token_map: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Block:
    block_id: str
    context: str
    parts: list[Part]


@dataclass(slots=True)
class AttributeItem:
    id: str
    text: str
    hint: str
    node_ref: NodeRef
    translated_text: str | None = None
    protected_text: str | None = None
    token_map: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class TranslationItem:
    id: str
    text: str
    block_id: str | None = None
    hint: str | None = None
    allow_empty: bool = True


@dataclass(slots=True)
class TranslateBatch:
    items: list[TranslationItem]
    chars: int


@dataclass(slots=True)
class OfflineResult:
    output_dir: Path
    index_path: Path
    report_path: Path
    report: dict[str, Any]
