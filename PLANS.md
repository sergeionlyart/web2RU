# Web2RU Codex Execution Plans (ExecPlans)

This document defines what an execution plan (“ExecPlan”) is in this repository and how to write one so that a
stateless coding agent (or a human new to the repo) can deliver a working change end-to-end.

This file is intentionally prescriptive. It is adapted from OpenAI’s guidance on using PLANS.md for multi-hour work,
with project-specific guardrails added for Web2RU. (Keep it short enough to be readable.)

---

## 1) What is an ExecPlan

An ExecPlan is a living design-and-implementation document that:

- explains **why** the work matters in user-visible terms,
- describes the **exact sequence** of edits and commands to run,
- defines **observable acceptance** (not just “code exists”),
- records discoveries and decisions as work proceeds,
- is sufficient to resume work using **only the repo + this plan**.

Think of it as “the single source of truth for one change”.

---

## 2) When an ExecPlan is REQUIRED in this repo

Write an ExecPlan before implementing work that is any of:

- Cross-cutting pipeline changes (online render, offline processing, translation, apply, assets, freeze).
- Any change that can affect **offline purity** (“0 external requests”).
- Any change to **translation contracts**:
  schema, prompts, batching, retry/splitting, caching, Token Protector rules.
- Any change to **freeze-js / sanitization / security posture**.
- New CLI flags, changed defaults, or changed output layout (`report.json`, output folders).
- Any task expected to take more than ~1–2 hours or with meaningful unknowns.

For small, low-risk changes (typos, isolated refactors covered by tests), an ExecPlan is optional.

---

## 3) Relationship to AGENTS.md and repo skills

- Codex reads `AGENTS.md` automatically. This ExecPlan process MUST comply with the guardrails in `AGENTS.md`.
- If the repo contains skills under `.agents/skills/`, prefer those canonical procedures for:
  dev setup, quality gates, and safety checks, rather than inventing new commands.

If an ExecPlan conflicts with `AGENTS.md`, treat it as a bug in the plan and fix the plan first.

---

## 4) Web2RU non-negotiables (must be enforced in plans)

If your change touches the pipeline output, your ExecPlan MUST include validation that preserves these invariants:

1) DOM integrity:
   - Do not restructure DOM.
   - Only modify text nodes and explicitly allowed attributes.

2) Token Protector invariants:
   - Protected placeholders must round-trip unchanged.
   - Any placeholder mismatch is treated as an error, not “best effort”.

3) Structured outputs strictness:
   - Model output must validate against the JSON schema.
   - All requested ids must be present exactly once.

4) Offline purity:
   - Serving the output locally must yield **0 external network requests**.

5) Security posture:
   - freeze-js defaults and “deny by default” behavior must not be silently weakened.
   - Any relaxation requires explicit approval and dedicated tests.

Your ExecPlan must state which of these apply and how they will be proven.

---

## 5) Approval gates (human-in-the-loop)

Plans MUST explicitly mark steps that require human confirmation BEFORE execution, including:

- adding/upgrading production dependencies,
- changing translation schema/prompt/Token Protector rules,
- changing freeze-js behavior, network blocking, iframe policy, CSP/meta handling,
- running any live-network workflow (real URLs) if not explicitly authorized,
- changing CLI defaults or output formats.

Use a clear marker like: “HUMAN APPROVAL REQUIRED”.

---

## 6) Self-containment (practical version for this repo)

An ExecPlan must be self-contained enough to execute without external links.

You MAY reference stable in-repo docs by path (e.g., `docs/TECHNICAL_SPEC_WEB2RU.md`), but you MUST still include
a short summary of the specific requirements you are relying on. Do not make the reader hunt for essential details.

Do NOT require external blogs or documentation to complete the work. If external knowledge is necessary, paraphrase
the needed facts into the plan.

---

## 7) Writing style

Write in plain language. Prefer prose.

Lists are allowed when they improve clarity. Checklists are mandatory in `Progress` and permitted in:
- `Safety & Guardrails`
- `Validation & Acceptance`

Avoid long “wall of bullets” where a paragraph is clearer.

Define any non-obvious term when first introduced unless it is defined in the “Web2RU Glossary” below.

---

## 8) Formatting rules

If you are outputting an ExecPlan into chat, output it as a single Markdown fenced block labeled `md`
and do not nest additional fenced blocks inside it. For commands/transcripts/diffs inside that plan,
use indentation rather than nested code fences.

If you are writing an ExecPlan to a `.md` file where the file content is only the plan,
omit the outer fence.

---

## 9) Milestones

Milestones are how we de-risk and stay honest.

- Each milestone must be independently verifiable.
- Each milestone must end with:
  - exact commands to run,
  - the observable outcome to confirm,
  - what “done” means for that milestone.

Prototyping milestones are encouraged when they reduce uncertainty (asset capture edge cases, Shadow DOM behavior,
Structured Outputs corner cases, etc.). Prototypes must be runnable and either promoted or explicitly discarded.

---

## 10) Required living sections in every ExecPlan

Every ExecPlan MUST include and maintain these sections:

- Progress (checkbox list with timestamps)
- Surprises & Discoveries (with brief evidence)
- Decision Log (decision + rationale + date/author)
- Outcomes & Retrospective

These sections are not optional.

---

## 11) Web2RU glossary (use these definitions to avoid re-explaining)

- Online phase: Playwright-driven page render to a stable state + asset capture.
- Offline phase: local parsing/extraction/translation/application + asset rewriting + freeze-js.
- Offline purity: local serve produces zero external network requests.
- Token Protector: a mechanism that replaces sensitive/structured tokens with placeholders before translation and
  restores them after; placeholders must not change.
- freeze-js: a set of transformations that neutralize scripts, inline handlers, dangerous URLs, meta refresh, etc.
  to ensure offline purity and reduce security risk.

If you use a term not in this list and not common English, define it.

---

## 12) Skeleton of a good Web2RU ExecPlan

    # <Short, action-oriented description>

    This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`,
    and `Outcomes & Retrospective` must be kept up to date as work proceeds.

    This plan must comply with /AGENTS.md and with the standards in /PLANS.md.

    ## Purpose / Big Picture

    Explain what a user can do after this change that they could not do before, and how to see it working.

    ## Scope

    State what is in-scope and explicitly what is out-of-scope.

    ## Safety & Guardrails

    Describe:
    - whether live network is required,
    - any HUMAN APPROVAL REQUIRED gates,
    - data handling considerations (what may contain user content),
    - how offline purity is preserved.

    ## Progress

    - [ ] (YYYY-MM-DD HH:MMZ) ...
    - [ ] ...

    Keep this accurate at every stopping point.

    ## Surprises & Discoveries

    Record unexpected behavior with short evidence.

    ## Decision Log

    - Decision: ...
      Rationale: ...
      Date/Author: ...

    ## Outcomes & Retrospective

    Summarize what was achieved and what remains.

    ## Context and Orientation

    Assume the reader is new to the repo. Name relevant files by full repo-relative path.
    Summarize the specific requirements you are relying on (with doc paths if relevant).

    ## Invariants & Acceptance Criteria

    List the Web2RU non-negotiables that apply to this change and how they will be proven.
    Phrase acceptance as observable behavior.

    ## Plan of Work

    Prose description of the sequence of edits and additions.
    For each edit, name:
    - file path,
    - function/module (if known),
    - what to add/change and why.

    ## Concrete Steps

    Exact commands to run (include working directory).
    Show short expected outputs where it helps a novice confirm success.

    ## Validation & Acceptance

    Include:
    - unit/integration test commands appropriate to the repo,
    - any offline serve + “0 external requests” proof if output is affected,
    - what should fail before and pass after (if applicable).

    Checklists are allowed here.

    ## Idempotence and Recovery

    Describe how to safely retry, roll back, or recover from partial failure.

    ## Artifacts and Notes

    Include concise evidence snippets: diffs, logs, report excerpts, expected file outputs.

    ## Interfaces and Dependencies

    Be prescriptive. Name libraries and key interfaces/types if they must exist at the end.
    If adding a dependency, mark it HUMAN APPROVAL REQUIRED and explain why.

---

If you follow this guidance, an agent (or a novice engineer) can restart from only the ExecPlan and deliver a working,
observable result while preserving Web2RU’s safety and correctness constraints.