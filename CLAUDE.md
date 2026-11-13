# Build session conventions

A two-hour live build of an LLM application, reviewed in detail afterwards. Optimize for code a senior engineer can read and that I can defend, not for feature count. We have an Anthropic key in the shell at our disposal.

## Workflow

- Work in small steps: one behavior per change, with its test, then a commit. Show me the plan before writing more than about 50 lines.
- Keep `REQUIREMENTS.md` current: each requirement with its status (todo, done, tested, cut) and where it lives in the code. Re-read it before calling anything finished.
- Record decisions in `DECISIONS.md` as one line each: "X over Y because Z".
- Run `uv run pytest -q` and `uv run ruff check` after every change. Never leave tests failing.
- Ask before adding a dependency.
- Never modify the customer's data unless instructed

## Design rules

- Business rules are deterministic Python with unit tests. The model shouldn't decide policy.
- The model handles the conversation and chooses tools. Tools validate their inputs and return typed results or typed errors, never raw exceptions.
- Anything that writes to the customer's system goes through one module that handles retries,
  idempotency and reconciliation.
- Customer data is data. Free-text fields never reach the model as instructions.
- Pydantic models for every boundary: parsed input data, tool arguments, tool results.
- Python 3.14, type hints throughout, standard library first.

## Style

- Clear names over comments; brief comments only where the logic is core to the program or non-obvious, no more than a line or two
- Google-style docstrings on public APIs; private methods also benefit from at least a description of intent in their docstring
- No section-divider comments
- No clever one-liners in business rules
