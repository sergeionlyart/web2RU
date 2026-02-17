# Web2RU — Codex working agreement (repo-level)

# ExecPlans

For complex features, risky refactors, or any change that touches translation contracts, asset rewriting, or freeze-js,
start with an ExecPlan as defined in /PLANS.md and keep it updated until the work is complete.

## 0) Mission (what we are building)
Web2RU is a CLI utility that produces an **offline Russian snapshot** of a single web page:
- renders the page (incl. JS) to a stable state (Playwright/Chromium),
- captures all required assets (HTML + CSS/JS/fonts/images),
- extracts only user-visible text (excluding code/tech blocks),
- translates EN→RU via OpenAI **Responses API** using **Structured Outputs (JSON Schema)**,
- applies translations back **without changing DOM structure**,
- rewrites asset URLs to strictly-relative local paths,
- hardens the snapshot for offline viewing (**freeze-js=on** by default),
- outputs `output/<slug>/index.html`, `assets/…`, `report.json`.

**Key principle:** “snapshot + replace text”, NOT “generate new HTML”.

## 1) Non-negotiables (Definition of Done)
A change is “done” only if ALL hold:
1. **DOM integrity:** No node structure changes; we only modify:
   - text nodes (`node.text`) and selected attributes (`title`, `aria-label`, `placeholder`, `alt` by rules).
2. **Offline purity:** When serving output locally, there must be **0 external network requests**.
3. **LLM safety:** Structured outputs are validated (schema + id coverage + Token Protector invariants).
4. **Reproducibility:** Commands in this repo work on macOS/Linux; Windows is best-effort.
5. **Observability:** `report.json` is updated/extended when behavior changes.

If any item is not satisfied, stop and fix before moving on.

## 2) Agent operating rules (how you work here)
### 2.1 Plan-first, small diffs
- Start each task with a short plan and explicit acceptance criteria.
- Prefer **small, reviewable commits/PRs**; avoid “mega changes”.
- Keep diffs minimal: only change what the task requires.

### 2.2 Guardrails
Ask for human confirmation BEFORE you:
- add or upgrade production dependencies,
- change CLI surface (flags/defaults) or output format,
- change translation schema/prompt rules, Token Protector logic, or freeze-js behavior,
- run anything that uses **live network** (Playwright fetch, live regression) unless the task explicitly authorizes it,
- introduce any code that could exfiltrate data (telemetry, uploads, background beacons).

### 2.3 Source of truth
- The technical spec in `/docs/TECHNICAL_SPEC_WEB2RU.md` is authoritative.
- If a requirement conflicts with reality, implement best-effort and record an **Assumption** in `/docs/risks_and_assumptions.md`.

## 3) Repository map (expected structure)
- `src/web2ru/cli.py` — Typer/Click entrypoint (argument parsing, orchestration).
- `src/web2ru/pipeline/online_render.py` — Playwright online phase.
- `src/web2ru/pipeline/offline_process.py` — Offline parse/translate/apply/freeze phase.
- `src/web2ru/assets/` — capture cache, scan, fetch-missing, rewrite (HTML+CSS).
- `src/web2ru/extract/` — scope detection, block/textnode extraction.
- `src/web2ru/translate/` — batching, Responses API client, schema validation, retries, caches.
- `src/web2ru/apply/` — applying translations back to exact nodes/attrs.
- `src/web2ru/freeze/` — JS neutralization + sanitization.
- `src/web2ru/report/` — report.json builder + schema.
- `tests/unit/` — deterministic, fixture-driven tests (no network).
- `tests/integration/` — local fixture-based pipeline runs.
- `tests/e2e/` — (optional) end-to-end CLI runs.
- `scripts/` — dev helpers (regression runner, snapshot validator, etc.).
- `.agents/skills/` — Codex skills for this repo (keep concise).
- `agents/roles/`, `agents/workflows/` — role & workflow playbooks.

## 4) Local dev commands (canonical)
> Prefer `make ...` targets when available.

### 4.1 Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
python -m playwright install chromium
```

### 4.2 Quality gates (run before PR)
```bash
ruff format .
ruff check .
mypy src
pytest -q
```

### 4.3 Integration / e2e
- Fixture-based integration tests are allowed in PR CI.
- **Live** regression (hits real URLs) must be opt-in and may be flaky; ask before running.

## 5) Engineering standards
- Python: PEP 8, type hints everywhere, small single-purpose functions.
- Prefer pure functions + explicit IO boundaries (filesystem/network).
- No hidden global state; caching must be explicit and testable.
- All parsing/rewriting logic must be covered by unit tests on HTML/CSS fixtures.
- Security: default to “deny” for anything that could trigger network in offline output.

## 6) Contracts (IO expectations per pipeline stage)
### Online phase (Playwright)
Input: `url`, render options.  
Output:
- `final_url: str`
- `html_dump: str` (DOM serialization after stabilization)
- `asset_cache` populated from network capture
- shadow-dom stats (if enabled)

### Offline phase (parser)
Input: `html_dump`, `final_url`, `asset_cache`, processing options.  
Output:
- rewritten `index.html` with RU text
- `assets/…` local files + rewritten CSS
- `report.json` with required fields

### Translate step
Input: `{blocks|items}` payload with stable `id`s and Token Protector placeholders.  
Output: JSON matching schema: `[{id, text}]` covering all ids; placeholders preserved.

## 7) Task template (how to prompt Codex effectively)
Write tasks like a GitHub issue:
- **Goal** (one sentence)
- **Scope** (what to change / what NOT to change)
- **Acceptance criteria** (explicit checks)
- **Files/Modules** to touch (if known)
- **How to test** (commands)
- **Risk notes** (security/network)

This is the fastest way to keep changes aligned and reviewable.

## 8) ExecPlans

When writing complex features or significant refactors, use an ExecPlan (as described in `/PLANS.md`) from design to implementation.
