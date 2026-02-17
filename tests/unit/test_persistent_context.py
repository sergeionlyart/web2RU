from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from web2ru.pipeline.persistent_context import (
    is_profile_lock_error,
    profile_dir_in_use,
    remove_profile_singletons,
)


def test_is_profile_lock_error_detects_processsingleton() -> None:
    assert is_profile_lock_error(
        "BrowserType.launch_persistent_context: Failed to create a ProcessSingleton for your profile directory."
    )


def test_is_profile_lock_error_detects_profile_in_use_message() -> None:
    assert is_profile_lock_error("Profile is already in use by another instance of Chromium.")


def test_is_profile_lock_error_ignores_other_errors() -> None:
    assert not is_profile_lock_error("Timeout 30000ms exceeded.")


def test_profile_dir_in_use_matches_user_data_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile_dir = tmp_path / "profile"
    marker = f"--user-data-dir={profile_dir}"

    def fake_run(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(returncode=0, stdout=f"chrome ... {marker} ...\n")

    monkeypatch.setattr("subprocess.run", fake_run)
    assert profile_dir_in_use(profile_dir)


def test_profile_dir_in_use_is_conservative_on_ps_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile_dir = tmp_path / "profile"

    def fake_run(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError

    monkeypatch.setattr("subprocess.run", fake_run)
    assert profile_dir_in_use(profile_dir) is True


def test_remove_profile_singletons(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        (profile_dir / name).write_text("x", encoding="utf-8")

    removed = remove_profile_singletons(profile_dir)
    assert set(removed) == {"SingletonLock", "SingletonCookie", "SingletonSocket"}
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        assert not (profile_dir / name).exists()
