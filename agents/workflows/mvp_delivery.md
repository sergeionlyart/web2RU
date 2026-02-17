# Workflow: MVP delivery (Milestone 1)

## Цель
Выпустить MVP, полностью соответствующий ТЗ Milestone 1:
- двухфазный пайплайн,
- shadow-dom materialization (best effort),
- block-mode Extract + Token Protector,
- Translate (Structured Outputs + retry/auto-split + fallback),
- ассеты capture + scan + rewrite (HTML+CSS) + относительные пути,
- freeze-js hardening,
- report + регресс-скрипт.

## Принцип разбиения задач для Codex
Делим на “сквозные вертикали”, но маленькими PR:
1 PR = 1 подсистема + unit tests + docs notes.

## Шаги (рекомендованный order)
### 1) Repo scaffold
- pyproject, линтеры, pytest, basic CLI skeleton.
**Acceptance:** `pytest`, `ruff`, `mypy` проходят на пустом проекте.

### 2) AssetCache + network capture (online)
- Playwright render + capture responses → cache.
**Acceptance:** на простой странице сохраняются CSS+images; report пишет capture stats.

### 3) HTML dump + offline parse baseline
- `html_dump` сохраняется; offline parser читает/пишет index.html.
**Acceptance:** для fixture HTML round-trip не рушит базовую структуру.

### 4) Shadow DOM materialization (best effort)
- вставка `template[shadowrootmode]` для open shadow roots.
**Acceptance:** в отчёте корректные counters; fixture test на наличие `shadowrootmode`.

### 5) Extract block-mode + exclude rules
- scope main, exclude header/nav/footer, запретные теги.
**Acceptance:** unit тесты на выбор scope + на skip правил.

### 6) Token Protector
- placeholder mapping + strict validation.
**Acceptance:** unit тесты на URL/paths/flags/ids invariants.

### 7) Translate client (Responses API) + schema validation
- `text.format=json_schema(strict)`; parsing; retries; auto-split; fallback.
**Acceptance:** детерминированные тесты на валидаторы + “симуляция” плохого ответа.

### 8) Apply translations (text nodes + attrs)
- сохранение lead/trail whitespace; translate attrs allowlist.
**Acceptance:** unit тест на “DOM unchanged” (сравнение tree shape) + корректный текст.

### 9) Rewrite assets in HTML+CSS
- rewrite url()/@import, src/srcset, link href; relative paths; strip integrity.
**Acceptance:** unit тесты на rewrite; output не содержит `http(s)://` в ссылках на ассеты.

### 10) Freeze-JS + sanitization
- disable scripts/handlers/meta hints/base/iframes, lazy img fix, noscript policy.
**Acceptance:** unit tests + integration fixture.

### 11) Validator: 0 external requests
- serve output, open in Playwright, block external, assert 0.
**Acceptance:** regression runner passes for fixture; live URLs (manual/cron) — best effort.

## Выходной чек-лист (Go/No-Go)
- Все PR-гейты зелёные (lint/type/unit/integration).
- Live-regression (если запускали) не показывает внешних запросов.
- Manual visual check на контрольных страницах.
