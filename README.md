# Unprimed adopter check — a fresh information surface

This repository exists for exactly one purpose: to let an AI agent or human that has **no prior
context** about this product try to adopt it and report what actually happened.

## What is inside

- `material/` — a snapshot of a released product (documents, reference tools, examples, `VERSION`).
  Nothing here is modified, annotated, or explained by the people who built it.

That is the whole repository. There is **no** hidden answer sheet, oracle, test suite of the
authors, project history, or design discussion in this repository or in its Git history — the
history is a single orphan commit, by construction. Nothing is being withheld from you.

## What is deliberately not here

No explanation of what the product should be used for beyond what `material/` itself says. No
statement of known defects. No hints about the intended reading order beyond the documents' own
pointers. If something is unclear, that is a finding — write it down instead of guessing.

## Rules of the check

1. Work only from `material/`. Do not search the internet for the project, and do not look for
   other repositories by the same author.
2. You may run the tools. Use a **temporary directory** for any state you create; do not modify
   `material/` itself.
3. Report exactly what happened, including commands and raw output. Failures are the most valuable
   part of this exercise.
4. Do not try to be helpful by smoothing over confusion: if a document did not tell you something
   you needed, that is the finding.

See `TASK.md` for the concrete task and the report format.
