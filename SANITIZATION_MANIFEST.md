# PAO sanitization manifest

Created: 2026-09-29
Final file verification: 2026-10-05 (Asia/Saigon)

Subsequent operational changes: the user authorized running and continuing this
project. Local runtime and an independent Git baseline were subsequently created.
The inventory/exclusions below describe the initial sanitized handoff; exclude
ignored runtime/data and `.git` again when producing another sanitized copy.

Final inventory: 339 files, approximately 2.66 MiB. Source revision:
`365fdfbf3dcf238e381de8b22cdf8be48ec26af3`.

SHA-256 comparison: 318 source files unchanged, 18 approved source files modified
in the target, `.env.example` recreated, one generated evidence file excluded,
and two reports added. Zero missing allowlisted source files.

## Allowlisted project content

- `apps/api/pao/`: backend application source.
- `apps/api/migrations/`: database schema migrations.
- `apps/api/tests/`: isolated backend tests.
- `apps/web/app/`, `apps/web/components/`, `apps/web/lib/`: frontend source.
- Frontend and backend manifests, lock files, and build configuration.
- `apps/worker/`: worker documentation/source currently tracked by the project.
- `packages/agent-config/`: agent definitions.
- `packages/contracts/`: OpenAPI and generated TypeScript contracts.
- `infra/`: Docker, PostgreSQL, Redis, Temporal, and SearXNG configuration.
- `scripts/`: setup, migration, verification, and local-development tools.
- `docs/`: architecture, plans, operational history, and development guidance.
- `evals/`: safe evaluation fixtures.
- Root README, license, credits, and safe configuration files.

## Denylisted content

- `.git/`
- `.env` and all real environment variants
- `.runtime/`
- `.venv/`
- `node_modules/`
- `.next/`, `.pao-next/`, and previous build directories
- `.pytest_cache/`, `__pycache__/`, `*.pyc`, and `*.egg-info/`
- `*.log`, `*.tsbuildinfo`, and generated `next-env.d.ts`
- Database files and dumps: `*.dump`, `*.bak`, `*.db`, `*.sqlite*`
- Private-key and certificate files: `*.pem`, `*.key`, `*.p12`, `*.pfx`
- Runtime uploads, exports, reports, screenshots, sessions, cookies, and process
  state
- Generated `docs/phase-1-evidence.json`

## Target-only transformations

1. `.env.example` was generated from the required variable names. Secret-bearing
   values are empty; local-only examples are clearly non-production.
2. Historical deploy scripts resolve Docker from `DOCKER_EXECUTABLE` or `PATH`
   instead of a specific Windows installation path.
3. Local paths in documentation use `<PAO_PROJECT_DIR>`, `<JAVIS_PROJECT_DIR>`,
   `<PAO_BACKUP_DIR>`, and `<DOCKER_RUNTIME_BACKUP_DIR>`.
4. `.gitignore` prevents common secrets, user data, runtime outputs, and database
   artifacts from being committed accidentally.

## Integrity and safety rules

- The source checkout remains authoritative and was not edited.
- The copy contains no inherited Git history.
- No production database or real user/business data was copied.
- No API key, bot token, OAuth token, password, cookie, or session was copied.
- No external project source was imported.
- Any future Git repository must be initialized only after reviewing this report
  and generating local secrets outside version control.
