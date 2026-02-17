# Web2RU MVP Implementation (Single Page Offline RU Snapshot)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan complies with `/AGENTS.md` and `/PLANS.md`.

## Purpose / Big Picture

Deliver a working `web2ru` CLI that takes one URL and produces a local folder with:
- translated `index.html` (EN -> RU),
- fully rewritten local assets,
- hardened offline behavior (`freeze-js=on` by default),
- `report.json` with pipeline diagnostics.

User-visible success: a generated snapshot opens locally and performs `0 external requests` in default mode.

## Scope

In scope (MVP):
- full two-phase pipeline (online render + offline processing),
- block-mode extract/apply, Token Protector, Structured Outputs translation,
- capture + scan + fetch-missing + HTML/CSS asset rewriting,
- freeze-js sanitization and offline validator,
- deterministic unit/integration tests on fixtures.

Out of scope (for this plan):
- crawl mode and internal-link localization (Phase 2),
- authenticated/paywalled content support,
- guaranteed preservation of dynamic SPA interactivity offline.

## Safety & Guardrails

- Live network is required only for online render and optional fetch-missing. Fixture tests must remain network-free.
- HUMAN APPROVAL REQUIRED: adding/upgrading production dependencies.
- HUMAN APPROVAL REQUIRED: changing CLI defaults, translation schema/prompt contracts, Token Protector logic, freeze-js policy.
- HUMAN APPROVAL REQUIRED: running live regression on external URLs.
- Data handling: page content and translated text may include sensitive user data; never log secrets; never expose `OPENAI_API_KEY`.
- Offline purity policy: when assets are missing, do not keep external URLs; keep links local and report misses in `report.json`.

## Progress

- [x] (2026-02-17 10:43Z) Extend extraction/apply pipeline for in-article `pre/code` blocks:
  - prose-like `pre/code` content (e.g., markdown snippets) is now translated as normal text;
  - code-like `pre/code` content is translated comment-only via offset-based replacement, preserving executable code tokens and structure.
- [x] (2026-02-17 10:43Z) Relax markdown heading/fence validation to block only injected markup not present in source text, so legitimate markdown snippets can pass strict response validation.
- [x] (2026-02-17 10:44Z) Add regression tests:
  - `tests/unit/test_extract_blocks.py` (markdown `pre`, `data-language=md`, comment-only code extraction),
  - `tests/unit/test_apply_blocks.py` (offset-based in-place comment replacement),
  - `tests/unit/test_translate_validate.py` (allow heading when source contains it, reject injected heading otherwise).
- [x] (2026-02-17 10:45Z) Validate live on target page:
  - `output/developers.openai.com-cookbook-articles-codex_exec_plans-507523ef-2/report.json`,
  - problematic snippet now translated: “При разработке сложных функциональностей ... от этапа проектирования до этапа реализации.”
- [x] (2026-02-17 09:55Z) Investigate OpenAI control-page regression reported by user: mixed EN/RU output and missing images on offline snapshot.
- [x] (2026-02-17 09:57Z) Implement Token Protector hotfix in code (`src/web2ru/translate/token_protector.py`): remove global case-insensitive matching and bump `TOKEN_PROTECTOR_VERSION` to `1.1` to avoid stale cache reuse.
- [x] (2026-02-17 09:58Z) Add regression coverage in `tests/unit/test_token_protector.py` for plain prose (must not be protected) and technical-token protection (must still round-trip).
- [x] (2026-02-17 10:00Z) Validate with quality gates (`ruff`, `mypy`, `pytest`) and live OpenAI rerun after fix:
  - `output/openai.com-index-harness-engineering-293d0f96-6/report.json`
  - `translated_parts=170`, `errors=[]`, `missing_img_total=0`, `offline_ok_default_mode=true`.
- [x] (2026-02-16 22:23Z) Confirm canonical spec path and remove duplicate root `TECHNICAL_SPEC_WEB2RU.md`.
- [x] (2026-02-16 22:23Z) Prepare MVP ExecPlan document and commit implementation sequence.
- [x] (2026-02-16 23:50Z) Bootstrap Python package skeleton, `pyproject.toml`, and baseline CLI wiring.
- [x] (2026-02-16 23:50Z) Implement Online phase (`Playwright`, capture, readiness, shadow DOM materialization).
- [x] (2026-02-16 23:50Z) Implement Offline phase core (`parse`, `extract`, `translate`, `apply`, `rewrite`, `freeze`, `report`).
- [x] (2026-02-16 23:50Z) Add deterministic unit + integration + e2e fixtures and pass quality gates (`ruff`, `mypy`, `pytest`).
- [x] (2026-02-17 00:05Z) Run authorized live smoke on control URLs (partial): OpenAI page, Simon Willison page, GitBook page, plus offline validation (`0 external requests`) for generated snapshots.
- [x] (2026-02-17 07:15Z) Complete live translation pass for remaining large control URLs (`edison`, `minimaxir`) with LLM-enabled reports:
  - `output/edisonscientific.gitbook.io-edison-cookbook-paperqa-a8cf5938-7/report.json` (`translated_parts=673`, `llm.requests=20`)
  - `output/minimaxir.com-2025-11-nano-banana-prompts-91e2b9de-4/report.json` (`translated_parts=245`, `llm.requests=15`)

## Surprises & Discoveries

- Shiki-highlighted markdown blocks on `developers.openai.com` use `data-language="md"` plus nested span tokens, so language detection cannot rely only on `language-*` CSS classes.
- A strict “reject any markdown heading” validator blocked legitimate translations for markdown snippets that intentionally start with `#`; validation must distinguish injected markup from source-preserved markup.
- Token Protector over-protected normal English prose because `_PROTECT_RE` used `re.IGNORECASE`, which made the camelCase branch match ordinary lowercase words; this produced large placeholder sets and mixed EN/RU output after restore.
- OpenAI control-page image breakage in the reported run was amplified by `--fetch-missing-assets off`; with asset fetching enabled, page images were restored locally.
- The repo currently contains architecture/spec/testing docs but no `src/` implementation yet, so MVP work starts from project scaffold.
- The technical spec had markdown-rendered tag loss in several sections (`<script>`, `<noscript>`, `<base>`, inline tags); those sections were restored with backticks to prevent re-loss.
- Local runtime in this workspace is Python `3.10.10`; project metadata was adjusted to `requires-python>=3.10` to keep local reproducible setup and quality gates green.
- Some control URLs return anti-bot/interstitial HTML (e.g., OpenAI “Just a moment”), which yields valid snapshots but with little/no translatable content.
- Live translation runs on larger pages can be slow; OpenAI client timeout was explicitly set to reduce indefinite waiting.

## Decision Log

- Decision: treat `pre/code` blocks with markdown/text language hints as prose and translate fully; treat code-language blocks as comment-only translation with positional text replacement.
  Rationale: satisfies user requirement to translate narrative blocks inside articles while preserving executable code.
  Date/Author: 2026-02-17 / user-requested, Codex implemented.

- Decision: markdown heading/fence checks are now source-aware (reject only when markup appears in translation but not in source).
  Rationale: preserves LLM safety guardrails while allowing valid markdown snippet translation.
  Date/Author: 2026-02-17 / Codex.

- Decision: remove global case-insensitive regex matching in Token Protector and explicitly keep uppercase hex support in the hash pattern.
  Rationale: preserves protection for technical tokens while preventing accidental masking of natural-language words.
  Date/Author: 2026-02-17 / user-approved, Codex implemented.

- Decision: bump `TOKEN_PROTECTOR_VERSION` from `1.0` to `1.1`.
  Rationale: force fresh translation-cache keys after placeholder behavior change and prevent stale mixed-language cache hits.
  Date/Author: 2026-02-17 / Codex.

- Decision: Keep `docs/TECHNICAL_SPEC_WEB2RU.md` as canonical source of truth and remove root duplicate.
  Rationale: single authoritative spec avoids drift and ambiguity.
  Date/Author: 2026-02-16 / user + Codex.

- Decision: MVP HTML parser is `lxml.html`; MVP CSS parser is `tinycss2`.
  Rationale: stable traversal/serialization and safe token-level CSS URL rewriting.
  Date/Author: 2026-02-16 / user.

- Decision: Offline purity is higher priority than visual parity when assets are missing.
  Rationale: project non-negotiable is `0 external requests` in default mode.
  Date/Author: 2026-02-16 / user.

- Decision: `freeze-js=off` is treated as unsafe debug mode.
  Rationale: external-request validator may fail and must be reported explicitly.
  Date/Author: 2026-02-16 / user.

## Outcomes & Retrospective

Current outcome:
- baseline MVP implementation delivered in repo (`src/web2ru/*`) with two-phase pipeline and typed module boundaries.
- quality gates now pass in local environment: `ruff check .`, `mypy src`, `pytest -q`.
- control-url smoke runs are partially complete; extractor and asset scan heuristics were adjusted based on live findings.
- live translation artifacts were finalized for the remaining large control URLs (`edison`, `minimaxir`) and quality gates are still green.
- OpenAI control URL remains sensitive to anti-bot interstitial responses, so acceptance for translation quality is based on content-serving control URLs where text extraction is available.
- Token Protector hotfix is validated on OpenAI control page: no over-protection (`token_protected_count=0` for content run), full part translation (`translated_parts=170`), and no broken `<img>` assets in generated offline output.
- In-article markdown snippets now translate correctly on the target Cookbook page, and code examples keep code intact while allowing comment-only translation via offset-aware apply logic.

Retrospective placeholders (to update after delivery):
- what shipped vs planned,
- major regressions prevented,
- what should be simplified in Phase 2.

## Context and Orientation

Primary docs and contracts:
- `docs/TECHNICAL_SPEC_WEB2RU.md` (authoritative functional and non-functional requirements).
- `docs/requirements.md` (working requirement summary).
- `docs/architecture.md` (module boundaries and contracts).
- `docs/risks_and_assumptions.md` (accepted assumptions and risk controls).
- `AGENTS.md` and `PLANS.md` (process and guardrails for execution).

Expected implementation targets:
- `src/web2ru/cli.py`
- `src/web2ru/pipeline/online_render.py`
- `src/web2ru/pipeline/offline_process.py`
- `src/web2ru/assets/*`
- `src/web2ru/extract/*`
- `src/web2ru/translate/*`
- `src/web2ru/apply/*`
- `src/web2ru/freeze/*`
- `src/web2ru/report/*`

## Invariants & Acceptance Criteria

The plan must prove these invariants:

1) DOM integrity:
- only text nodes and allowlisted attributes are changed.
- Proof: structural fingerprint test before/after apply (ignoring text and allowed attrs).

2) Token Protector invariants:
- placeholders preserved 1:1, unchanged.
- Proof: validator tests with strict mode on/off cases.

3) Structured output strictness:
- schema-valid JSON, each id exactly once, no missing/duplicate ids.
- Proof: unit tests for response validation and retry/split behavior.

4) Offline purity:
- `0 external requests` in default mode.
- Proof: local serve + Playwright external-domain blocking test.

5) Security posture:
- `freeze-js` defaults remain `auto->on`; no silent relaxation.
- Proof: freeze transform tests and CLI default tests.

## Plan of Work

Milestone 1: Project skeleton and contracts
- Create package layout under `src/web2ru`.
- Add typed config models and CLI options matching spec.
- Add `report` schema scaffolding and basic logging.

Milestone 2: Online phase
- Implement Playwright render flow, readiness strategy, auto-scroll.
- Capture assets to cache with metadata and limits.
- Implement shadow DOM best-effort materialization and stats.

Milestone 3: Offline extract/translate/apply
- Parse `html_dump`, sanitize `<base>`.
- Implement scope + exclusions + block/parts extraction.
- Implement Token Protector, batching, OpenAI client, strict validation, retry/split/fallback.
- Apply translated text/attrs while preserving DOM structure.

Milestone 4: Asset scan/rewrite and freeze
- Scan needed URLs in HTML/CSS including `template[shadowrootmode]`.
- Fetch missing assets best effort with reporting.
- Rewrite HTML/CSS URLs to strict relative local paths.
- Apply freeze-js sanitization, SRI stripping, iframe policy, noscript handling.

Milestone 5: Report and validation
- Emit complete `report.json`.
- Add offline validator, integration fixtures, and CLI smoke coverage.

## Concrete Steps

Working directory for all commands:
- `cd /Users/sergejavdejcik/Library/Mobile Documents/com~apple~CloudDocs/2026_1_air/web2RU`

1. Bootstrap package and test scaffolding.
   - create `src/web2ru/...` modules and `tests/unit`, `tests/integration`, `tests/e2e` skeletons.

2. HUMAN APPROVAL REQUIRED: add production dependencies in project config.
   - expected deps: `playwright`, `httpx`, `lxml`, `tinycss2`, `typer` (and minimal supporting libs).

3. Implement Milestones 1-5 in small reviewable commits.

4. Run quality gates.
   - `ruff format .`
   - `ruff check .`
   - `mypy src`
   - `pytest -q`

5. HUMAN APPROVAL REQUIRED: run live regression smoke on one external URL.
   - verify snapshot output and `0 external requests` in default mode.

## Validation & Acceptance

Unit validation:
- Token Protector, schema validator, batching and retry/split paths.
- extract/apply invariants, whitespace reconstruction, attr translation rules.
- asset rewrite and freeze transforms on fixtures.

Integration validation:
- fixture-driven offline pipeline generates `index.html`, `assets/...`, `report.json`.
- no unresolved external asset URLs remain in default mode.

Acceptance checklist:
- quality gates pass,
- output contains required artifacts,
- report contains required metrics and warnings,
- default-mode snapshot passes external-request validator.

## Idempotence and Recovery

- Cache-backed operations (assets/translations) are idempotent by key.
- Retry-safe writes: generate outputs in temp location, then atomic move to final `output/<slug>`.
- If a batch fails permanently, fallback to per-item translation or original text with explicit report entry.
- If online phase fails, preserve partial logs and captured assets for rerun diagnostics.

## Artifacts and Notes

Expected artifacts per successful run:
- `output/<slug>/index.html`
- `output/<slug>/assets/...`
- `output/<slug>/report.json`

Evidence to record during implementation:
- before/after fixture diffs for rewritten HTML/CSS,
- validator logs for placeholder integrity and schema checks,
- offline external-request check summary.

## Interfaces and Dependencies

External interfaces:
- Playwright Chromium runtime.
- OpenAI Responses API with strict JSON schema outputs.

Core internal interfaces:
- Online phase output contract: `final_url`, `html_dump`, `asset_cache`, shadow stats.
- Extract output contract: blocks/parts with stable ids and node refs.
- Translate output contract: list of `{id, text}` covering every requested id exactly once.
- Report contract: stable keys required by spec section 9.3.

Dependency policy:
- keep production deps minimal and explicit,
- prefer deterministic fixture tests over live-network tests in CI,
- any dependency change follows HUMAN APPROVAL REQUIRED gate.
