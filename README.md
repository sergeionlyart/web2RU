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

## OpenAI-домен (устойчивость сессии)
- Для `openai.com` автоматически используется persistent browser profile и reuse `storage_state`
  в кеше (`~/Library/Caches/web2ru` на macOS).
- Межзапросный интервал для `openai.com` настраивается через ENV:
  `WEB2RU_OPENAI_RATE_LIMIT_MS` (по умолчанию `2500`).
- Если страница отдает anti-bot interstitial, утилита завершится явной ошибкой (без ложного “перевода”).

## Medium авторизация (для surf и single)
- Для `medium.com` также используется persistent профиль и сохранение `storage_state`.
- Если Medium требует логин, запустите:
  `web2ru 'https://medium.com/' --auth-capture on --headful`
- После входа в аккаунт нажмите Enter в терминале: сессия сохранится и будет переиспользоваться в следующих запусках.

## Surf-режим (переход по ссылкам)
- В `--mode surf` по умолчанию переписываются и same-origin, и cross-origin ссылки (`--surf-same-origin-only off`).
- Если перевод целевой страницы невозможен, surf показывает понятную страницу ошибки с причиной и ссылкой на оригинал.
- Чтобы ограничить переходы только текущим доменом, используйте `--surf-same-origin-only on`.

## Качество
См.:
- `AGENTS.md` — правила работы Codex и команды
- `TESTING.md` — стратегия тестирования
- `docs/architecture.md` — архитектура и контракты
