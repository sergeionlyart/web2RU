from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values


def load_env_chain(repo_root: Path) -> None:
    """
    Load env in the order required by spec:
    1) existing environment variables,
    2) .env in cwd,
    3) .env in repo root.
    Existing variables are never overwritten.
    """
    for env_path in [Path.cwd() / ".env", repo_root / ".env"]:
        if not env_path.exists():
            continue
        values = dotenv_values(env_path)
        for key, value in values.items():
            if value is None:
                continue
            current = os.environ.get(key)
            if current is None or current.strip() == "":
                os.environ[key] = value
