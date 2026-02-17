from __future__ import annotations

import os
from pathlib import Path

from web2ru.env import load_env_chain


def test_load_env_chain_overrides_empty_existing_var(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("OPENAI_API_KEY=repo_key\n", encoding="utf-8")

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / ".env").write_text("OPENAI_API_KEY=cwd_key\n", encoding="utf-8")

    monkeypatch.chdir(cwd)
    monkeypatch.setenv("OPENAI_API_KEY", "")

    load_env_chain(repo)
    assert os.environ["OPENAI_API_KEY"] == "cwd_key"
