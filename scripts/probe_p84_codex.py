"""Local version/help only. Never executes codex exec, login or sandbox commands."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from pao_cli_runtime.codex_probe import probe
from pao_cli_runtime import CliFailure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    folder = ROOT / '.runtime' / ('p84-codex-probe-' + uuid4().hex)
    folder.mkdir()
    diagnostics = {}
    help_outputs = {}
    try:
        pin, outputs = probe(args.binary, folder, diagnostics, help_outputs)
    except CliFailure as error:
        failure = {'pass': False, 'code': error.code, 'operations': diagnostics, 'inference_calls': 0}
        with (folder / 'probe-failed.json').open('x', encoding='utf-8') as target:
            json.dump(failure, target, indent=2)
        for name, value in help_outputs.items():
            with (folder / (name + '.txt')).open('x', encoding='utf-8') as target:
                target.write(value)
        print(folder)
        print(json.dumps(failure))
        raise SystemExit(1) from None
    required = {'--json', '--ephemeral', '--ignore-user-config', '--skip-git-repo-check', '--sandbox', '--ask-for-approval'}
    record = {'utc': datetime.now(timezone.utc).isoformat(), 'binary': {**asdict(pin), 'flags': sorted(pin.flags)},
              'required_flags': sorted(required), 'missing_flags': sorted(required - pin.flags),
              'version_help_only': True, 'existing_auth_store_read': False, 'inference_calls': 0,
              'sandbox_executed': False, 'live_accepted': False, 'operations': diagnostics}
    for name, value in outputs.items():
        with (folder / (name + '.txt')).open('x', encoding='utf-8') as target:
            target.write(value)
    with (folder / 'probe.json').open('x', encoding='utf-8') as target:
        json.dump(record, target, ensure_ascii=False, indent=2)
    print(folder)
    print(json.dumps(record))


if __name__ == '__main__':
    main()
