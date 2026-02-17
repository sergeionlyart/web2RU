from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir


@dataclass(slots=True)
class RunConfig:
    url: str
    fast: bool = False
    model: str = "gpt-5.1"
    reasoning_effort: str = "medium"
    max_output_tokens: int = 8192
    batch_chars: int = 4000
    max_items_per_batch: int = 40
    max_retries: int = 6
    timeout_ms: int = 60000
    post_load_wait_ms: int = 1500
    auto_scroll: bool = True
    max_scroll_steps: int = 25
    max_scroll_ms: int = 20000
    shadow_dom: str = "auto"  # auto|on|off
    scope: str = "auto"  # auto|main|page
    translation_unit: str = "block"  # block|textnode
    allow_empty_parts: bool = True
    translate_attrs: bool = True
    translate_alt: str = "auto"  # auto|on|off
    token_protect: bool = True
    token_protect_strict: bool = False
    cache_dir: Path = Path(user_cache_dir("web2ru"))
    use_asset_cache: bool = True
    use_translation_cache: bool = True
    max_asset_mb: int = 15
    asset_scan: bool = True
    fetch_missing_assets: bool = True
    freeze_js: str = "auto"  # auto|on|off
    drop_noscript: str = "auto"  # auto|on|off
    block_iframe: str = "auto"  # auto|on|off
    open_result: bool = False
    serve: bool = False
    serve_port: int = 0
    headful: bool = False
    log_level: str = "info"
    output_root: Path = Path("output")
    exclude_selectors: list[str] = None  # type: ignore[assignment]
    api_key: str | None = None

    def __post_init__(self) -> None:
        if self.exclude_selectors is None:
            self.exclude_selectors = []

    @property
    def freeze_js_enabled(self) -> bool:
        return self.freeze_js in {"on", "auto"}

    @property
    def shadow_dom_enabled(self) -> bool:
        return self.shadow_dom in {"on", "auto"}

    @property
    def block_iframe_enabled(self) -> bool:
        return self.block_iframe == "on" or (self.block_iframe == "auto" and self.freeze_js_enabled)
