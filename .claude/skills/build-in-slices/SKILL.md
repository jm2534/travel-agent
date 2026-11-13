---
name: build-in-slices
description: Build from REQUIREMENTS.md as a runnable end-to-end skeleton first, then one requirement at a time (stubs, tests, test review, implementation), so something always runs and no code outpaces the user's understanding.
disable-model-invocation: true
---

A slice AKA tracer-bullet is a vertical piece of functionality, typically an embodied user story or application flow. Two goals exist, in this order: at least once slice runs end to end as soon as possible, and the user has understood core routines and abstractions before the next slice starts.

Needs a `REQUIREMENTS.md` (or another spec the user points to). If there is none, tell the user to run `/grill-to-requirements` first.

## Step 0: Skeleton

Build the whole main flow with stubs: domain types, public functions with signatures and contract docstrings, and the entry point (CLI, API, or UI) wired through all of them. Stubs can raise NotImplemented initially, with the goal of getting at least one flow to run shortly thereafter. They can also return sensible defaults, but use this judiciously, since it can quickly become hard to tell stubbed code from intended implementation.

Add one smoke test that runs the flow end to end.

The skeleton is the design. Keep it small enough to read in full, walk the user through it (modules, flow, data types), and get their sign-off before any slice.

Order the slices: MUST requirements, following the main flow.

## Each slice

A slice is one requirement, or a few that land in the same function.

1. **Stubs.** Add or adjust the types and signatures the slice needs. Show the user the diff; they own this layer.
2. **Tests,** at the public interface. Requirement tests come first and open their docstring with the requirement ID: `"""R3: overdue claims are escalated to a human."""`. Add contract tests (validation, parsing, boundaries of a function's documented contract) only where the contract has a real edge; they carry no ID.
3. **Review.** Call the Skill tool for "review-against-spec" in tests mode, scoped to this slice's requirements. Address its findings.
4. **Red.** Run the new tests against the stubs. A test that passes against a hardcoded stub isn't testing the requirement; strengthen it. Mark the requirement `tested`.
5. **Implement** the least code that makes the tests pass. Show the user the diff and wait until they say they've read it. If it was too long to read in a couple of minutes, split the next slice smaller.
6. **Done.** Tests green, smoke test green, mark the requirement `done`.

## When the code disagrees with the doc

If implementation reveals a missing or wrong requirement, stop. Update `REQUIREMENTS.md` (with a line under Decisions), then the test, then the code. Never the code first.

## Testing

- Mock only system boundaries (external APIs, time, the LLM), never your own modules.
- Expected values are literals or the examples from `REQUIREMENTS.md`, never recomputed the way the code computes them.
- Tests may not need to call a real model. Consider replacing with a fake that returns canned outputs, including malformed ones, so validation and fallback paths are tested deterministically. With Pydantic AI, use `TestModel` or `FunctionModel` via `Agent.override`, and set `models.ALLOW_MODEL_REQUESTS = False` in tests. Exercise the real model by hand a few times as a smoke check.

## Finishing

When the MUSTs are done, or time is short, stop starting slices: a working subset with a clear Out of scope beats a half-built slice. Then call the Skill tool for "review-against-spec" in final mode.
