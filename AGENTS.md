# PAO OS Muse — instructions for this independent checkout

## Read first, in this order

1. `START-HERE.vi.md`
2. `MUSE.md`
3. `handoff/PROJECT-STATE.vi.md`
4. `docs/PAO-MASTER-GAP-AND-ROADMAP.vi.md`
5. Relevant current acceptance report; old receipts are historical evidence only.

## Scope overrides copied historical operator instructions

- Work ONLY in `G:\PAO OS Muse`. `F:\PAO-ACOS` and `F:\PAO-BOS Backup 001` are
  protected references, NOT your checkout or writable runtime.
- Original AGENTS is preserved at `handoff/AGENTS-SOURCE-HISTORY.md` as history.
  Its references to working in F:, primary DB15432/Redis16379, and source process
  commands do NOT authorize running them here. This file takes precedence for scope.
- Start/stop ONLY with `Start-Muse.ps1` / `Stop-Muse.ps1`. Do not use copied
  start_acos_local, start_local, install_*, backup_* or check_* operator helpers
  until each path, DB, port, container and protected root has been adapted/reviewed.
- Own DB25432/pao_muse_local, Redis26379/0, test DB25432/pao_test and Redis26379/15.
  Never connect to source DB15432, Redis16379, API8100 or Web3200 for mutations/tests.
- This is a clean install: no source users, SME data, memory, credentials, sessions,
  CLI logins, .env, runtime receipts or Git history have been imported.
- Native Muse used as an Orca coding agent is distinct from the Muse provider
  inside PAO. PAO has a separate `.runtime/muse-profile`; login officially in Settings.
  Never copy source profile tokens, hooks or account credentials to make it connect.
- Preserve enterprise/Brain privacy, tool approval, usage accounting, immutable
  pins, replay/idempotency, loop/timeout and cancellation. No public deployment,
  provider spending, Ads write or messages unless separately authorized.
- Customer UI Vietnamese; preserve provider IDs/enums/contracts verbatim.
- Implement the entire approved phase sequentially and test; concise updates,
  no approval request after each tiny step. Stop only for a genuine authority gap.
- Do not mark mocks/catalog/saved configuration as live acceptance. Preserve
  original failures. Do not silently rewrite historic receipts or restore data to pass.
- New runs use provider-managed tokens; model limits and byte guards remain.
- Do not auto-update pinned Muse binary/trace codec, enable shared Codex or turn
  Antigravity/Claude catalog into claimed working inference without implementation.
- No automatic push/merge/public links. This repository has no source remote.
- Install/launcher additions belong only to this fork; do not port back into F: automatically.
