# ADR-0002: Goal, Task dependency and execution attempts

- Status: Accepted
- Date: 2026-09-29
- Scope: PAO Stage 3 / M1

## Decision

`Goal` describes a business outcome and its success criteria. `Task` describes
one required or optional unit of work. `TaskAttempt` is one execution try and
may link to an existing PAO `Run`; it never copies chat or agent output.
`TaskDependency` is the authoritative dependency edge. The legacy JSON
`dependencies` field remains a compatibility cache for the current UI/API and
is updated in the same transaction.

Task state is explicit:

`draft → ready → running → waiting_approval → completed`

`blocked`, `failed`, and `cancelled` are controlled recovery/terminal branches.
AI/agent tasks enter `running` and `waiting_approval` only through an attempt.
Human tasks may be advanced manually by a workspace operator. Completion always
requires success criteria and evidence. A goal completes only when every
required task is completed and has evidence.

## Safety invariants

1. Dependency and parent tasks must be completed before a child attempt starts.
2. Dependency and parent graphs cannot contain self-reference or cycles.
3. Attempt request keys are idempotent and compare a canonical input fingerprint.
4. A cancelled task rejects late attempt results and cancels running attempts.
5. A failed/cancelled task may retry with a new attempt; existing attempts are immutable.
6. Goal, task, dependency, attempt, run and project references are workspace-scoped.
7. Telegram `/goals` and `/tasks` are read-only and expose only the linked workspace.

## Deferred work

Stage 3 records execution attempts but does not invent a general skill executor.
M2 will add versioned skill manifests and permitted business-tool adapters. Until
then, an attempt may link to an existing Run or be managed through the API; it
does not authorize Ads, email, calendar or external side effects.
