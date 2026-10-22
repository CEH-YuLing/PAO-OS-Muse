# Candidate: model and reasoning effort per attempt

The four files overlay `packages/cli-runtime/pao_cli_runtime` only when building
with `prepare_p84_codex_docker.py --runtime-candidate`. They are not imported by
the serving backend. The installed library, device registry and profile pins
remain unchanged. Never copy these into the installed library without a new
tested image, idle/checkpoint gate and explicit runtime/profile migration.

Native Codex 0.157.1 passed network-none synthetic Responses tests for default,
tool-injection denial, High and Low. There was no login/auth mount or provider
inference. This is protocol evidence, not quota, entitlement, shared identity or
PAO chat acceptance. A personal login must not be relabeled as an organizational
identity.

The `backend/` candidate now connects installation selection, native engine pins,
per-agent overrides, the existing AccountingEngine and the existing CLI dispatch
ledger to per-invocation model/effort. `stage_installation_cli_candidate.py`
builds an isolated source tree using exact-count, fail-on-drift transformations.
It has no install switch and never modifies the serving package.

Candidate revision0076 exists ONLY in that staged tree. It keeps the native
attempt/workspace FK, immutable history and one unresolved attempt per source;
the source connection can belong to the installation custodian while the
attempt/usage/lease stays on the caller SME. SQL rechecks catalog/effort, caller
and custodian membership, resource revision, source pins and active lease.
Downgrade refuses populated shared-dispatch history.

`shared.admit()` still rejects all real shared CLI admission. Only tests replace
that provider-identity boundary; they do not bypass PAO auth, ACL, privacy,
native accounting or dispatch checks. Captured metadata and connected personal
profiles do not enable sharing. The normal resource API also calls that gate.
The installed schema stays0075; the candidate is not a live shared CLI adapter.

Verification uses a disposable labeled PostgreSQL container, a restored private
checkpoint clone and synthetic transports. The image fixture separately checks
two synthetic model IDs and High/Low against the actual pinned Codex binary,
network disabled, without login/auth mounts or quota consumption. See
`scripts/check_shared_cli_candidate.py` and
`scripts/check_installation_codex_candidate.py --multimodel --image-receipt ...`.

Reproducible build: use the documented pinned cached official Codex archive and
the existing image builder. Production data, OAuth caches and Windows home must
never be included in the context.
