# Medium Auth Session Capture for Surf Navigation

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan complies with `/AGENTS.md` and `/PLANS.md`.

## Purpose / Big Picture

When users surf translated pages and click links to Medium, translation often fails due to login requirement.
After this change users can explicitly capture a Medium login session once and reuse it automatically in further
translations (single and surf). If translation is still blocked, users see a clear actionable message.

## Scope

In scope:
- Extend session policy to treat `medium.com` as persistent-session domain.
- Add CLI auth-capture mode for manual login and state save.
- Detect Medium login wall and return explicit guided error.
- Improve surf error rendering for page-route failures too.
- Add/extend unit tests and docs.

Out of scope:
- Bypassing anti-bot/paywall restrictions.
- Non-Medium custom auth providers.

## Safety & Guardrails

- No new dependencies.
- Session data stored only in local cache (`storage_state` + profile dir).
- No telemetry or external data transfer added.
- Offline purity behavior for generated snapshots is unchanged.

## Progress

- [x] (2026-02-17 17:45Z) Added Medium support to session policy.
- [x] (2026-02-17 17:46Z) Added `--auth-capture on` flow in CLI for manual auth capture.
- [x] (2026-02-17 17:47Z) Added Medium login-wall detection and guided runtime error.
- [x] (2026-02-17 17:48Z) Updated surf error routing to show actionable navigation errors.
- [x] (2026-02-17 17:50Z) Run full lint/type/tests and summarize outcomes.

## Surprises & Discoveries

- Medium can return sign-in path (`/m/signin`) after navigation even for article URL, so path-based detection is reliable baseline.

## Decision Log

- Decision: Use explicit auth-capture command mode instead of implicit auto-login flow.
  Rationale: predictable UX, clear user control, and deterministic state save point.
  Date/Author: 2026-02-17 / Codex

- Decision: Keep domain support scoped to Medium for auth-provider guidance.
  Rationale: solves current request with minimal complexity and low risk.
  Date/Author: 2026-02-17 / Codex

## Outcomes & Retrospective

Implementation complete. All quality gates are green:
- `ruff check src tests`
- `mypy src`
- `pytest -q`
