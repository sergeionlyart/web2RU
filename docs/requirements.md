# Требования Web2RU (выжимка из ТЗ v1.3)

Документ нужен как “рабочая карта” для реализации и контроля качества. Полная спецификация — `docs/TECHNICAL_SPEC_WEB2RU.md`.

## 1. Цель и продукт
CLI утилита `web2ru` делает **персональный офлайн‑перевод одной веб‑страницы** (EN→RU) как локальный snapshot:
- без потери структуры и визуального восприятия;
- **заменяем только текст** и выбранные атрибуты, не ломая DOM.

## 2. MVP-объём (обязательный)
### 2.1 Online фаза (Playwright/Chromium)
- открыть URL, дождаться стабилизации (DOMContentLoaded + post-load-wait + auto-scroll);
- network capture: сохранять ответы (ассеты) в кэш;
- best effort materialize **open Shadow DOM** в Declarative Shadow DOM (`template[shadowrootmode]`) перед `page.content()`;
- зафиксировать `final_url` и `html_dump`.

### 2.2 Offline фаза (локальный HTML парсер)
- распарсить `html_dump` предсказуемым парсером (фиксируем один дефолт);
- удалить/переписать `<base>` (исключить сетевые резолвы);
- asset-scan (HTML + CSS) и best-effort докачка недостающих ресурсов;
- Extract переводимых сегментов:
  - scope auto→main;
  - не переводить `script/style/noscript/code/pre/...`, `template` кроме `template[shadowrootmode]`;
  - дефолтная единица: `translation-unit=block` (с parts для text nodes);
- Token Protector (защита URL/путей/флагов/хешей/идентификаторов);
- Translate через OpenAI Responses API:
  - Structured Outputs (JSON Schema, strict);
  - retry/auto-split/fallback (до textnode), кеш переводов (SQLite);
- Apply: подстановка перевода обратно в **исходные text nodes/атрибуты**;
- переписать ссылки на ассеты в HTML и CSS на строго относительные пути;
- freeze-js=on (нейтрализация JS, CSP/meta refresh, resource hints, iframes, integrity, on* handlers, javascript: URLs);
- сохранить результат как `output/<slug>/...` + `report.json`.

## 3. Нефункциональные требования (must)
- **DOM/верстка сохраняются**: структура узлов, классы, атрибуты.
- Результат **открывается офлайн** без внешних запросов.
- Устойчивость к ошибкам LLM (валидация, retries, auto-split, fallback).
- Производительность: batching, кэш ассетов и переводов, лимиты ассетов и retries.
- Безопасность: по умолчанию freeze-js=on, санитизация.

## 4. CLI (MVP)
Обязательный параметр: `url`.

Ключевые опции:
- render: `--timeout-ms`, `--post-load-wait-ms`, `--auto-scroll`, `--max-scroll-*`, `--headful`
- shadow dom: `--shadow-dom auto|on|off`
- translate: `--model`, `--reasoning-effort none|low|medium|high`, batching/retries
- strategy: `--translation-unit block|textnode`, `--allow-empty-parts`, `--translate-attrs`, `--translate-alt`
- caches/assets: `--cache-dir`, `--no-asset-cache`, `--no-translation-cache`, `--asset-scan`, `--fetch-missing-assets`
- security: `--freeze-js`, `--drop-noscript`, `--block-iframe`
- output: `--open`, `--serve`, `--serve-port`
- logging: `--log-level`

## 5. Артефакты (ожидаемый output)
- `output/<slug>/index.html`
- `output/<slug>/assets/...`
- `output/<slug>/report.json` (статистика, LLM, shadow-dom, ассеты, санитизация, валидации)

## 6. Регресс-набор (live URLs)
Список URL для ручной/ночной регрессии (см. ТЗ 10.1) хранить в `tests/data/regress_urls.txt`.

## 7. Phase 2 (опционально)
- crawl-режим (GitBook) по внутренним ссылкам;
- переписывание внутренних ссылок на локальные.
