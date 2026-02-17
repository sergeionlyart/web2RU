# Surf Navigation Comfort: Cross-Origin by Default + Clear Failure Pages

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan complies with `/AGENTS.md` and `/PLANS.md`.

## Purpose / Big Picture

Make link-to-link reading in `surf` mode seamless: links should route through Web2RU translation regardless of domain.
When translation fails, users should see a clear, actionable message instead of silent non-translation behavior.

## Scope

In scope:
- Enable cross-origin surf rewriting by default.
- Keep an explicit flag to re-enable same-origin-only behavior.
- Improve surf navigation error pages for unsupported links, anti-bot blocks, and limits.
- Avoid stale reuse of old surf sessions with previous origin policy.
- Add unit tests and run full quality gates.

Out of scope:
- Changes to translation model/prompt contracts.
- Anti-bot bypasses.
- Output format changes outside surf navigation UX.

## Safety & Guardrails

- No new dependencies.
- No additional data egress.
- Offline purity unaffected.
- Existing CLI flag retained; default adjusted to user-requested behavior.

## Progress

- [x] (2026-02-17 17:35Z) Confirmed root cause: external links were not rewritten due same-origin restriction.
- [x] (2026-02-17 17:37Z) Switched surf default to cross-origin allowed.
- [x] (2026-02-17 17:38Z) Added user-friendly surf error classification with fallback link to source.
- [x] (2026-02-17 17:39Z) Added session slug suffix by origin policy to avoid stale page reuse.
- [x] (2026-02-17 17:40Z) Added/updated tests and passed full lint/type/test suite.
- [x] (2026-02-17 17:41Z) Live-validated `doc.govt.nz` link rewrite in `simonwillison.net` surf session.

## Surprises & Discoveries

- Existing surf output reused old rendered pages, so config default changes were invisible without a fresh session key.
- The specific link issue reproduced directly in generated HTML (`href` stayed external until policy/default was updated).

## Decision Log

- Decision: Default `--surf-same-origin-only` to `off`.
  Rationale: Matches user requirement for frictionless cross-site translated surfing.
  Date/Author: 2026-02-17 / Codex

- Decision: Add specific error-page messaging by failure category.
  Rationale: Users need understandable feedback when translation cannot proceed.
  Date/Author: 2026-02-17 / Codex

- Decision: Include origin-policy suffix in surf session slug.
  Rationale: Prevent stale/incorrect reuse of previously rendered pages built under older policy.
  Date/Author: 2026-02-17 / Codex

## Outcomes & Retrospective

Implemented and validated. In surf mode, external links now rewrite to `__web2ru__/go` by default.
When page translation fails, users get explicit status/reason and can open the original target page.
