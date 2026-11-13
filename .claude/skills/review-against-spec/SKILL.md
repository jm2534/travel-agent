---
name: review-against-spec
description: Review tests or code against a requirements doc in fresh-context sub-agents. Tests mode checks that tests would catch a broken requirement; final mode checks the code meets every requirement and is well built. Use when checking requirement coverage or reviewing work against a spec.
---

## Inputs

- **Spec:** `REQUIREMENTS.md` by default, or a path or pasted text. If there is none, ask for it.
- **Scope:** requirement IDs, files, or the whole working tree. If the user gives a git ref, scope to `git diff <ref>`.
- **Mode:** `tests` or `final`. If unstated, use `final`.

Run each reviewer as a sub-agent started with a fresh context window, in the foreground. Give it the spec, the scope, and its brief below. Reviewers may run the tests but never edit files. Present their reports as returned; fixing is the user's call.

## Tests mode: one sub-agent

Brief: "For each in-scope requirement, find its tests (the requirement ID opens their docstring) and judge whether they would fail if the requirement were broken. Report:
(a) requirements with no test, or whose examples or failure behavior aren't tested;
(b) weak requirement tests: tautological, coupled to implementation (mocking the project's own modules, asserting on calls), or passing against a stub;
(c) unlabelled tests asserting customer-visible behavior the spec doesn't state: an unrecorded product decision, to add to the spec or drop. Tests of a function's documented contract are fine without an ID.
Quote the requirement for each finding. Under 300 words."

## Final mode: two sub-agents in parallel

**Requirements** brief: "Run the test suite. Then produce a table with one row per requirement: ID, status (met, partial, missing, out of scope), and evidence (test name, and `file:line` of the implementing code). Below it, list behavior in the code that no requirement asked for. Quote the requirement for each problem. Under 400 words plus the table."

**Standards** brief: "Review the code for: naming, separation of concerns, error handling and input validation at boundaries, and abstraction or generality the requirements don't need. Where the code calls an LLM, check that business rules are enforced in code rather than prompts, outputs are validated, and failures are retried, fall back, or escalate. Name Fowler code smells where they apply. Where the repo documents its own standards, they win. Label each finding a hard violation or a judgement call, and skip anything a linter enforces. Under 400 words."

Present them under `## Requirements` and `## Standards`, without merging or reranking. End with one line per section: finding count and the worst issue.
