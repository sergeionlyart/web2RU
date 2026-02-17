# Workflow: Bugfix / regression triage

## Цель
Быстро воспроизвести баг, зафиксировать тестом, исправить без побочных эффектов.

## Steps
1) Repro minimal:
- сохранить входные данные: `html_dump` + минимальный набор ассетов (fixture),
- если баг только на live странице — записать `source_url`, `final_url`, параметры запуска.

2) Define expected:
- что именно сломано: внешний запрос? пропал текст? сломался layout? испорчен токен?
- какой инвариант нарушен.

3) Add test:
- unit test (предпочтительно) или integration fixture.
- тест должен падать до фикса.

4) Fix:
- точечная правка.

5) Validate:
- прогон всех quality gates.
- если баг был про сеть — прогон валидатора external requests.

6) Postmortem:
- если причина системная — записать в `docs/risks_and_assumptions.md`.

## Когда нужен человек
- если для воспроизведения нужен live network (разрешение),
- если исправление затрагивает freeze-js или Token Protector.
