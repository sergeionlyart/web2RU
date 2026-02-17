# Web2RU

CLI утилита для персонального офлайн‑перевода веб‑страниц (EN → RU) по принципу:
**снапшот страницы (HTML+ассеты) + замена только текста**, без ломания DOM/верстки.

Полная спецификация: `docs/TECHNICAL_SPEC_WEB2RU.md`.

## Быстрый старт (dev)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
```

## Запуск (пример)
```bash
web2ru "https://example.com/page" --open
```

## Качество
См.:
- `AGENTS.md` — правила работы Codex и команды
- `TESTING.md` — стратегия тестирования
- `docs/architecture.md` — архитектура и контракты
