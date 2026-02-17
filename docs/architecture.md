# Архитектура Web2RU (MVP)

## 1) Двухфазный пайплайн (инвариант)
### Фаза A — Online (Playwright)
Цель: получить “финальный” HTML и максимальный набор ассетов без участия LLM.

**Выходы online-фазы:**
- `final_url`
- `html_dump` (DOM serialization)
- `asset_cache` (network capture)
- shadow-dom stats

### Фаза B — Offline (локальная обработка)
Цель: все длительные операции (LLM) и любые модификации делать **без живого DOM**, гарантируя устойчивость и повторяемость.

**Выходы offline-фазы:**
- `index.html` + `assets/...`
- `report.json`

## 2) Модули и границы ответственности
> Идея: “тонкая” CLI и orchestration, всё остальное — чистые компоненты с явным IO.

### 2.1 `pipeline/online_render.py`
- запускает браузер, применяет стратегию готовности и auto-scroll,
- слушает network responses → кладёт в AssetCache,
- (опционально) materialize open Shadow DOM → DSD (`template[shadowrootmode]`),
- возвращает `final_url`, `html_dump`, статистику.

### 2.2 `assets/cache.py` + `assets/rewrite_*`
- `AssetCache`: хранение bytes + метаданные (sha256, content-type, final URL).
- `reference_scan`: DOM+CSS scan нужных URL.
- `fetch_missing`: best-effort httpx GET по списку.
- `rewrite_html_urls`: переписывание ссылок в HTML на `./assets/<host>/<path>__<hash>.<ext>`.
- `rewrite_css_urls`: переписывание `url()` и `@import` в CSS с учётом base URL.

**Инварианты:**
- ссылки строго относительные (`./assets/...`) — никаких `/assets` и никаких внешних URL.

### 2.3 `extract/`
- `scope.py`: поиск main/article/role=main + fallback по плотности текста.
- `block_extractor.py`: строит blocks и parts (text nodes) в DOM-порядке.
- `exclude_rules.py`: теги/атрибуты/эвристики исключений.
- `normalize_ws.py`: lead/trail whitespace split.

**Договор:** extractor возвращает список блоков с устойчивыми `part_id` и ссылками на узлы парсера (node handles).

### 2.4 `translate/`
- `token_protector.py`: выделяет инварианты и заменяет на placeholders, хранит mapping.
- `batcher.py`: группировка по batch-chars и max-items-per-batch.
- `client_openai.py`: вызов Responses API с `text.format=json_schema` (strict).
- `validate.py`: schema + id coverage + placeholder invariants.
- `retry_split.py`: retry → split → fallback.
- `cache_sqlite.py`: кеш переводов keyed by payload hash.

### 2.5 `apply/`
- `apply_blocks.py`: применяет `translated_core` обратно в text nodes:
  - `lead_ws + translated_core + trail_ws`
  - гарантирует, что структура DOM не меняется.
- `apply_attrs.py`: применяет переводы в атрибуты (по allowlist), c правилами alt.

### 2.6 `freeze/`
- `freeze_js.py`: нейтрализация script/src, inline scripts, on* handlers, javascript: URLs,
  meta refresh/CSP, resource hints, base, iframes, SRI.
- `lazy_img_fix.py`: перенос data-src/srcset → src/srcset.
- `noscript.py`: drop-noscript=auto логика (best effort).

### 2.7 `report/`
- единый сборщик `report.json` + стабильная схема полей.
- **важно:** все best-effort ошибки не должны “теряться” — пишем в отчёт.

## 3) Форматы данных (внутренние)
### 3.1 Block payload (внутри программы)
```json
{
  "block_id": "b_000123",
  "context": "…optional…",
  "parts": [
    {
      "id": "t_000001",
      "raw": "  Hello ",
      "lead_ws": "  ",
      "core": "Hello",
      "trail_ws": " ",
      "node_ref": {"path": "...", "kind": "text"} 
    }
  ]
}
```

### 3.2 Translate request (на LLM)
- отправляем только `core` (после Token Protector),
- требуем вернуть `[{"id","text"}]` по JSON Schema (strict).

### 3.3 Apply contract
- по `id` находим part, получаем `translated_core`,
- восстанавливаем пробелы,
- записываем обратно в node.

## 4) Где обязательна проверка человеком
- Любые изменения в `freeze/` (безопасность и UX).
- Любые изменения в Token Protector и правилах “не переводить”.
- Любые изменения в contract/схеме translate.
- Любая оптимизация, меняющая order parts/blocks (риск незаметной деградации).
