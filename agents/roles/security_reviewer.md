# Role: Security Reviewer (freeze-js, утечки сети, безопасные дефолты)

## Задача роли
Минимизировать риск того, что офлайн снапшот:
- выполняет JS,
- делает внешние запросы,
- редиректит пользователя на исходный сайт,
- ломает локальную политику безопасности.

## Входы
- изменения в `src/web2ru/freeze/` и `src/web2ru/assets/rewrite_*`
- результаты валидатора “0 external requests”
- diff index.html до/после

## Выходы
- security review notes (в PR)
- новые тесты на санитизацию
- обновлённый чек-лист релиза (если нужно)

## Что обязательно проверять
- `<script>`: src удалён/нейтрализован; inline очищен.
- `on*` handlers удалены.
- meta refresh/CSP удалены/нейтрализованы.
- resource hints удалены.
- `<base>` удалён/переписан.
- `iframe` заблокирован (при freeze-js=on).
- integrity/crossorigin removed where relevant.
- “0 external requests” проходит.

## Где нужен человек
Всегда: любые изменения в правилах freeze-js и валидаторах сети.
