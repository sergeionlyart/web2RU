# Repair Scroll-Locked Surf Pages

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must comply with /AGENTS.md and with the standards in /PLANS.md.

## Purpose / Big Picture

Some translated surf pages can render correctly but refuse vertical scrolling. After this change, a user should be
able to open a translated surf page and scroll up/down normally even when the source site applied root/body or wrapper
CSS that locks viewport height or overflow.

## Scope

In scope: diagnose `http://127.0.0.1:8794/__web2ru__/page/fab6f55f52b1c731/index.html`, patch the minimal offline
sanitization/freeze logic needed to restore vertical scroll, add tests, run quality gates, and open a PR to `main`.

Out of scope: translation schema/prompt changes, asset URL rewriting changes, CLI flags/defaults, and unrelated
refactors.

## Safety & Guardrails

This task inspects already-generated local output and may use the running local server. Live network was already
authorized by the user by asking for the translated surf page and providing the local translated URL. The code change
must preserve offline purity and must not re-enable scripts or relax network blocking. No secrets are read or printed.

Because this touches freeze-js/sanitization behavior, this ExecPlan is required. No production dependencies, output
format changes, or CLI defaults will be added.

## Progress

- [x] (2026-06-27 20:20Z) Created this ExecPlan.
- [x] (2026-06-27 20:33Z) Diagnosed Sourcepoint CMP `sp-message-open` root class and `sp_message_container_*` overlay as the scroll lock.
- [x] (2026-06-27 20:36Z) Implemented minimal Sourcepoint overlay removal and root/body scroll unlock in `freeze_js.py`.
- [x] (2026-06-27 20:37Z) Added unit regression test for Sourcepoint scroll lock.
- [x] (2026-06-27 20:42Z) Rebuilt the affected page through surf mode and verified browser `scrollY` changes from 0 to 700.
- [x] (2026-06-27 20:43Z) Ran `uv run --extra dev ruff check .` and `WEB2RU_REASONING_EFFORT=medium uv run --extra dev pytest -q`; both passed.
- [x] (2026-06-27 20:46Z) Created PR `https://github.com/sergeionlyart/web2RU/pull/2` targeting `main`.

## Surprises & Discoveries

- The problematic page is not a Simon Willison page; it is a surf-linked `the-decoder.com` article. Evidence:
  manifest maps `fab6f55f52b1c731` to `https://the-decoder.com/landmark-german-ruling-declares-googles-ai-overviews-are-googles-own-words-and-makes-it-liable-for-false-answers/`.
- Browser metrics before the patch showed `scrollHeight == clientHeight == 894`, `window.scrollTo(0, 700)` left `scrollY == 0`, `html.className == "sp-message-open"`, body computed `overflow: hidden` and `position: fixed`, and Sourcepoint container style `display: block`.

## Decision Log

- Decision: Keep the fix in existing offline sanitization/freeze plumbing unless diagnostics prove a narrower module.
  Rationale: Scroll locks are output safety/comfort concerns and should not affect translation contracts or assets.
  Date/Author: 2026-06-27 / Codex.
- Decision: Treat Sourcepoint consent UI as a known offline-blocking overlay alongside Funding Choices and LinkedIn.
  Rationale: Its disabled JS cannot dismiss the modal, and the captured CSS locks document scrolling via `sp-message-open`.
  Date/Author: 2026-06-27 / Codex.

## Outcomes & Retrospective

Implemented and opened as PR `https://github.com/sergeionlyart/web2RU/pull/2`.

The bug was caused by Sourcepoint CMP markup captured after online render. Since Web2RU freezes JS, the consent modal
could not be dismissed, while its root class kept the document in a fixed, non-scrollable modal state. The patch removes
that overlay family and unlocks root/body scrolling during freeze-js sanitization.

Patched local rebuild evidence: report shows `overlays_neutralized_count: 2`, `scroll_unlocks_count: 2`,
`fallback_parts: 0`, `errors: 0`; browser check shows Sourcepoint container absent and `window.scrollTo(0, 700)`
sets `scrollY` to `700`.

## Context and Orientation

Relevant files likely include `src/web2ru/freeze/freeze_js.py`, which neutralizes scripts and scroll-hostile overlays,
and `src/web2ru/pipeline/offline_process.py`, which may add domain-specific scroll repairs after freeze. Existing tests
live in `tests/unit/test_freeze_js.py` and `tests/integration/test_offline_pipeline.py`.

Web2RU must preserve DOM structure, keep offline output free of external requests, and keep freeze-js deny-by-default
security behavior intact. This fix should only add CSS/style repair needed for scrolling.

## Invariants & Acceptance Criteria

Acceptance:

- The problematic local page has `document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight`.
- Calling `window.scrollTo(0, 500)` changes `window.scrollY` on the problematic page.
- The generated page remains translated and served locally.
- Unit/integration tests cover the scroll-locking pattern.
- `ruff check .` and `pytest -q` pass under the same environment constraints used in this repo.

Applicable invariants:

- DOM integrity: do not restructure source DOM; only add/update sanitization style where already allowed.
- Offline purity: do not keep or introduce external runtime requests.
- Security posture: do not re-enable scripts, event handlers, iframes, or relaxed CSP/network behavior.

## Plan of Work

First, inspect the surf manifest, page report, HTML, CSS, and browser scroll metrics for page key `fab6f55f52b1c731`.
Then map the observed lock to code paths in freeze/offline processing. Implement the smallest general repair that
fixes this class without site-specific hacks unless the pattern is truly unique. Add tests that fail on the current
pattern and pass with the patch. Rebuild or reprocess as needed, validate in the browser, run quality gates, then
stage only the intended files and create a PR.

## Concrete Steps

Run diagnostics from `/Users/sergejavdejcik/Code/web2RU`:

    find /tmp -path '*surf-simonwillison.net-8b0eaafe-any/manifest.json' -print
    curl -sS http://127.0.0.1:8794/__web2ru__/page/fab6f55f52b1c731/index.html

Run validation:

    uv run --extra dev ruff check .
    WEB2RU_REASONING_EFFORT=medium uv run --extra dev pytest -q

## Validation & Acceptance

Use unit tests for the sanitization helper and, if practical, an integration fixture for offline process scroll repair.
Use the in-app browser or a local browser check to confirm `scrollY` changes on the generated page after the fix.

## Idempotence and Recovery

The change should be safe to rerun: generated `/tmp/web2ru-*` outputs can be recreated, and tests are deterministic.
If the patch causes regressions, revert the commit/PR. Do not reset or discard pre-existing local uncommitted changes.

## Artifacts and Notes

Pending diagnostics.

## Interfaces and Dependencies

No new dependencies. The patch should use existing lxml/style handling and existing test tooling.
