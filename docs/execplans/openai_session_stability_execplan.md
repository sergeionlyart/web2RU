# OpenAI Domain Session Stability (Persistent Profile + Storage State + Rate Limit)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan complies with `/AGENTS.md` and `/PLANS.md`.

## Purpose / Big Picture

Improve stability for pages under `openai.com` where anti-bot interstitials are intermittent.
The user-visible result is: if access is allowed, Web2RU should reuse prior browser session state and avoid bursty
navigation cadence, reducing repeated challenge hits. If access is blocked, Web2RU must still fail explicitly.

## Scope

In scope:
- Add a session policy for `openai.com` that enables persistent Playwright profile reuse.
- Reuse `storage_state` (cookies/local storage snapshot) between runs.
- Add a conservative per-domain rate limiter for `openai.com` navigations.
- Keep existing interstitial detection and explicit error behavior.
- Add unit tests for policy/rate-limit behavior.

Out of scope:
- Any bypass of anti-bot mechanisms.
- New CLI flags or changed CLI defaults.
- Changes to translation contracts, schema, or freeze-js behavior.

## Safety & Guardrails

- Live network is not required for implementation; optional post-check can be run separately.
- No new external dependencies.
- No data exfiltration; state is stored locally under configured cache directory.
- Offline purity contract remains unchanged.
- CLI surface remains unchanged (ENV-only tuning for rate limit).

## Progress

- [x] (2026-02-17 15:25Z) Created plan and acceptance criteria.
- [x] (2026-02-17 15:25Z) Implemented `openai.com` session policy (persistent profile + storage state paths).
- [x] (2026-02-17 15:25Z) Integrated domain rate-limit in online render attempts.
- [x] (2026-02-17 15:25Z) Wired config/env and report observability for `openai_min_interval_ms`.
- [x] (2026-02-17 15:27Z) Run lint/type/test suite and validate no regressions.
- [x] (2026-02-17 15:29Z) Optional live validation on `openai.com` with session/rate-limit artifacts confirmed.

## Surprises & Discoveries

- Interstitial hits on `openai.com` are non-deterministic in the same day/session; some runs succeed, some fail.
- Returning explicit error on challenge pages is safer than silently producing empty/non-translated output.
- After policy rollout, cache artifacts are created as expected:
  `browser_profiles/openai.com`, `storage_state/openai.com.json`, `rate_limit/openai.com.json`.

## Decision Log

- Decision: Apply persistent profile/state only for `openai.com` via automatic policy.
  Rationale: Fix target instability with minimal blast radius for other domains.
  Date/Author: 2026-02-17 / Codex

- Decision: Keep configuration via ENV (`WEB2RU_OPENAI_RATE_LIMIT_MS`) instead of new CLI flags.
  Rationale: Avoid CLI surface changes while enabling operator tuning.
  Date/Author: 2026-02-17 / Codex

## Outcomes & Retrospective

Implementation complete.
Expected outcome preserved: improved repeat-run stability for `openai.com` when challenge is not hard-blocking, with no regressions for other domains.
Live note: domain can still hard-block and return interstitial after retries; now the behavior is explicit and session artifacts are reused between runs.
