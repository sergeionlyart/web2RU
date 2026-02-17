from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

_RATE_LIMIT_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    host: str | None
    auth_provider: str | None
    use_persistent_profile: bool
    profile_dir: Path | None
    storage_state_path: Path | None
    min_interval_ms: int


def build_session_policy(*, url: str, cache_dir: Path, openai_min_interval_ms: int) -> SessionPolicy:
    host = (urlparse(url).hostname or "").strip().lower()
    if not host.endswith("openai.com"):
        if host.endswith("medium.com"):
            return _persistent_policy(
                host=host,
                auth_provider="medium",
                cache_dir=cache_dir,
                min_interval_ms=0,
            )
        return SessionPolicy(
            host=None,
            auth_provider=None,
            use_persistent_profile=False,
            profile_dir=None,
            storage_state_path=None,
            min_interval_ms=0,
        )

    return _persistent_policy(
        host=host,
        auth_provider=None,
        cache_dir=cache_dir,
        min_interval_ms=max(openai_min_interval_ms, 0),
    )


def enforce_domain_rate_limit(
    *,
    policy: SessionPolicy,
    cache_dir: Path,
    now_fn: Callable[[], float] = time.time,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    if policy.host is None or policy.min_interval_ms <= 0:
        return

    marker_path = cache_dir / "rate_limit" / f"{policy.host}.json"
    with _RATE_LIMIT_LOCK:
        now = float(now_fn())
        last_ts = _read_last_timestamp(marker_path)
        interval_s = policy.min_interval_ms / 1000.0
        wait_s = max(0.0, interval_s - (now - last_ts))
        if wait_s > 0:
            sleep_fn(wait_s)
            now = float(now_fn())
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps({"last_request_ts": now}), encoding="utf-8")


def resolve_storage_state_input(policy: SessionPolicy) -> str | None:
    if policy.storage_state_path is None:
        return None
    if not policy.storage_state_path.exists():
        return None
    return str(policy.storage_state_path)


def load_storage_state(policy: SessionPolicy) -> dict[str, object] | None:
    if policy.storage_state_path is None:
        return None
    if not policy.storage_state_path.exists():
        return None
    try:
        payload = json.loads(policy.storage_state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(payload, dict):
        return payload
    return None


def persist_storage_state(policy: SessionPolicy, storage_state: object) -> None:
    if policy.storage_state_path is None:
        return
    policy.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
    policy.storage_state_path.write_text(
        json.dumps(storage_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_last_timestamp(path: Path) -> float:
    if not path.exists():
        return 0.0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0.0
    if not isinstance(payload, dict):
        return 0.0
    value = payload.get("last_request_ts")
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _persistent_policy(
    *, host: str, auth_provider: str | None, cache_dir: Path, min_interval_ms: int
) -> SessionPolicy:
    safe_host = host.replace(":", "_")
    return SessionPolicy(
        host=host,
        auth_provider=auth_provider,
        use_persistent_profile=True,
        profile_dir=cache_dir / "browser_profiles" / safe_host,
        storage_state_path=cache_dir / "storage_state" / f"{safe_host}.json",
        min_interval_ms=max(min_interval_ms, 0),
    )
