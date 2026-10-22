// Compatibility entry point retained for older local commands.
// The original single-page browser scenario targeted controls that moved to
// independent PAO routes. Runtime/SSE behavior is covered by `test:runtime`,
// while the current end-to-end browser contract lives in this verifier.
require('./verify_workspace_ui.cjs');
