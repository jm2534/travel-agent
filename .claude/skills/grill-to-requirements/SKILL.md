---
name: grill-to-requirements
description: Turn notes on a customer problem into a testable REQUIREMENTS.md, grilling the user only on the gaps. Use before building against a problem statement.
disable-model-invocation: true
---

The user has already talked to the customer. They hold the answers; your job is to get those answers into a document that can drive tests.

## Process

1. **Read what the user has** (pasted notes, a file, a problem statement) and draft `REQUIREMENTS.md` from it right away, using the template below. Something on disk beats a perfect interview.
2. **Grill the gaps.** Call the Skill tool for "grilling" and follow it, with these adjustments:
   - The user is relaying a customer. Ask what the customer needs, not what the user would prefer.
   - Every MUST needs a concrete example and its failure behavior. Prioritise questions that supply those.
   - An unknown never blocks. If the user doesn't know, record an assumption with a one-line reason and move on.
   - Stop after about three rounds. Whatever is still open becomes an assumption.
3. **Update the file after every round,** not at the end.
4. **Read back the Summary** and ask the user to confirm it. That confirmation ends the session.

Be prepared to end the rounds early, and therefore surface high-signal questions sooner than later.
## Template

```markdown
# <Project>

## Summary
<3 to 5 sentences: who the users are, the problem, the core workflow, and what success looks like.>

## Terms
<Only terms that were ambiguous. **Term**: one-line definition. Code uses these names.>

## Requirements

### R1: <short name> (MUST)
<One sentence.>
- Handled by: code | LLM | human
- Examples: <given input> → <expected outcome>
- On failure: <what happens on missing or invalid input, or when a tool or the LLM fails>
- Status: todo

## Out of scope
- <thing>: <one-line reason>

## Assumptions
- A1: <assumption>, because <reason>. (unconfirmed)

## Decisions
- <decision>, because <reasoning>; tradeoff: <cost>
```

Notes on the template:

- Priorities are MUST or SHOULD. Anything else goes in Out of scope.
- Business rules are handled by code, never by an LLM prompt alone.
- Behavior that spans requirements (for example, "LLM output that fails validation is retried once, then escalated") is just another requirement.
- Status moves `todo` → `tested` → `done` during the build.
