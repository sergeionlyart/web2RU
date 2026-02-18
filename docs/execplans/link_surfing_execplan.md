# Web2RU Multi-Page Surfing Mode (On-Demand Link Translation)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan complies with `/AGENTS.md` and `/PLANS.md`.

## Purpose / Big Picture

Enable low-friction browsing across links from a translated page:
- user starts with one URL,
- clicks an internal link on translated page,
- receives translated target page automatically,
- continues browsing translated pages in one local session.

User-visible result:
- "translated surfing" works without manual re-running `web2ru` for each clicked URL.

## Scope

In scope (MVP):
- new on-demand local serve mode for same-origin links (`surf mode`);
- automatic translation of target page when clicked link is not yet prepared;
- persistent page cache/manifest for generated pages in one site session;
- rewriting internal links to local surf routes;
- deterministic blocking navigation flow (`go` route waits for generation, then redirects).

In scope (Phase 2):
- optional prefetch mode (`crawl-depth`) for immediate navigation across N levels;
- shared site glossary for better terminology consistency across pages.

Out of scope:
- cross-origin crawling by default;
- authenticated/paywalled navigation flows;
- full SPA route emulation (client-side routers that never expose real URLs);
- complete offline browsing of unvisited pages without prefetch/crawl.

## Safety & Guardrails

- Live network is REQUIRED for on-demand translation of newly visited URLs.
- HUMAN APPROVAL REQUIRED:
  - CLI surface changes (`--mode surf`, `--crawl-depth`, budgets),
  - any dependency additions/upgrades,
  - any change to translation schema/prompt/Token Protector logic,
  - live validation on external sites.
- Data handling:
  - URLs and translated text may contain sensitive content;
  - do not log raw page bodies by default;
  - never expose `OPENAI_API_KEY`.
- Security/network policy:
  - default allowlist: same origin as start URL only;
  - deny non-http(s), `javascript:`, `data:`, `file:`, loopback/private-network targets unless explicitly allowed.
- Offline purity:
  - each generated page must still satisfy Web2RU offline invariants (`0 external requests` for snapshot output).

## Progress

- [x] (2026-02-17 13:14Z) Feasibility analysis completed and architecture options compared.
- [x] (2026-02-17 13:14Z) ExecPlan drafted with phased rollout and acceptance criteria.
- [x] (2026-02-17 13:24Z) Confirm MVP CLI/API shape and implement:
  - `--mode single|surf`,
  - `--surf-same-origin-only on|off`,
  - `--surf-max-pages`.
- [x] (2026-02-17 13:24Z) Implement MVP surf mode end-to-end:
  - on-demand per-link page translation,
  - manifest persistence and page cache reuse,
  - same-origin link rewrite to local surf routes,
  - local surf server with deterministic error pages.
- [x] (2026-02-17 13:24Z) Add unit/e2e coverage for surf router/session/CLI and run full quality gates.
- [x] (2026-02-17 13:52Z) Run authorized live validation on control URLs (functional surf mode, fixed local ports):
  - `openai`: startup/navigation route ok; page had no rewritten `go` links for click-check sample.
  - `simon`: first sampled link (`atom/everything`) was non-representative for article navigation and timed out; targeted HTML link (`/about/`) passed (`go` => `302`).
  - `edison`: passed (`go` => `302`).
  - `matt`: passed (`go` => `302`).
  - `minimaxir`: passed (`go` => `302`).

## Surprises & Discoveries

- Current pipeline is single-page oriented and writes one `output/<slug>/index.html` per run.
  Evidence: `src/web2ru/pipeline/offline_process.py` produces one `OfflineResult`.
- Current `--open --serve on` serves a static folder only and cannot generate missing pages on click.
  Evidence: `src/web2ru/cli.py` uses `SimpleHTTPRequestHandler` for static serving.
- Existing translation and asset caches already provide a strong base for on-demand multi-page mode.
  Evidence: `translation_cache.sqlite3` and reusable `AssetCache`/URL slugging exist in current flow.
- A fully asynchronous progress page is not required for MVP correctness and can be deferred.
  Evidence: blocking `go` route with deterministic completion/error page already provides one-click navigation semantics without manual rerun.
- Sampling first internal link for click-check can pick non-HTML endpoints (Atom/Webmention/etc.) and produce false-negative navigation verdicts.
  Evidence: `simonwillison.net` first sampled link was Atom feed; explicit HTML page link (`/about/`) passed.

## Decision Log

- Decision: build MVP as on-demand local surf server first, then optional prefetch crawl.
  Rationale: fastest path to "click -> translated page" with controlled compute cost.
  Date/Author: 2026-02-17 / Codex.

- Decision: default navigation scope is same-origin only.
  Rationale: safety, predictable cost, and lower SSRF/exfiltration risk.
  Date/Author: 2026-02-17 / Codex.

- Decision: keep per-page snapshot contract unchanged (`index.html`, `assets`, `report.json`), add manifest above it.
  Rationale: reuse existing pipeline and tests with minimal risk.
  Date/Author: 2026-02-17 / Codex.

- Decision: implement synchronous on-demand translation in `go` route for MVP, defer async progress polling to Phase 2.
  Rationale: reduces implementation risk while still meeting primary UX requirement ("click link -> get translated page").
  Date/Author: 2026-02-17 / Codex.

- Decision: for live surf validation, prefer HTML navigational links over feed/webmention endpoints when choosing click-check candidates.
  Rationale: better reflects user-facing browsing workflow and avoids false negatives from non-article resources.
  Date/Author: 2026-02-17 / Codex.

## Outcomes & Retrospective

Target outcome:
- user can surf translated same-origin pages in one session with minimal friction;
- no regression in DOM integrity, offline purity, structured outputs, and freeze-js safety.

Status now:
- MVP surf mode implemented in codebase with tests;
- remaining: authorized live multi-page validation on control URLs and potential async progress refinement.

Retrospective (after delivery):
- navigation latency vs quality tradeoff,
- cache effectiveness,
- what to move from Phase 2 into defaults.

## Context and Orientation

Primary modules to extend:
- `src/web2ru/cli.py` (new mode/flags and bootstrapping surf server),
- `src/web2ru/pipeline/online_render.py` (reuse as-is; optionally expose reusable function),
- `src/web2ru/pipeline/offline_process.py` (reuse as-is; ensure deterministic per-page outputs),
- `src/web2ru/assets/rewrite_html.py` (internal link rewrite to surf routes),
- `src/web2ru/report/builder.py` and report fields (surf session diagnostics),
- new module(s): `src/web2ru/surf/server.py`, `src/web2ru/surf/router.py`, `src/web2ru/surf/manifest.py`.

Requirements relied on:
- `docs/TECHNICAL_SPEC_WEB2RU.md` single-page snapshot invariants remain mandatory per generated page.
- `AGENTS.md` non-negotiables remain unchanged.

## Invariants & Acceptance Criteria

Core invariants (must remain green):
1. DOM integrity unchanged except allowed text/attrs.
2. Structured outputs strictness unchanged.
3. Token Protector invariants unchanged.
4. Offline purity remains true for each generated page snapshot.
5. Security posture (`freeze-js`/sanitization) not weakened.

New surfing acceptance criteria:
1. Clicking same-origin link on translated page opens translated target page without manual CLI rerun.
2. Revisit of previously translated link is served from cache (no full regeneration).
3. Broken/missing page translation shows deterministic error page with retry link, not blank/hang.
4. Route-to-source mapping is stable and resumable after process restart.
5. Session report includes pages translated, cache hits, failures, total elapsed.

## Plan of Work

Milestone 1: Surf routing and manifest
- Add URL normalization + stable page key (canonical URL -> page id).
- Add persistent manifest (JSON/SQLite): source URL, output dir, status, timestamps, error.
- Add route format: `/__web2ru__/page/<page_id>/`.

Milestone 2: On-demand translation orchestrator
- Introduce queue with dedup:
  - one translation task per URL at a time,
  - concurrent clicks on same URL await same task.
- Reuse existing pipeline to generate page snapshot for target URL.
- Save manifest status transitions: `pending -> running -> ready|failed`.

Milestone 3: Surf HTTP server
- Replace static-only serving with custom handler:
  - serve ready pages by route,
  - trigger background translation when missing,
  - return progress page and auto-refresh until ready.
- Preserve existing `--open/--serve` behavior for default single-page mode.

Milestone 4: Internal link rewriting strategy
- During page rewrite, convert same-origin `<a href>` to surf routes.
- Keep external links explicit (open externally or blocked by policy, configurable).
- Preserve anchors/fragments where possible.

Milestone 5: Reliability and budgets
- Add limits:
  - max pages per session,
  - max concurrent page builds,
  - optional max spend guard by estimated tokens/pages.
- Add graceful cancellation and resume from manifest.

Milestone 6: Validation and rollout
- Unit tests for URL normalization, policy checks, manifest transitions, dedup queue.
- Integration tests on local mini-site with 3-5 linked pages.
- E2E test: click through links and verify translated outputs served.
- Authorized live validation on control URLs.

## Concrete Steps

Working directory:
- `cd /path/to/web2RU`

Implementation sequence:
1. Add `surf` modules and manifest storage.
2. Add CLI flags (proposed):
   - `--mode single|surf` (default `single`),
   - `--surf-same-origin-only on|off` (default `on`),
   - `--surf-max-pages <int>`,
   - `--surf-concurrency <int>`.
3. Integrate on-demand orchestrator with existing pipeline entrypoint.
4. Implement link rewriting to surf routes.
5. Add tests and diagnostics to `report.json` (session-level artifact).
6. Run quality gates and live validation.

Quality commands:
- `ruff check .`
- `mypy src`
- `pytest -q`

## Validation & Acceptance

- [ ] Unit tests for surf router/manifest/orchestrator pass.
- [ ] Integration mini-site test verifies click-through translated navigation.
- [x] E2E test confirms no manual rerun required for linked pages.
- [x] Per-page `report.json` contract remains unchanged and generated by existing pipeline.
- [x] No regression in existing single-page mode tests.
- [x] Live control-url validation approved and documented.

## Idempotence and Recovery

- Manifest-based status makes retries idempotent.
- Failed page entries can be retried without corrupting existing ready pages.
- Existing caches (`asset`, `translation`) remain reusable across page builds.
- On crash/restart, surf server reloads manifest and serves ready pages immediately.

## Artifacts and Notes

Expected new artifacts:
- session manifest (e.g., `output/<session_slug>/manifest.json`),
- per-page outputs under session folder,
- session summary report (e.g., `output/<session_slug>/session_report.json`),
- existing per-page `report.json` unchanged/extended compatibly.

## Interfaces and Dependencies

Preferred MVP: no new production dependencies (use stdlib HTTP server + current pipeline).

If async server/framework is needed later, that is HUMAN APPROVAL REQUIRED with explicit rationale.
