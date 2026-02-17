# Web2RU Translation Quality and Context Cohesion Upgrade

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan complies with `/AGENTS.md` and `/PLANS.md`.

## Purpose / Big Picture

Improve translation quality from "segment-correct but stylistically fragmented" to "article-level coherent Russian prose" while preserving all Web2RU non-negotiables:
- DOM integrity,
- offline purity,
- structured output safety,
- Token Protector invariants.

User-visible result:
- fewer broken endings/cases across neighboring sentences,
- more stable terminology across one page,
- better readability for long technical articles with mixed prose and code examples.

## Scope

In scope:
- extraction and translation payload changes that provide local context (`prev/current/next`) for each translatable item;
- batching strategy improvements to keep neighboring content together;
- document-level terminology pass (lightweight glossary bootstrap);
- optional second pass for style harmonization on translated prose only;
- quality metrics and regression tests for coherence/terminology;
- `report.json` extension for translation quality diagnostics.

Out of scope:
- crawl mode / multi-page global memory;
- changing freeze-js behavior;
- changing output folder layout;
- rewriting code tokens inside code blocks (only comment text may be translated as already implemented).

## Safety & Guardrails

- Live network is needed only for final authorized validation on control URLs. Unit/integration tests remain fixture-based and network-free.
- HUMAN APPROVAL REQUIRED before changing translation schema, translation system prompt rules, Token Protector behavior, or CLI defaults.
- HUMAN APPROVAL REQUIRED before adding/upgrading production dependencies.
- HUMAN APPROVAL REQUIRED before any new live regression run against external websites.
- Data handling: page content can include sensitive text. Do not log full source content or secrets.
- Offline purity is preserved because this plan changes translation quality logic only; assets/freeze/network blocking remain unchanged and must be re-validated.

## Progress

- [x] (2026-02-17 10:05Z) Create `docs/execplans/translation_quality_execplan.md` with milestones, risks, and acceptance criteria.
- [ ] Establish baseline quality metrics on control pages and save baseline artifacts.
- [x] (2026-02-17 10:11Z) Implement context-aware payload contract for translation items without breaking id coverage/order guarantees.
- [x] (2026-02-17 10:11Z) Implement section-preserving sequential batching with configurable context window.
- [x] (2026-02-17 10:11Z) Implement document-level terminology bootstrap pass and glossary injection into main pass.
- [ ] Implement optional prose harmonization second pass (guarded by config flag).
- [x] (2026-02-17 10:11Z) Extend validator/report with quality diagnostics and failure reasons.
- [x] (2026-02-17 10:11Z) Add/extend unit and integration tests for new quality path.
- [x] (2026-02-17 10:11Z) Run quality gates (`ruff`, `mypy`, `pytest`) in local `venv`.
- [x] (2026-02-17 10:43Z) Add XML-safety sanitization for translated text/attrs (`\\x00` and invalid control chars) after live-run crash on `simonwillison.net`; add unit coverage.
- [x] (2026-02-17 10:43Z) Run authorized live validation on all 5 control URLs and capture fresh artifacts.
- [x] (2026-02-17 12:31Z) Implement P1 speed optimizations:
  - less aggressive section-boundary splitting in translation batching,
  - selective neighbor-context injection only for short/fragmented text,
  - concurrent `fetch_missing_assets` with shared client reuse.
- [x] (2026-02-17 12:31Z) Run before/after runtime benchmark on all 5 control URLs with identical CLI profile (`reasoning-effort=none`, `max-retries=3`).

## Surprises & Discoveries

- Current payload sends isolated items (`id`, `text`, `hint`) without neighboring context, which likely causes case/agreement drift between adjacent fragments.
  Evidence: `src/web2ru/translate/translator.py` payload creation currently includes only the item text and hint.
- Current batching is purely size-based; nearby sections can be split apart when limits are hit.
  Evidence: `src/web2ru/translate/batcher.py` uses only `max_chars` and `max_items`.
- Existing strict validation and placeholder controls are strong and should be reused rather than relaxed.
  Evidence: `src/web2ru/translate/validate.py` and `src/web2ru/translate/token_protector.py`.
- The current ruff setup in this environment does not support markdown formatting without preview mode, so only code formatting should be included in default quality commands.
  Evidence: `ruff format docs/execplans/translation_quality_execplan.md` returns "Markdown formatting is experimental".
- Live run on `simonwillison.net` crashed during apply because translated text occasionally contained XML-invalid control bytes (e.g., `\\x00`), which `lxml` rejects.
  Evidence: `ValueError: All strings must be XML compatible` in offline apply stage; fixed by sanitizing translated text/attrs before setting node content.
- Wall-clock before/after comparisons can be heavily skewed by translation-cache state.
  Evidence: baseline run had high cache-hit ratios on several pages (`cache_hits` ~= `batches_total`), while post-change run used cold keys after batching/context changes and therefore made many live LLM calls.

## Decision Log

- Decision: Improve quality in phased steps behind explicit config toggles first, then promote to defaults only after control-page validation.
  Rationale: minimize regression risk for existing stable snapshots.
  Date/Author: 2026-02-17 / Codex.

- Decision: Preserve structured output shape (`translations: [{id, text}]`) for compatibility with current validator/apply flow.
  Rationale: avoid broad refactor and keep strict id/order guarantees.
  Date/Author: 2026-02-17 / Codex.

- Decision: Keep DOM/apply/asset/freeze logic unchanged for this plan, except diagnostics in `report.json`.
  Rationale: isolate quality work to extraction/translation components.
  Date/Author: 2026-02-17 / Codex.

- Decision: keep structured response schema unchanged and pass context as additional input fields (`context_prev`, `context_next`, `section_hint`) while still returning only `{id, text}`.
  Rationale: quality gains without touching apply/validation contracts.
  Date/Author: 2026-02-17 / Codex.

- Decision: sanitize translated strings at apply-time for XML compatibility before writing to DOM/attributes.
  Rationale: prevents runtime crashes from rare control characters produced by model output while preserving pipeline invariants.
  Date/Author: 2026-02-17 / Codex.

- Decision: keep context-quality improvements but reduce context payload size via heuristics and reduce batch fragmentation by section.
  Rationale: target lower LLM request count and lower payload overhead while keeping cohesion gains.
  Date/Author: 2026-02-17 / Codex.

## Outcomes & Retrospective

Target outcome:
- translation reads as coherent article-level Russian prose on control pages,
- no regression in offline purity and safety invariants,
- measurable quality gain versus baseline.

Current status:
- context-aware translation payload, section-aware batching, glossary bootstrap, quality stats, and tests are implemented.
- live validation completed on all control URLs with fresh output artifacts.
- P1 speed optimization code implemented and benchmarked; uncached-request counts reduced on large control pages.
- remaining work: isolate and report cache-normalized speed benchmark, baseline-vs-new qualitative scoring package, and optional harmonization second pass.

Retrospective (fill after delivery):
- what improved most (cohesion vs terminology vs style),
- what remained weak and why,
- what to carry into Phase 2.

## Context and Orientation

Primary files expected for this change:
- `src/web2ru/extract/block_extractor.py` (ordering/section context metadata if needed),
- `src/web2ru/translate/batcher.py` (sequential/section-aware batching),
- `src/web2ru/translate/translator.py` (payload composition, multi-pass orchestration, caching keys),
- `src/web2ru/translate/client_openai.py` (system prompt/payload contract adjustments),
- `src/web2ru/translate/validate.py` (guardrails for new context flow),
- `src/web2ru/config.py` and `src/web2ru/cli.py` (new optional knobs if approved),
- `src/web2ru/report/builder.py` and `src/web2ru/pipeline/offline_process.py` (quality stats in `report.json`),
- `tests/unit/*` and `tests/integration/*` (regression coverage).

Spec requirements relied on:
- `docs/TECHNICAL_SPEC_WEB2RU.md`: DOM must not be restructured, offline output must avoid external requests in default mode, translation must preserve technical/code tokens and placeholders.

## Invariants & Acceptance Criteria

Non-negotiable invariants (must stay green):
1. DOM integrity unchanged except allowed text/attribute updates.
2. Placeholder integrity unchanged (`WEB2RU_TP_*` round-trip).
3. Structured output strictness unchanged (schema-valid JSON, exact id coverage, stable order).
4. Offline purity in default mode remains `0 external requests`.
5. Security posture unchanged (no weakening of freeze/network protections).

Quality acceptance criteria (new):
1. Human review score improves on all 5 control URLs with a fixed rubric (cohesion, fluency, terminology), target average >= 4.2/5.
2. Terminology consistency improves: repeated key terms keep one canonical Russian rendering within a document (target >= 90% consistency for top repeated terms).
3. Context breaks (wrong agreement/endings caused by local isolation) reduced by at least 50% vs baseline sample.
4. No significant rise in fallback behavior (`fallback_parts` increase <= 5% relative).

## Plan of Work

Milestone 1: Baseline and observability
- Add quality diagnostics collector and baseline script for control URLs.
- Capture current outputs and annotate known bad fragments.
- Extend `report.json` with optional `quality` section (readability/consistency counters).

Milestone 2: Context-aware payload
- Keep primary `id -> text` translation contract, but include neighbor context in each item payload:
  - `context_prev`, `context_next`, `section_hint`.
- Update system/user instruction so the model translates only `text`, using context only as guidance.
- Preserve strict id-order validation logic.

Milestone 3: Sequential section-aware batching
- Batch in document order, preferring contiguous items from the same section/block.
- Respect existing hard limits (`max_items_per_batch`, `batch_chars`).
- Add bounded context window so each item carries nearby context even if batched separately.

Milestone 4: Document terminology bootstrap
- First lightweight pass extracts frequent technical terms and candidate Russian forms.
- Feed stable glossary into main translation pass.
- Record glossary version/hash in cache key to avoid stale mixed behavior.

Milestone 5: Optional harmonization second pass
- Run only on prose parts after first pass.
- Goal: smooth style and agreement across neighboring translated segments.
- Keep strict constraints: no HTML/Markdown injection, placeholder integrity unchanged.
- Guard with config flag (default off until validated).

Milestone 6: Validation and rollout
- Add fixture tests for context mapping and quality regressions.
- Run full quality gates.
- Run authorized live control-page validation and compare against baseline.
- If targets met, propose enabling selected quality features by default.

## Concrete Steps

Working directory:
- `cd /Users/sergejavdejcik/Library/Mobile Documents/com~apple~CloudDocs/2026_1_air/web2RU`

Implementation sequence:
1. Add baseline quality diagnostics and tests.
2. Add context fields to translation payload and update prompts.
3. Update batcher for contiguous section-aware grouping.
4. Add glossary bootstrap pass and cache key versioning.
5. Add optional harmonization pass.
6. Extend `report.json` quality section.
7. Validate and compare baseline/new outputs on control URLs.

Validation commands:
- `ruff format .`
- `ruff check .`
- `mypy src`
- `pytest -q`

Live validation commands (HUMAN APPROVAL REQUIRED before running):
- `web2ru 'https://openai.com/index/harness-engineering/' --headful --freeze-js on --asset-scan on --fetch-missing-assets on`
- `web2ru 'https://simonwillison.net/' --headful --freeze-js on --asset-scan on --fetch-missing-assets on`
- `web2ru 'https://edisonscientific.gitbook.io/edison-cookbook/paperqa' --headful --freeze-js on --asset-scan on --fetch-missing-assets on`
- `web2ru 'https://matt.might.net/articles/peer-fortress/' --headful --freeze-js on --asset-scan on --fetch-missing-assets on`
- `web2ru 'https://minimaxir.com/2025/11/nano-banana-prompts/' --headful --freeze-js on --asset-scan on --fetch-missing-assets on`

## Validation & Acceptance

Checklist:
- [ ] Unit tests prove context window mapping and stable id ordering.
- [ ] Unit tests prove placeholder round-trip unchanged with new context payload.
- [ ] Integration tests prove no DOM-structure changes.
- [ ] Integration/offline checks prove `0 external requests` in default mode.
- [ ] Baseline vs new comparison artifacts generated for all control URLs.
- [ ] Human rubric scores meet acceptance thresholds.
- [ ] `report.json` contains new quality diagnostics without breaking existing keys.

## Idempotence and Recovery

- All translation requests remain cacheable; cache keys include model, prompt version, glossary version, and payload hash.
- If context/harmonization fails validation, pipeline falls back to first-pass translation or original text per existing fallback rules, with explicit `report.json` errors.
- Quality features are toggleable; disable with config flags to return to current stable behavior.
- Keep baseline artifacts so rollback quality comparison is always possible.

## Artifacts and Notes

Expected artifacts:
- baseline and post-change outputs under `output/<slug>/`,
- `report.json` with `quality` diagnostics,
- test evidence in `tests/unit` and `tests/integration`,
- summary comparison note in `docs/` (to be added during implementation).

Recommended comparison notes per control URL:
- examples of pre/post fragments with improved agreement,
- terminology consistency examples,
- any residual issues and whether they are model/prompt/extraction related.

## Interfaces and Dependencies

Current dependencies are sufficient for the first iteration.

If later adding new NLP tooling for scoring or terminology extraction:
- mark as HUMAN APPROVAL REQUIRED,
- justify why existing stack cannot provide the needed signal.

Key interfaces to preserve:
- `TranslationItem` core semantics (`id`, translated `text` result),
- strict `translations` JSON schema contract,
- `apply_blocks` and `apply_attributes` behavior,
- report compatibility for existing consumers.
