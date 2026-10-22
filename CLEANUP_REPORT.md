# PAO clean-copy report

Created: 2026-09-29
Final file verification: 2026-10-05 (Asia/Saigon)

Operational update on 2026-10-05: the user subsequently authorized a local run.
Dependencies, ignored `.env`, `.runtime`, model files, and isolated demo database
were created for that run. The source-only inventory below describes the clean
handoff before runtime setup, not the current operational directory. See
`docs/ACOS-LOCAL-RUN-2026-10-05.vi.md` for the running environment. Exclude all
runtime artifacts again before sharing or publishing a clean project copy.

## Result

**SAFE** within the file-copy checks described below, for development and backup.
This result does not establish production deployment readiness.

This directory is a sanitized copy of the PAO project. The original checkout was
treated as read-only. No production migration, advertising action, external
message, or deployment was performed.

## Copy summary

- Source allowlist: 338 Git-tracked files.
- Copied unchanged initially: 336 files.
- Excluded before copying: the original `.env.example` and generated
  `docs/phase-1-evidence.json`.
- Recreated: `.env.example`, using empty secret fields and harmless local
  placeholders.
- Added reports: `CLEANUP_REPORT.md` and `SANITIZATION_MANIFEST.md`.
- Git history was not copied and no new repository was initialized.
- Final inventory: 339 files, approximately 2.66 MiB including these reports.
- Source revision: `365fdfbf3dcf238e381de8b22cdf8be48ec26af3`.
- SHA-256 comparison on 2026-10-05: 318 copied files identical to source,
  18 approved target-only transformations, and zero missing allowlisted files.

## Removed or excluded

- Real environment files and credentials.
- Git history and remotes.
- Python and Node dependencies.
- Next.js output, caches, bytecode, and package metadata.
- Runtime models, application logs, screenshots, health evidence, and process
  state.
- Database dumps and other runtime/database data.
- Generated test evidence.

## Sanitization performed

- Rebuilt `.env.example` and added the missing `SEARXNG_SECRET` variable.
- Added `DOCKER_EXECUTABLE` as an optional environment override.
- Replaced a machine-specific Docker executable path in 14 historical deploy
  scripts with environment/PATH discovery.
- Replaced personal absolute paths in documentation with portable placeholders.
- Strengthened `.gitignore` for environment files, credentials, database files,
  dumps, uploads, exports, and reports.

## Verification

Functional checks below were performed on 2026-09-29. File inventory, exclusion,
secret-signature, path, and source-integrity checks were repeated on 2026-10-05.

- Strong secret-signature scan: zero findings.
- Real `.env`: absent.
- Private keys, certificate files, database dumps, logs, and runtime data: absent.
- Machine-specific absolute paths: zero confirmed findings.
- Git metadata: absent.
- Python syntax: 149 files parsed successfully.
- Backend migration/check on the isolated `pao_test` database: passed at current
  migration head.
- Backend regression: 182 passed.
- Runtime/SSE tests: 8 passed.
- Frontend workspace acceptance: all 12 PAO routes passed.
- Frontend production build: passed; 17 pages/routes generated or validated.
- Dependency install from `package-lock.json`: passed (358 packages).

Dependencies and generated verification artifacts were removed again after the
checks, leaving this directory source-only.

Backend tests used the existing Python dependency environment, with application
imports redirected to this clean copy. They verify the copied backend but do not
prove a fresh Python dependency installation. Database/Redis connection values
were held only in the test process; they were not written into this directory.
The test script redirected access to `pao_test` and Redis database 15.

Secret detection used file-name checks and heuristic signatures, not gitleaks or
trufflehog. No unresolved findings remain in those checks; this is not a guarantee
that every possible secret format has been detected. Frontend route acceptance
used the project's automated verification script; manual live login, Telegram,
and provider integrations were not re-tested for this copy.

## Required setup after copying

1. Copy `.env.example` to `.env` locally.
2. Generate new passwords, JWT secret, encryption key, and provider tokens.
3. Never reuse secrets from the original checkout.
4. Install Python and Node dependencies from the committed lock files.
5. Run migrations only against a newly created development/test database.
6. Run the documented test and build commands before deployment.

## Scope note

The scan covers files inside this clean directory. External Docker volumes,
databases, credentials stores, and files elsewhere on the machine are not part of
the copy and were not imported.
