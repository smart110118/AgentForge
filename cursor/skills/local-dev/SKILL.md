---
name: local-dev
description: Delegate implementation tasks to the local coding agent.
---

# Local Development Workflow

## Principle

Cursor is the planner and reviewer.

The local coding agent is the implementation executor.

## Workflow

1. Understand the user's request.
2. Inspect the repository.
3. Break the task into atomic implementation units.
4. Define acceptance criteria.
5. Delegate implementation to `local-coder` (MCP `local_agent_execute`).
6. Wait for the result (or poll `local_agent_status` / `local_agent_result`).
7. Review changed files and test results. Trust test **exit code**, not model prose.
8. If failed, delegate a correction task via `local_agent_retry`.
9. Repeat until acceptance criteria pass.
10. Perform final review.

## Delegation

Use MCP tool `local_agent_execute`.

Provide:

- task / objective
- repository / workspace
- files (allow globs)
- constraints
- acceptance criteria
- test command

## Completion

A task is complete only when:

- implementation exists
- tests pass (exit code 0)
- git diff is acceptable
- no unrelated files changed
- acceptance criteria are satisfied
