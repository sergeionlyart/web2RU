from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_base_report(
    *,
    source_url: str,
    final_url: str,
    run_params: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_url": source_url,
        "final_url": final_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "params": run_params,
        "stats": {},
        "llm": {},
        "quality": {},
        "shadow_dom": {},
        "assets": {},
        "sanitization": {},
        "validation": {},
        "warnings": [],
        "errors": [],
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
