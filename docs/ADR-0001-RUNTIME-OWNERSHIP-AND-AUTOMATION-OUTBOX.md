# ADR-0001: Runtime ownership and durable automation delivery

- Status: Accepted
- Date: 2026-09-29
- Scope: PAO Stage 2 / M0 stability

## Decision

PostgreSQL owns user-visible workflow state, audit history, idempotency keys and
the durable delivery queue. Temporal owns execution history, durable timers and
signal handling. Redis/ARQ owns short-lived dispatch work only; it is never the
sole copy of a business command.

Every start, approval, rejection or cancel request is committed to PostgreSQL
before it is sent to Temporal. `automation_outbox` is the boundary between the
two systems. The ARQ dispatcher leases pending commands, delivers them at least
once, retries with bounded backoff, and marks permanently exhausted starts or
signals as failed. A deterministic Temporal workflow ID and unique outbox
dedupe key make replay safe.

## Invariants

1. No external Temporal call occurs inside the transaction that accepts a user
   command.
2. A successful HTTP response means the command is durable, not necessarily
   already delivered.
3. `request_key` idempotency compares every execution-affecting input through a
   canonical SHA-256 fingerprint.
4. Approval and cancellation lock the workflow row and increment its version.
5. A terminal database projection cannot be overwritten by a late activity.
6. Waiting timers are interruptible by cancellation.
7. Dispatcher leases expire after two minutes so a stopped worker can recover.

## Failure behaviour

- Temporal unavailable: command remains pending and the UI shows `starting` or
  the latest accepted state.
- Worker dies after delivery: the lease expires; deterministic IDs/signals make
  retry safe.
- Five failed deliveries: outbox becomes `dead`; a non-terminal workflow is
  projected to `failed` with the public code `automation_dispatch_failed`.
- Concurrent decisions: the database row lock and version allow exactly one.

## Operational rule

Migration `0021` is additive. Before applying it to the local application DB,
`scripts/deploy_stage2.py` verifies idle short jobs, creates a custom-format
backup, restores it into a uniquely named isolated database, removes only that
temporary database, applies the migration, and confirms all pre-existing table
row counts are unchanged.
