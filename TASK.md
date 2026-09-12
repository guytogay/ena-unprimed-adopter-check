# TASK — adopt this product from cold, and tell us where it hurts

You are the fresh adopter. Nobody will help you. Everything you are allowed to know is in
`material/`.

## Do this

1. Read `material/` in whatever order the material itself suggests. Start where a new user would
   start.
2. Bring the thing up: create the working environment the product expects, using a temporary
   directory as the state location (never inside `material/`).
3. Use the reference tools that ship with it for the workflows the documents describe — at minimum:
   whatever the product calls its startup check, its change/state workflow, and its evidence or
   validation path.
4. Deliberately try **three things the documentation does not explicitly bless** (a plausible
   mistake a new user would make), and record whether the product caught it, ignored it, or
   behaved confusingly.

## Report format (keep it plain and factual)

```text
A. Time to first successful action
   - what you ran, in order, and where you had to stop and think

B. What the documents told you vs what you had to discover yourself
   - list each gap; quote the document line that was missing or misleading if you can

C. Raw evidence
   - the exact commands you ran, their exit codes, and the output (trimmed but unedited)

D. The three unblessed things you tried
   - for each: what you did, what you expected, what actually happened, and whether the product's
     response was useful

E. Confusion and defects
   - anything you could not do, anything that surprised you, and any place where the product
     claimed something it did not demonstrate

F. One paragraph: would you adopt this, and what is the single thing that would most improve it?
```

Constraints: do not modify `material/`; do not look for this project elsewhere on the internet or in
other repositories; do not invent capabilities you did not exercise.
