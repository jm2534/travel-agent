Assignment
Take home Assignment - Trip Idea Agent

Role: Applied AI Engineer
Estimated time: ~2 hours
Stack: Your choice; we use Next.js + TypeScript, and you'll have the smoothest review if you stay close to that, but pick what lets you do your best work in 2 hours.
Coding assistant: Required — Claude Code, Cursor, Codex CLI, Aider, or similar

Why we're asking you to do this

We want to see how you work with AI tools, not just what you build with them. In 2 hours you can't ship a polished agent, and we're not asking you to. We're asking you to make a small, real thing. And to show us how you and your coding assistant got there together.

How you collaborate with a coding agent is a first-class engineering skill at Atlas. We use these tools every day, and we'd rather see how you actually work with them than pretend you don't. The deliverable here is your process as much as the artifact.

LLM Provider and Credentials

We won't provide an API key; provider choice and integration are part of the exercise. Use any LLM you want. Make the provider/model configurable, keep secrets out of the repo, and document setup in your README so we can see which provider/model you used, what env vars are required, and what happens when credentials are missing or invalid.

You don't need a paid key. Most major providers have free tiers or trial credits. OpenRouter has free models (https://openrouter.ai/collections/free-models) but they vary in quality and tool-call reliability. If you go with a flaky free model, that shows up in how robust your app is; document the trade-off.


The Build Task

Build a small "Trip Idea" agent; a single-turn function that takes a natural-language travel request and returns a structured suggestion.

The agent should be able to reason about destinations, budget, flights, and accommodation. How you split this into tools is up to you; at minimum 3, more if it makes sense. Mocks are fine (hardcoded responses for a couple of inputs is plenty).


Example inputs:

    "Relaxing beach week in February under $2000 for two, leaving from JFK. Want a nice hotel."

    "Long weekend in Europe, flying from SFO. Walkable city, great food, boutique hotel under $300/night."

    "Family of 4 (kids 6 and 9), warm weather over spring break, ~$5k all-in. Need a place with a pool."

    "Anniversary trip in May, somewhere romantic and not too touristy. We hated Santorini. Budget flexible but flag if it's blowing past $4k."

    "I'll be in Lisbon Oct 10–13 for a wedding. Want to tack on 5 days somewhere nearby. Already have the flight to Lisbon."

    "Tokyo for 8 days in November, two adults, $6k budget excluding flights. We've been once before."

    "Cheap."

Must have

    A typed, structured response (destinations, reasoning, rough budget, caveats)

    Graceful handling when critical info is missing: ask, flag, or degrade rather than hallucinate

    A small eval harness: 5+ cases, scored on at least 2 dimensions, with a summary report

    A README.md that gets us running in under 5 minutes

Explicitly out of scope

    Real travel data or any third-party travel APIs; keep the mocks simple

    A UI. A CLI or a single function entry point is plenty.

    Persistence, sessions, or multi-turn conversation. One request → one response.

    Authentication, accounts, or any notion of users.

    Production concerns: deployment, caching, observability infrastructure, retries.

    A "perfect" agent. Two hours is short; cutting scope intelligently is part of the exercise.

Your call (we want to see how you decide)

    How to slice the tools across destinations, budget, flights, and accommodation. One tool per concern, combined, or some other split — defend it.

    How the agent orchestrates its tool calls. A single LLM-as-planner pass, a ReAct loop, a structured workflow — your call, but be ready to explain.

    How you handle missing or ambiguous information. Ask the user, infer with caveats, refuse to answer — different choices serve different products.

    What dimensions your eval scores on, and how. Deterministic checks, schema validation, LLM-as-judge — pick what gives you real signal in 2 hours.

    Where you stop. Two hours is the budget; cutting scope intelligently is part of the exercise.

That's it for functionality. Don't over-build. We've sized this so a focused 2 hours is enough — but if you go over, just tell us where the time went.


The Process Deliverable

This is the part most candidates underweight, and it's the part we read most carefully. The goal is to give us a window into how you think with these tools — not surveillance, not a coverage exercise.


1. Full session transcript(s)

Every prompt you sent and every response you got back, in order. Most assistants can export this:

    Claude Code: /export or share the .jsonl from the session

    Cursor: export chat

    Codex CLI: commit the raw session file from ~/.codex/sessions/, or use jinghan23/codex-export for markdown

If you used multiple sessions or tools, include all of them, labeled. If you used spec-driven development, include the spec files too. If your tool doesn't support export, say so and skip it — we'd rather have an honest gap than a reconstructed one.


2. Annotated highlights — 5 to 10 prompts in PROCESS.md

Pick the prompts where you made a real decision: scoping the schema, choosing how to split the tools, debugging a weird extraction, deciding what to cut. For each, two or three lines on:

    What you were trying to do

    What the tool gave you back (briefly)

    What you kept, changed, or threw away — and why

This is the highest-signal part of the submission. Treat it like a code review comment, not a chore.


3. A short reflection (same PROCESS.md)

    Your overall approach. Did you plan first, or dive in? Did you let the agent drive, or stay in tight control? Why?

    What you reviewed by hand vs. trusted. Where did you read every line? Where did you skim? Where (honestly) did you ship something you didn't fully verify?

    What you'd do differently next time.

    If this had to run at scale. What would you change about model choice, prompting, schema, or eval strategy if this were serving 10k requests an hour? Don't implement it — just sketch your thinking.


4. The repo itself

A GitHub repo with the working code, README, and eval output. Runnable in under 2 minutes from a clean clone.
What we're evaluating

We care about your judgment in the loop, not your typing speed. Roughly in the order it shapes our impression:

    The annotated prompts. Clarity of thought, willingness to push back on the model, good taste about when to write something yourself rather than prompting for it.

    What you cut and why. Two hours is short on purpose. We want to see deliberate scope decisions, not panicked omissions.

    Eval design. What did you choose to measure, and why? Are the cases meaningful, or just easy?

    Code structure and naming. Could a teammate extend this without asking you?

    Prompt and schema design in the agent. Is the output contract explicit? Are prompts clean and reproducible?

    README and decision log. Setup that works, decisions explained, known gaps acknowledged.


What we're evaluating

We care about your judgment in the loop, not your typing speed. Roughly in the order it shapes our impression:

    The annotated prompts. Clarity of thought, willingness to push back on the model, good taste about when to write vs. prompt. Did you catch the model over-engineering? Did you redirect when it drifted? This is the highest-signal part of the submission.

    Eval design. What did you measure, and why? Are the cases meaningful, or just easy? We're looking for inputs that stress the hard parts; missing budget, contradictory constraints, underspecified requests. We'll check whether your scoring dimensions give real signal or just confirm the output exists.

    Tool design and orchestration. How did you slice the problem into tools, and can you defend that boundary? Does the agent actually use what the tools return? We'll look for clean separation between tool concerns, sensible behavior when a tool returns nothing useful, and an orchestration strategy you can explain.

    Prompt and schema design. Is the output contract explicit and stable? Are prompts clean and readable by a teammate? We're looking for taste; not exhaustive instructions, but prompts that communicate intent clearly and schemas that reflect the real shape of the problem.

    Code structure and naming. Could a teammate extend this without asking you? Where do the tools live relative to the agent? Are the names honest about what things do?

    Handling missing and ambiguous input. "Cheap." is a valid input. So is a request with no destination, no dates, and no budget. We'll look at whether your agent asks, infers with caveats, or fails gracefully; and whether that behavior is consistent, not scattered.

    README and decision log. Setup steps that work. Decisions explained. Known gaps acknowledged honestly.

    What you cut and why. Two hours is short on purpose. We want deliberate scope decisions, not panicked omissions. A short list of known gaps and how you'd close them is a strong positive signal.

    Provider choice and configuration. We are not evaluating which paid model you have access to. We are evaluating whether you made a reasonable provider choice, kept credentials out of the repo, documented setup cleanly, and handled model/API failure modes thoughtfully.


A few things we're explicitly not looking for:

    A specific framework or model choice — pick what lets you do your best work.

    "Pure" code with no AI involvement. This isn't that test.

    A polished repo paired with a thin transcript. The transcript is the point.

Be honest about what you didn't fully understand or verify. If you copy-pasted a chunk of code from a prompt without reading it carefully, say so — we'd rather talk about it than have you pretend.


Questions

If anything is unclear, send us a note before you start rather than guessing for an hour. We'd rather answer a question than read a clarification in your README.


Submission

Reply with:

    Repo link

    Transcript file(s)

    PROCESS.md (in the repo is fine)

    Approximate time spent — if you went over 2 hours, tell us where the time went; we'd rather know

Good luck — we're looking forward to seeing what you build.
