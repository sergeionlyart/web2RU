from __future__ import annotations

import subprocess
from pathlib import Path

from playwright.sync_api import BrowserContext, Playwright
from playwright.sync_api import Error as PlaywrightError


def is_profile_lock_error(message: str) -> bool:
    lowered = message.lower()
    return "processsingleton" in lowered or "profile is already in use" in lowered


def profile_dir_in_use(profile_dir: Path) -> bool:
    """Best-effort detection of a Chromium process using the given user-data-dir.

    We are conservative: if we cannot inspect running processes, assume the profile is in use
    to avoid deleting singleton lock files while another Chromium instance is running.
    """

    ps_output = _ps_commands_output()
    if ps_output is None:
        return True

    marker = f"--user-data-dir={profile_dir}"
    if marker in ps_output:
        return True

    # Fallback for call logs that omit the leading "--".
    marker = f"user-data-dir={profile_dir}"
    return marker in ps_output


def remove_profile_singletons(profile_dir: Path) -> list[str]:
    removed: list[str] = []
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        path = profile_dir / name
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            continue
        removed.append(name)
    return removed


def launch_persistent_context_with_lock_recovery(
    *,
    playwright: Playwright,
    profile_dir: Path,
    headless: bool,
    args: list[str] | None = None,
) -> BrowserContext:
    try:
        return playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=headless,
            args=args,
        )
    except PlaywrightError as exc:
        message = str(exc)
        if not is_profile_lock_error(message):
            raise

        if not profile_dir_in_use(profile_dir):
            remove_profile_singletons(profile_dir)
            try:
                return playwright.chromium.launch_persistent_context(
                    str(profile_dir),
                    headless=headless,
                    args=args,
                )
            except PlaywrightError as retry_exc:
                retry_message = str(retry_exc)
                if is_profile_lock_error(retry_message):
                    raise RuntimeError(
                        "Chromium profile directory is locked and cannot be recovered automatically. "
                        f"Close any Chromium instances using {profile_dir} and retry."
                    ) from retry_exc
                raise

        raise RuntimeError(
            "Chromium profile directory is already in use by another Chromium process. "
            f"Close any Chromium instances using {profile_dir} and retry."
        ) from exc


def _ps_commands_output() -> str | None:
    for cmd in (
        ["ps", "axww", "-o", "command="],
        ["ps", "auxww"],
        ["ps", "aux"],
    ):
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return None
        if result.returncode == 0 and result.stdout:
            return result.stdout
    return None
