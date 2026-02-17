from __future__ import annotations

import json
from pathlib import Path

from web2ru.pipeline.session_policy import (
    build_session_policy,
    enforce_domain_rate_limit,
    load_storage_state,
    persist_storage_state,
    resolve_storage_state_input,
)


def test_build_session_policy_for_openai_domain(tmp_path: Path) -> None:
    policy = build_session_policy(
        url="https://openai.com/index/harness-engineering/",
        cache_dir=tmp_path,
        openai_min_interval_ms=2500,
    )

    assert policy.host == "openai.com"
    assert policy.use_persistent_profile is True
    assert policy.profile_dir == tmp_path / "browser_profiles" / "openai.com"
    assert policy.storage_state_path == tmp_path / "storage_state" / "openai.com.json"
    assert policy.min_interval_ms == 2500


def test_build_session_policy_for_non_openai_domain(tmp_path: Path) -> None:
    policy = build_session_policy(
        url="https://simonwillison.net/",
        cache_dir=tmp_path,
        openai_min_interval_ms=2500,
    )

    assert policy.host is None
    assert policy.use_persistent_profile is False
    assert policy.profile_dir is None
    assert policy.storage_state_path is None
    assert policy.min_interval_ms == 0


def test_enforce_domain_rate_limit_sleeps_when_needed(tmp_path: Path) -> None:
    policy = build_session_policy(
        url="https://openai.com/index/harness-engineering/",
        cache_dir=tmp_path,
        openai_min_interval_ms=1000,
    )
    assert policy.host is not None

    marker = tmp_path / "rate_limit" / f"{policy.host}.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"last_request_ts": 100.0}), encoding="utf-8")

    now_values = iter([100.2, 101.2])
    sleep_calls: list[float] = []

    enforce_domain_rate_limit(
        policy=policy,
        cache_dir=tmp_path,
        now_fn=lambda: next(now_values),
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
    )

    assert len(sleep_calls) == 1
    assert abs(sleep_calls[0] - 0.8) < 0.01

    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert float(payload["last_request_ts"]) == 101.2


def test_resolve_storage_state_input_returns_none_for_missing_file(tmp_path: Path) -> None:
    policy = build_session_policy(
        url="https://openai.com/index/harness-engineering/",
        cache_dir=tmp_path,
        openai_min_interval_ms=2500,
    )
    assert resolve_storage_state_input(policy) is None


def test_storage_state_round_trip(tmp_path: Path) -> None:
    policy = build_session_policy(
        url="https://openai.com/index/harness-engineering/",
        cache_dir=tmp_path,
        openai_min_interval_ms=2500,
    )
    payload = {"cookies": [{"name": "cf_clearance", "value": "abc"}], "origins": []}

    persist_storage_state(policy, payload)

    loaded = load_storage_state(policy)
    assert loaded is not None
    assert loaded["cookies"] == payload["cookies"]
    assert resolve_storage_state_input(policy) is not None
