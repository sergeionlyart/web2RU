Вводная по функционалу скрипта

Мы делаем утилиту для персонального офлайн-перевода материалов из интернета (статьи, блоги, документация) с целью получить локальную русскую версию страницы, которую можно открыть и читать как оригинал — без потери структуры, стилей и визуального восприятия.

Ключевой принцип: это не “перевод текста отдельно”, а снятие снапшота страницы (HTML \+ ассеты) и замена только текстового контента на русский без ломания DOM/верстки.

Базовый пайплайн скрипта:

	1\.	Загрузка и рендер страницы (включая JS-страницы) до стабильного состояния.

	2\.	Сохранение офлайн-копии: HTML \+ все необходимые ассеты (CSS/JS/шрифты/картинки) так, чтобы страница открывалась локально.

	3\.	Извлечение переводимых сегментов: аккуратно собрать именно пользовательский текст (заголовки, абзацы, пункты, подписи), исключая код, служебные элементы, повторяющиеся блоки и т.п.

	4\.	Перевод сегментов через LLM (GPT-5.1 через OpenAI Response API, reasoning=Medium).

	5\.	Обратная вставка перевода в исходный HTML так, чтобы:

	•	структура DOM не менялась,

	•	стили/классы/атрибуты сохранялись,

	•	ссылки, кодовые блоки, inline-элементы не ломались,

	•	текст корректно отображался в исходной типографике.

	6\.	Выходной результат: локальная папка/пакет, открывающийся офлайн (оригинальная структура \+ русский текст).

Контрольные сайты для анализа типовых страниц и регрессионного теста

	•	https://openai.com/index/harness-engineering/

	•	https://simonwillison.net/

	•	https://edisonscientific.gitbook.io/edison-cookbook/paperqa

	•	https://matt.might.net/articles/peer-fortress/

	•	https://minimaxir.com/2025/11/nano-banana-prompts/

---

# **Web2RU — утилита персонального офлайн‑перевода веб‑страниц (EN → RU)**

**Статус:** финальное ТЗ для разработки (вариант B, укреплённый)

**Версия:** 1.3 (2026-02-16)

**Целевая платформа:** macOS / Linux (Windows — best effort)

**Язык перевода (MVP):** русский (ru)

**Рендер:** Playwright (Chromium)

**Перевод:** OpenAI Responses API (gpt-5.1 по умолчанию), Structured Outputs (JSON Schema), reasoning.effort=medium (по умолчанию)

---

## **История изменений**

### **1.3 → относительно 1.2**

* Добавлена **best‑effort поддержка Shadow DOM**: материализация open shadow roots в **Declarative Shadow DOM** (template\[shadowrootmode\]) перед снятием html\_dump. Это нужно, чтобы текст внутри Shadow DOM не “исчезал” после freeze-js=on при открытии офлайн.

* Уточнены исключения Extract: обычные  по‑прежнему не переводим, **кроме** template\[shadowrootmode\] (его содержимое переводится и проходит asset-scan/rewrite).

* Добавлен режим **allow-empty-parts** (по умолчанию on) для block‑mode: разрешены пустые parts и перераспределение текста между соседними parts при сохранении списка id и порядка частей. Это улучшает естественность русского на инлайн‑разметке.

* Обновлены валидаторы ответа LLM и условия retry/auto‑split: пустые parts больше не являются автоматической ошибкой; ошибкой считается потеря значимого текста блока, пропажа id или нарушение Token Protector.

* report.json расширен статистикой по Shadow DOM и empty-parts.

### **1.2 → относительно 1.1**

* Добавлен **Token Protector**: защита URL/хешей/CLI‑флагов/кодов/идентификаторов от “перевода” и искажений.

* Ассеты: переход на схему **Network capture \+ Reference scan** (после дампа HTML/CSS ищем недостающие ссылки и доскачиваем best effort).

* Усилен freeze-js=on: нейтрализация , CSP/meta refresh, resource hints, iframe, удаление integrity (SRI) при переписывании, фиксы lazy‑img.

* Уточнена семантика –reasoning-effort=none: это **не значение API**, а режим “не отправлять параметр reasoning”.

---

## **0\. Контекст и цель**

Мы разрабатываем CLI‑утилиту, которая:

1. загружает и рендерит страницу (включая JS‑страницы) до устойчивого состояния;

2. сохраняет офлайн‑копию (HTML \+ ассеты) так, чтобы страница открывалась локально;

3. аккуратно извлекает переводимые сегменты (пользовательский текст) без ломания DOM;

4. переводит сегменты через LLM;

5. подставляет перевод обратно **без изменения структуры DOM/верстки**;

6. выдаёт локальную папку, которую можно открыть офлайн и читать как оригинал, но на русском.

**Ключевой принцип:** это “снапшот страницы \+ замена текстового контента”, а не генерация новой HTML‑страницы.

---

## **1\. Нефункциональные требования**

### **1.1 Качество и устойчивость**

* DOM/верстка MUST сохраниться: классы, атрибуты, структура узлов.

* Перевод MUST изменять только текстовые ноды и выбранные атрибуты.

* Перевод MUST не ломать inline‑элементы (, , , …) и ссылки.

* Результат MUST открываться офлайн без внешних сетевых запросов (см. 8.4, 10.2).

### **1.2 Архитектурная устойчивость**

* **Двухфазный пайплайн**: online‑рендер и offline‑перевод (без живого DOM).

* Ошибки/нестабильность LLM MUST обрабатываться retry/auto-split/fallback.

### **1.3 Безопасность**

* По умолчанию freeze-js=on (auto→on).

* Удалять/нейтрализовать элементы, ведущие к внешним запросам (см. 8).

### **1.4 Производительность и стоимость**

* Поддержка batching и кешей ассетов/переводов.

* Лимиты на размер ассетов и число retries.

---

## **2\. Объём работ**

### **2.1 MVP (обязательный)**

Одна страница по URL:

* Playwright‑рендер \+ автоскролл (lazy‑load),

* сохранение сетевых ассетов (network capture),

* (опционально) materialize Shadow DOM (template\[shadowrootmode\], best effort; см. 4.3),

* дамп финального HTML,

* офлайн‑парсинг HTML,

* Extract (контекстные блоки) \+ Token Protector,

* Translate через OpenAI Responses API (Structured Outputs),

* Apply (подстановка перевода в текстовые ноды/атрибуты),

* ассеты:

  * переписывание HTML \+ CSS (url()/@import),

  * reference scan \+ best‑effort доскачивание недостающих ресурсов,

* freeze‑JS \+ санитизация,

* сохранение снапшота в папку,

* report.json,

* опционально –serve и –open.

### **2.2 Phase 2 (опционально, предусмотрено архитектурой)**

* Crawl‑режим для документации (GitBook) по внутренним ссылкам.

* Переписывание внутренних ссылок a\[href\] на локальные.

---

## **3\. CLI и конфигурация**

### **3.1 Команда**

web2ru  \[options\]

### **3.2 Обязательные параметры**

* url — исходная страница.

### **3.3 Опции MVP**

**Рендер / сеть**

* –open — открыть результат (см. также –serve).

* –headful — запуск Playwright в видимом режиме (отладка).

* –timeout-ms  — общий таймаут online‑фазы (по умолчанию 60\_000).

* –post-load-wait-ms  — пауза после “готовности” (по умолчанию 1\_500).

* –auto-scroll on|off — автоскролл (по умолчанию on).

* –shadow-dom auto|on|off — best‑effort материализовать open Shadow DOM в template\[shadowrootmode\] перед html\_dump (по умолчанию auto→on; см. 4.3).

* –max-scroll-steps  — лимит шагов (по умолчанию 25).

* –max-scroll-ms  — лимит времени автоскролла (по умолчанию 20\_000).

**Область перевода**

* –scope auto|main|page — область перевода (по умолчанию auto→main).

* –exclude-selector “” — можно задавать несколько раз; исключает узлы из перевода.

**Стратегия извлечения/перевода**

* –translation-unit block|textnode

  * block (по умолчанию): контекстный перевод внутри блока с применением в исходные text nodes (рекомендуется).

  * textnode: перевод каждой текстовой ноды отдельно (fallback/дешевле, но хуже качество на инлайн‑разметке).

* –allow-empty-parts on|off — (только для translation-unit=block) разрешить пустые parts и перераспределение текста между соседними parts при сохранении порядка id (по умолчанию on).

* –translate-attrs on|off — перевод атрибутов (по умолчанию on).

* –translate-alt auto|on|off — перевод alt (по умолчанию auto).

**Token Protector**

* –token-protect on|off — защита технических токенов (по умолчанию on).

* –token-protect-strict on|off — строгий режим (по умолчанию off; см. 6.5).

**LLM**

* –model  — модель (по умолчанию gpt-5.1).

* –reasoning-effort none|low|medium|high

  * medium (по умолчанию).

  * none означает: **не отправлять поле reasoning в запросе** (а не effort=“none”).

* –max-output-tokens  — верхняя граница токенов генерации (по умолчанию 8192).

* –batch-chars  — лимит суммарных символов core на запрос к LLM (по умолчанию 4\_000).

* –max-items-per-batch  — лимит parts на запрос (по умолчанию 40).

* –max-retries  — число повторов при ошибках/обрывах (по умолчанию 6).

**Ассеты**

* –cache-dir  — корень кешей (по умолчанию platformdirs user\_cache\_dir).

* –no-asset-cache — не читать/не писать кеш ассетов.

* –no-translation-cache — не читать/не писать кеш переводов.

* –max-asset-mb  — не сохранять ассеты больше N МБ (по умолчанию 15).

* –asset-scan on|off — reference scan по HTML/CSS (по умолчанию on).

* –fetch-missing-assets on|off — пытаться доскачивать ассеты, не попавшие в capture (по умолчанию on).

**JS / безопасность**

* –freeze-js auto|on|off — нейтрализация JS (по умолчанию auto→on).

* –drop-noscript auto|on|off — обработка  (по умолчанию auto; см. 8.5).

* –block-iframe auto|on|off — блокировать  (по умолчанию auto→on при freeze-js=on).

**Открытие результата**

* –serve on|off — поднять локальный статический сервер (по умолчанию on при –open, иначе off).

* –serve-port  — порт (по умолчанию 0 → выбрать свободный).

**Логи**

* –log-level debug|info|warning|error — по умолчанию info.

### **3.4 Переменные окружения (.env)**

* OPENAI\_API\_KEY — **обязательно**.

* WEB2RU\_MODEL (опционально).

* WEB2RU\_REASONING\_EFFORT (опционально).

* WEB2RU\_CACHE\_DIR (опционально).

* WEB2RU\_SHADOW\_DOM (опционально; auto|on|off).

* WEB2RU\_ALLOW\_EMPTY\_PARTS (опционально; on|off).

Правило загрузки:

1. переменные окружения,

2. затем .env в текущей рабочей директории,

3. затем .env в корне репозитория (если CLI запускается из репо).

---

## **4\. Пайплайн обработки страницы (MVP)**

### **4.1 Двухфазная архитектура**

#### **Фаза A — Online (Playwright)**

**Цель:** получить “финальное” HTML‑состояние и ассеты, **не выполняя перевод в живом DOM**.

Шаги:

1. Открыть страницу в Playwright (Chromium).

2. Перехватывать ответы сети и сохранять ассеты в AssetCache (см. 7.2) на протяжении online‑фазы.

3. Дождаться “готовности” (см. 4.2), выполнить auto-scroll (если включён).

4. Если –shadow-dom \!= off — выполнить best‑effort материализацию open Shadow DOM (см. 4.3).

5. Снять дамп:

   * final\_url (после редиректов),

   * html\_dump \= page.content() (DOM‑сериализация на момент стабилизации).

6. Закрыть браузер.

#### **Фаза B — Offline (локальный HTML‑парсер)**

**Цель:** стабильность при длительных LLM‑операциях и отсутствие проблем “detached nodes”.

Шаги:

1. Распарсить html\_dump (парсер выбирается по критерию предсказуемой сериализации; зафиксировать один дефолт).

2. Выполнить **санитизацию базы URL**:

   * если есть  — удалить или переписать на ./ (см. 8.2), чтобы исключить сетевые резолвы.

3. Выполнить **ассет‑reference scan** (если включён) и при необходимости доскачать недостающие ресурсы (см. 7.3–7.4).

4. Выполнить **Extract** (раздел 5\) → блоки/части.

5. Выполнить **Translate** (раздел 6\) → переводы.

6. Выполнить **Apply**: замена текста/атрибутов без изменения структуры DOM.

7. Переписать URL ассетов в HTML (7.6) и CSS (7.7).

8. Выполнить **Freeze JS** (раздел 8).

9. Сохранить index.html, assets/…, report.json.

### **4.2 Готовность страницы**

networkidle не является обязательным критерием (часто “никогда” не наступает).

MVP‑стратегия готовности:

* дождаться domcontentloaded;

* ждать post-load-wait-ms;

* выполнить автоскролл (если включён) с лимитами max-scroll-steps/max-scroll-ms;

* ждать post-load-wait-ms и снимать page.content().

В report.json фиксировать: шаги скролла, изменение высоты, кол-во сохранённых ассетов.

### **4.3 Shadow DOM (best effort, MVP)**

Проблема: часть современных сайтов рендерит пользовательский текст внутри **Shadow DOM**. При сохранении HTML через page.content() этот текст **не попадает в дамп**, а при freeze-js=on офлайн‑страница может “обеднеть” (текст/кнопки/лейаут исчезают).

**Решение (best effort):** перед снятием html\_dump материализовать **open shadow roots** в HTML через **Declarative Shadow DOM**.

Поведение при –shadow-dom=on (или auto→on):

1. После готовности страницы (4.2) выполнить page.evaluate():

   * пройти по дереву DOM (document \+ вложенные shadowRoot, если они open),

   * для каждого элемента host, у которого host.shadowRoot && host.shadowRoot.mode \=== "open":

     * создать template с атрибутом shadowrootmode="open",

     * (опционально) добавить data-web2ru-shadow="1",

     * поместить внутрь template HTML‑сериализацию host.shadowRoot (включая \<style\> внутри shadow root),

     * **best effort для adoptedStyleSheets:** если host.shadowRoot.adoptedStyleSheets доступны и можно прочитать cssRules, то слить правила в \<style data-web2ru-adopted="1"\>...\</style\> в начале template.

   * вставить template внутрь host (рекомендуемо первым child), не удаляя существующих light‑DOM детей.

2. Зафиксировать в report.json:

   * shadow\_dom.enabled,

   * shadow\_dom.open\_roots\_found,

   * shadow\_dom.templates\_inserted,

   * shadow\_dom.adopted\_stylesheets\_extracted,

   * shadow\_dom.errors (best effort).

Ограничения (ожидаемые):

* **closed shadow roots** недоступны — материализация невозможна.

* adoptedStyleSheets может быть не сериализуем (исключения безопасности/кросс‑доменные правила) — допускаем частичную потерю стилей shadow‑контента.

* Declarative Shadow DOM зависит от поддержки браузера при просмотре офлайна (ориентируемся на современный Chromium).

Требование для Offline‑фазы:

* Extract/asset-scan/rewrite MUST обходить и переводить/переписывать ресурсы **внутри template\[shadowrootmode\]** (это часть пользовательского контента shadow‑компонентов).

---

## **5\. Извлечение переводимых строк (Extract)**

### **5.1 Выбор области перевода (scope)**

* main: использовать первый найденный из:

  1. main,

  2. article,

  3. \[role=“main”\],

  4. контейнер с максимальной плотностью текста среди section/div (fallback),

  5. document.body (последний fallback).

* page: document.body.

* auto \= main.

### **5.2 Исключения (не переводить)**

**По тегам (жёстко):**

* script, style, noscript (см. 8.5), code, pre, textarea, svg, math.

* template — не переводить, **кроме** template\[shadowrootmode\] (см. 4.3): переводить содержимое template.content.

**По атрибутам/семантике (best effort):**

* элементы/родители с aria-hidden=“true”, hidden.

* элементы с translate=“no” или class\*=“notranslate” / data-no-translate (если встретились).

* узлы внутри input/select/option (кроме выбранных атрибутов, если включено).

**По строковым признакам (эвристика, до Token Protector):**

* строки из одних пробелов/пунктуации,

* “иконки‑слова” (GitBook): короткие токены ^\[a-z0-9-\]{3,}$ внутри элементов с role=“img” или рядом с SVG,

* строки, похожие на URL/email/UUID/хеш/путь — скорее защищаем, чем переводим.

**Через –exclude-selector:**

* по умолчанию в main‑scope исключать:

  * header, nav, footer, aside, \[role=“navigation”\].

### **5.3 Единица перевода:**

### **translation-unit=block**

### **(по умолчанию)**

#### **5.3.1 Почему block‑подход**

Перевод изолированных text nodes ломает контекст на инлайн‑разметке (, , …).

Поэтому дефолт: **перевод блока с контекстом**, но применение результата — обратно в исходные text nodes (DOM сохраняется).

#### **5.3.2 Что такое “блок”**

Блок — DOM‑элемент, выступающий как минимальная смысловая единица.

**Primary block tags:**

* p, li, h1…h6, blockquote, figcaption, caption, dd, dt, td, th, summary.

**Fallback:**

* ближайший предок из div/section, который:

  * содержит ≥ 120 символов видимого текста,

  * не содержит вложенных primary‑блоков.

#### **5.3.3 Как строится payload**

Для каждого блока:

* собрать все текстовые ноды внутри блока (в DOM‑порядке), исключая запрещённые теги;

  * обход MUST включать содержимое template\[shadowrootmode\] (см. 4.3), т.к. это сериализованный Shadow DOM;

* для каждой ноды:

  * raw, lead\_ws, trail\_ws, core (см. 5.5),

  * part\_id,

  * путь/идентификатор узла в парсере для последующего Apply.

**В LLM отправляем только core**, предварительно обработав Token Protector (если включён).

### **5.4 Атрибуты (если**

### **–translate-attrs=on**

### **)**

Переводим:

* title,

* aria-label,

* placeholder,

* alt (по правилам ниже).

#### **5.4.1 Правила для**

#### **alt**

–translate-alt=auto:

* переводить только если:

  * alt не пустой,

  * длина ≤ 180 символов,

  * alt не выглядит как техническое описание/параметры/путь/URL.

### **5.5 Нормализация и пробелы**

Для каждого text node:

* raw — исходная строка,

* lead\_ws — ведущие пробельные символы,

* trail\_ws — хвостовые пробельные символы,

* core — строка без lead/trail.

Переводим только core. При применении собираем обратно: lead\_ws \+ translated\_core \+ trail\_ws.

---

## **6\. Перевод через LLM (Translate)**

### **6.1 Используемый API**

OpenAI **Responses API**.

Дефолтный запрос:

* model \= gpt-5.1,

* reasoning \= { “effort”: “medium” } (если –reasoning-effort \!= none),

* max\_output\_tokens \= 8192,

* text.format \= { type: “json\_schema”, strict: true, schema: … } (Structured Outputs).

### **6.2 Формат запроса (block‑mode)**

В input передаём JSON со списком блоков:

{

“task”: “translate\_blocks”,

“target\_language”: “ru”,

“rules”: {

“keep\_placeholders”: true,

“no\_html”: true,

“allow\_empty\_parts”: true

},

“blocks”: \[

{

“block\_id”: “b\_000123”,

“context”: “I built a tool using python.”,

“parts”: \[

{“id”: “t\_000001”, “text”: “I built a”},

{“id”: “t\_000002”, “text”: “tool”},

{“id”: “t\_000003”, “text”: “using”},

{“id”: “t\_000004”, “text”: “python”}

\]

}

\],

“glossary”: {

“OpenAI”: “OpenAI”,

“Codex”: “Codex”

}

}

**Требование:** parts\[\].id уникальны в пределах одного запроса.

Если –allow-empty-parts=off: задавать rules.allow\_empty\_parts=false и требовать непустой перевод для каждого непустого входного part.

#### **6.2.1 Формат для атрибутов**

{

“task”: “translate\_items”,

“target\_language”: “ru”,

“items”: \[

{“id”: “a\_000101”, “text”: “Search”, “hint”: “attr:placeholder”},

{“id”: “a\_000102”, “text”: “Copy link”, “hint”: “attr:aria-label”}

\],

“glossary”: {

“OpenAI”: “OpenAI”

}

}

### **6.3 JSON Schema ответа (единая для blocks/items)**

text.format:

* type: “json\_schema”,

* strict: true,

* name: “web2ru\_translations”.

Схема:

{

“type”: “object”,

“additionalProperties”: false,

“properties”: {

“translations”: {

“type”: “array”,

“items”: {

“type”: “object”,

“additionalProperties”: false,

“properties”: {

“id”: { “type”: “string” },

“text”: { “type”: “string” }

},

“required”: \[“id”, “text”\]

}

}

},

“required”: \[“translations”\]

}

### **6.4 Инструкции (prompt)**

Инструкции MUST фиксировать:

* перевод на русский,

* **не добавлять HTML/Markdown**,

* **не менять состав/порядок id**: для каждого входного id вернуть ровно одну строку text; нельзя добавлять новые id, удалять id или менять их порядок,

* если rules.allow\_empty\_parts=true (–allow-empty-parts=on): допускается оставлять отдельные parts пустыми и **распределять перевод между соседними parts**, чтобы при склейке частей по порядку получался естественный русский (это важно для инлайн‑разметки //),

* если rules.allow\_empty\_parts=false (–allow-empty-parts=off): каждый part с непустым входом должен иметь непустой перевод,

* не выдумывать новые сущности,

* **не изменять плейсхолдеры Token Protector** (см. 6.5),

* не переводить кодоподобные токены (CLI‑флаги, пути, идентификаторы) — даже если они просочились в текст,

* учитывать context блока и давать части так, чтобы конкатенация читалась естественно.

### **6.5 Token Protector (обязателен в MVP)**

#### **6.5.1 Зачем**

Технические страницы содержат множество “инвариантов”, которые LLM склонна:

* переводить (ломая смысл),

* “улучшать” (ломая идентификаторы/URL),

* форматировать (ломая команды/параметры).

Token Protector делает инварианты **непереводимыми** технически, а не “на честном слове промпта”.

#### **6.5.2 Что защищаем (MVP)**

Защищаем заменой на плейсхолдеры:

* URL: https?://…, www….,

* email,

* UUID,

* хеши/sha/commit,

* пути файлов (/usr/bin, ./path),

* CLI‑флаги (–flag, \-x),

* inline code вида ... (если встретилось как текст, но не внутри ),

* версии/semver,

* идентификаторы, похожие на snake\_case/camelCase (best effort).

#### **6.5.3 Формат плейсхолдера**

Например:

WEB2RU\_TP\_000123

#### **6.5.4 Правила строгого режима**

Если –token-protect-strict=on:

* любое изменение плейсхолдера (символ/порядок/кол-во) считается ошибкой батча.

#### **6.5.5 Валидация сохранности**

После ответа LLM:

* проверить, что все плейсхолдеры присутствуют 1:1 и не изменены.

---

### **6.6 Батчинг**

Формируем батчи по:

* –batch-chars (сумма len(part.text) в батче),

* –max-items-per-batch (кол-во parts).

### **6.7 Retry, auto-split и fallback (обязательное поведение)**

Батч считается неуспешным, если:

* статус incomplete / есть incomplete\_details,

* JSON не парсится/не соответствует схеме,

* отсутствуют переводы для части id (id пропал или продублирован),

* нарушена сохранность плейсхолдеров Token Protector,

* в text появляется HTML/Markdown (нарушение rules.no\_html),

* аномалии по empty parts:

  * если –allow-empty-parts=off: **любой** part с непустым входным core получил пустой text,

  * если –allow-empty-parts=on: пустые parts допустимы, но аномалией считать:

    * блок, у которого хотя бы один входной part был непустым, а после перевода **все** parts блока пустые,

    * (эвристика) доля пустых translated parts среди непустых входных parts по блоку \> 80% при длине блока ≥ 80 символов (похоже на “потерю текста”).

Поведение:

1. retry до max-retries;

2. если снова неуспешно — **разделить батч пополам** и повторить рекурсивно (минимум: 1 блок или 1 part);

3. если конкретный блок/part всё равно не удаётся стабильно перевести:

   * пометить как fallback=textnode (если исходно был block),

   * перевести по одиночке translate\_items (без требования “конкатенации”),

   * если и это не удалось — оставить оригинал и залогировать причину.

Все фейлы фиксируются в report.json.

### **6.8 Кеш переводов**

SQLite‑кеш хранит:

* ключ: sha256(model | reasoning\_effort | prompt\_version | glossary\_version | translation\_unit | token\_protector\_version | payload\_hash)

* значение: translations\_by\_id, created\_at, status, usage\_tokens (если доступно).

---

## **7\. Ассеты: сбор, scan, кеширование, переписывание (HTML \+ CSS)**

### **7.1 Что считаем ассетом (MVP)**

* CSS (link rel=stylesheet),

* JS (script src) — сохраняем, но затем нейтрализуем в freeze-js=on,

* изображения (img/src/srcset, picture/source),

* шрифты (woff/woff2/ttf/otf),

* прочие медиа (video/audio/poster) — best effort.

### **7.2 Network capture (online‑фаза)**

Во время Playwright‑сессии:

* перехватывать ответы,

* сохранять по URL в AssetCache:

  * raw bytes,

  * content-type,

  * final URL,

  * размер,

  * sha256.

Ограничения:

* игнорировать data: и blob: URL,

* игнорировать ответы \> –max-asset-mb.

### **7.3 Reference scan (offline‑фаза,**

### **–asset-scan=on**

### **)**

Задача: найти ссылки на ресурсы, которые могли не попасть в network capture (не видны без скролла/hover/разных media queries).

Сканировать:

* DOM‑обход MUST включать содержимое template\[shadowrootmode\] (см. 4.3), иначе ассеты shadow‑контента останутся внешними.

* HTML‑атрибуты: src, href, srcset, poster, data, content (для некоторых meta), xlink:href (best effort).

* Inline style атрибуты: style=”…url(…)”.

\<style\> блоки: url(...), @import.

* 

* Все сохранённые CSS: url(…), @import.

Нормализация:

* разрешать относительные URL относительно:

  * final\_url для HTML,

  * URL конкретного CSS (для url() внутри CSS),

* сохранять query‑строки, игнорировать \#fragment.

Результат scan: список needed\_urls.

### **7.4 Доскачивание недостающих (**

### **–fetch-missing-assets=on**

### **)**

Для каждого URL из needed\_urls, если его нет в AssetCache:

* выполнить best‑effort HTTP GET (через httpx):

  * выставить User-Agent как у Playwright,

  * Referer: final\_url,

  * применить те же ограничения по content-type и размеру.

* при успехе сохранить в AssetCache,

* при неудаче — записать в report.json как missing\_asset (без падения всего процесса).

### **7.5 Путь ассета в output**

Схема:

assets//\_\_.

**Критическое правило:** ссылки в HTML/CSS должны быть **строго относительными**:

* ✅ ./assets/example.com/styles\_\_a1b2c3d4.css

* ❌ /assets/styles.css

### **7.6 Переписывание URL в HTML (offline‑фаза)**

Переписывание MUST обходить весь DOM, включая содержимое template\[shadowrootmode\] (см. 4.3).

Переписывать:

* img\[src\], img\[srcset\]

* source\[src\], source\[srcset\]

* link\[href\] для rel=stylesheet и (опционально) preload/icon если они реально нужны для отображения

* video\[src\], video\[poster\], audio\[src\]

* object\[data\], embed\[src\]

* inline styles: style=”…url(…)” (best effort)

\<style\> содержимое (если не вынесено в отдельный CSS) — best effort

Не переписывать в MVP:

* a\[href\] (внутренние ссылки — Phase 2),

* script\[src\] (см. 8).

### **7.7 Переписывание URL в CSS**

В каждом CSS:

* переписать url(…) на локальный путь,

* переписать @import на локальный путь.

Относительные пути считать относительно URL исходного CSS.

### **7.8 SRI / integrity (обязательное правило)**

Если переписываем link/script, то:

* удалить integrity,

* удалить crossorigin (best effort),

* увеличить integrity\_stripped\_count в report.json.

---

## **8\. Freeze JS и санитизация сохранённого HTML**

### **8.1 Зачем это нужно**

Чтобы офлайн‑страница:

* не выполняла JS,

* не делала внешних сетевых запросов,

* не “переезжала” на оригинальный сайт.

### **8.2 Поведение**

### **freeze-js=on**

### **(MVP)**

В сохранённом HTML выполнить (DOM‑обход MUST включать содержимое template\[shadowrootmode\], см. 4.3):

1. **Нейтрализовать исполняемые** 

\<script src\>:

\* удалить src,

\* перенести значение в data-web2ru-src,

\* поставить type="application/x-web2ru-disabled".

* 

  * inline :

    * заменить содержимое на пустую строку,

    * опционально сохранить data-web2ru-inline-sha256.

2. **Удалить inline‑обработчики событий**

   * удалить любые атрибуты, начинающиеся на on\* (onclick, onload, …).

3. **Нейтрализовать JS‑URL**

   * href=“javascript:…” → href=”\#”, исходное в data-web2ru-href.

4. **Нейтрализовать опасные meta**

   * удалить/нейтрализовать:

     * \<meta http-equiv=“refresh” …\> (может увести в сеть),

     * \<meta http-equiv=“Content-Security-Policy” …\> (может ломать локальные ресурсы).

5. **Resource hints**

   * удалить link\[rel=preconnect\], link\[rel=dns-prefetch\], link\[rel=prefetch\], link\[rel=prerender\]

   * preload оставлять только если после переписывания он указывает на локальный ассет; иначе удалить.

6. 

   * если присутствует — по умолчанию удалить.

   * альтернативно (для отладки) можно переписать на ./.

7. **Iframe**

   * если –block-iframe=on (или auto при freeze-js=on):

     * iframe\[src\] заменить на about:blank,

     * исходный src сохранить в data-web2ru-src,

     * если есть srcdoc — очистить, исходное сохранить в data-web2ru-srcdoc (best effort).

8. **Lazy‑img fix (best effort)**

   * если img\[src\] пуст/плейсхолдер, а есть data-src/data-lazy-src → перенести в src,

   * аналогично для srcset: data-srcset → srcset,

   * для source внутри picture аналогично.

**Исключения (можно оставлять):**

\<script type="application/ld+json"\>,

* 

\<script type="application/json" ...\> (например \_\_NEXT\_DATA\_\_), при условии что они не исполняются.

### **8.3**

### **freeze-js=off**

* Не трогаем , не трогаем обработчики.

* Валидатор внешней сети всё равно может падать (см. 8.4).

### **8.4 Базовая защита от “утечки сети” (валидатор результата)**

Автотест (см. 10.2):

* поднять output через –serve,

* открыть страницу в Playwright,

* заблокировать все запросы на внешние домены (кроме localhost),

* ожидать 0 внешних запросов.

### **8.5**

### **и**

### **drop-noscript**

drop-noscript=auto:

* если freeze-js=on: удалять , но предварительно:

  * если внутри  есть img/link (частый lazy‑fallback) — попытаться перенести в DOM (best effort),

  * иначе удалить.

---

## **9\. Формат вывода**

### **9.1 Структура папки снапшота (single page)**

output//

* index.html

* assets/…

* report.json

### **9.2 slug**

По умолчанию:

* host \+ path, нормализованные,

* ограничение длины,

* если конфликт — добавлять hash.

### **9.3 report.json**

report.json должен включать как минимум:

* source\_url, final\_url, timestamp,

* параметры запуска (без секретов),

* статистику:

  * blocks\_total, parts\_total, attrs\_total,

  * translated\_parts, fallback\_parts, skipped\_parts,

  * token\_protected\_count,

  * empty\_parts\_total, empty\_parts\_ratio (если –allow-empty-parts=on),

* LLM:

  * модель, reasoning\_effort, кол-во запросов, retries, auto-split depth, кеш-hit rate,

* Shadow DOM:

  * enabled, open\_roots\_found, templates\_inserted, adopted\_stylesheets\_extracted, errors\_count,

* ассеты:

  * сколько поймано в capture,

  * сколько найдено scan,

  * сколько доскачано,

  * список missing\_assets (URL \+ причина),

* санитизация:

  * scripts\_disabled\_count,

  * integrity\_stripped\_count,

  * iframes\_blocked\_count,

  * csp\_meta\_removed\_count,

  * resource\_hints\_removed\_count,

* валидация:

  * external\_requests\_detected (если был прогон),

* ошибки/предупреждения по блокам (id \+ причина).

---

## **10\. Тестирование и регресс**

### **10.1 Контрольные URL (регресс‑набор)**

* https://openai.com/index/harness-engineering/

* https://simonwillison.net/

* https://edisonscientific.gitbook.io/edison-cookbook/paperqa

* https://matt.might.net/articles/peer-fortress/

* https://minimaxir.com/2025/11/nano-banana-prompts/

### **10.2 Проверки (автоматизируемые)**

* Команда для каждого URL:

  * генерирует output,

  * поднимает –serve,

  * открывает страницу в Playwright и блокирует внешнюю сеть:

    * **ожидаем 0 внешних запросов**,

  * делает скриншот (best effort),

  * проверяет, что:

    * index.html существует,

    * есть CSS и хотя бы часть картинок/шрифтов (не ноль),

    * report.json без критических ошибок,

    * при freeze-js=on нет активных .

    * если report.shadow\_dom.open\_roots\_found \> 0: templates\_inserted \> 0 и в index.html присутствует shadowrootmode (best effort).

### **10.3 Проверки (ручные, разово для релиза)**

* Визуально:

  * нет “белого экрана”,

  * нет “Enable JavaScript” оверлеев,

  * навигация по странице/скролл работает,

  * изображения и шрифты подгружаются локально.

---

## **11\. Известные ограничения (честно)**

* Авторизованные сайты / paywall / контент за логином — не поддерживаем в MVP.

* Сложные интерактивные SPA офлайн в интерактивном виде — не цель MVP.

* Shadow DOM: материализуем только **open** shadow roots; closed shadow roots недоступны. adoptedStyleSheets сериализуются best effort. Просмотр офлайна с Declarative Shadow DOM ориентирован на современный Chromium.

* Видео/встроенные плееры/iframe‑контент — best effort; по умолчанию iframe блокируется при freeze-js=on.

* 100% полное сохранение всех ресурсов во всех случаях не гарантируется (есть CDN‑ограничения/антибот/тайминг).

---

## **12\. План поставки (рекомендуемый)**

**Milestone 1 (MVP):**

* two‑stage пайплайн,

* shadow-dom materialization (template\[shadowrootmode\], best effort),

* Extract block‑mode \+ Token Protector,

* Translate Structured Outputs \+ retry/auto-split \+ fallback,

* ассеты: capture \+ rewrite \+ CSS rewrite \+ relative paths,

* reference scan \+ fetch missing (best effort),

* freeze-js hardening (CSP/base/iframes/resource hints/meta refresh),

* отчёт \+ регресс‑скрипт.

**Milestone 2:**

* улучшение scope/exclude эвристик \+ минимальный GitBook‑адаптер.

**Milestone 3:**

* crawl‑режим для документации (GitBook) с переписыванием внутренних ссылок.

