# Workflow: Feature change (изменение поведения / новая опция)

## Когда использовать
- добавляется CLI флаг/режим,
- меняется дефолт,
- меняются правила extract/token-protect/apply/freeze.

## Steps
1) Spec update:
- обновить `docs/requirements.md` и/или `docs/TECHNICAL_SPEC_WEB2RU.md` (если это эволюция),
- зафиксировать риски/допущения.

2) Tests-first:
- добавить unit tests на новую логику,
- если влияет на пайплайн — integration fixture.

3) Implementation:
- минимальные диффы,
- строго соблюдать инварианты (DOM, offline).

4) Report:
- при изменении поведения — расширить report.json.

5) Review:
- security reviewer обязателен для freeze-js/сети.

6) Release note:
- если это user-facing — добавить в changelog.

## Acceptance criteria (универсальные)
- `ruff/mypy/pytest` проходят,
- тесты покрывают новый кейс,
- нет новых внешних запросов в офлайне,
- CLI help/README обновлены (если флаг новый).
