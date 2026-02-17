# Workflow: Release

## Версионирование
SemVer: `MAJOR.MINOR.PATCH`
- PATCH: багфиксы без изменения поведения CLI (или минимальные).
- MINOR: новые опции, расширение поведения backward-compatible.
- MAJOR: изменения дефолтов/форматов/совместимости.

## Steps
1) Freeze: main зелёный, все PR смержены.
2) Run PR-gates locally:
```bash
ruff format .
ruff check .
mypy src
pytest -q
```
3) (Опционально) Live regression.
4) Manual acceptance:
- открыть 3–5 контрольных страниц, убедиться что читается и нет сетевых запросов.
5) Bump version:
- обновить `pyproject.toml` и `CHANGELOG.md`.
6) Tag:
- `git tag vX.Y.Z && git push --tags`
7) Release notes:
- кратко: что изменилось, как откатиться, известные проблемы.

## Human sign-off обязателен
Особенно если менялись extract/token-protect/freeze/assets.
