# Process

- Work through tasks in order.
- Commit regularly, even if a task is not yet complete.
- Read the acceptance criteria before starting and before marking complete.
- When marking a task complete, include a timestamp.

## Team roles

For tasks worth the overhead, work can be split across three subagents
(`.claude/agents/`) instead of one session doing everything:

- **product-manager** — grooms the next open task: sharpens acceptance
  criteria, catches missing edge cases, splits out-of-scope ideas into new
  backlog items. Never writes code.
- **software-engineer** — implements the groomed task: code, migrations,
  tests, regular commits. Never marks a task complete.
- **qa-engineer** — verifies the implementation against the task's
  criteria and the full test suite, and reports `PASS` or `FAIL`. Never
  fixes anything itself.

The driving session acts as orchestrator: dispatch product-manager, then
software-engineer, then qa-engineer, in that order. On `FAIL`, dispatch
software-engineer again with QA's findings and re-run qa-engineer. On
`PASS`, mark the task complete in `_docs/tasks.md` with a timestamp
(the orchestrator does this — not qa-engineer) and move to the next task.
