# Testing strategy (Web2RU)

## 1) Зачем так строго
Проект ломается не “крэшем”, а тихими деградациями:
- чуть изменили DOM и поехала верстка,
- один внешний запрос остался — офлайн “не офлайн”,
- LLM “перевёл” URL/флаг/идентификатор — контент стал неверным,
- ассеты не переписались и CDN остался снаружи.

Поэтому тесты должны ловить инварианты.

## 2) Пирамида тестов
### 2.1 Lint / format (быстро, всегда)
- `ruff format .`
- `ruff check .`

### 2.2 Type checks
- `mypy src`

### 2.3 Unit tests (детерминированные)
Цель: покрыть все трансформеры на фикстурах без сети:
- Token Protector: placeholder invariants, strict mode
- Extract: scope selection, skip rules, block/parts building
- Apply: whitespace rules, id mapping
- Asset rewrite: HTML rewrite, CSS url()/@import
- Freeze-JS: sanitization transforms

Команда:
```bash
pytest -q tests/unit
```

### 2.4 Integration tests (фикстуры)
Запускаем куски пайплайна на сохранённых HTML/CSS/asset фикстурах:
- “offline pipeline” end-to-end без live сети.
Команда:
```bash
pytest -q tests/integration
```

### 2.5 E2E (CLI)
Запуск `web2ru` на локальном тестовом сервере/фикстуре.
Команда:
```bash
pytest -q tests/e2e
```

### 2.6 Live regression (opt-in)
Запуск по реальным URL (может быть флейки).
- не блокирует PR,
- запускается manual/cron.
Команда:
```bash
python scripts/run_live_regression.py --urls tests/data/regress_urls.txt --out ./_regress_out
```

## 3) Что блокирует PR (CI gates)
Минимальный набор:
- format/lint
- mypy
- unit + integration (fixture-only)

Live regression — отдельная джоба или ручной запуск.

## 4) Финальные проверки перед продакшеном
### 4.1 Smoke
- `web2ru <url>` на одной контрольной странице,
- убедиться что output создан и открывается.

### 4.2 Regression (желательно)
- прогнать все URL из `tests/data/regress_urls.txt` (best effort),
- проверить `0 external requests`.

### 4.3 Acceptance (ручной чек-лист)
- нет “белого экрана”,
- нет “Enable JavaScript” оверлеев,
- локально грузятся картинки/шрифты,
- структура страницы визуально похожа на оригинал,
- перевод не ломает inline разметку.
