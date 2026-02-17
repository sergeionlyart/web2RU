# Workflow: Live regression (контрольные URL из ТЗ)

## Важно
Live регрессия:
- флейки из-за изменений сайтов/антибота,
- требует network доступа,
- не должна блокировать обычный PR merge.

## Когда запускать
- перед релизом,
- по расписанию (nightly/weekly),
- при больших изменениях extract/assets/freeze/translate.

## Команда (пример)
```bash
python scripts/run_live_regression.py --urls tests/data/regress_urls.txt --out ./_regress_out
```

## Проверки
Для каждого URL:
- output создан,
- `report.json` без критических ошибок,
- Playwright check: **0 external requests** при `--serve`,
- best-effort screenshot,
- если shadow_dom.open_roots_found > 0 → в index.html есть `shadowrootmode`.

## Как разбирать фейлы
- если missing assets: смотреть `report.missing_assets[]`
- если external requests: смотреть request log и правило переписывания URL
- если пустой перевод: смотреть translate retries/fallback
- если layout белый: смотреть freeze-js (не вырезали ли нужное)
