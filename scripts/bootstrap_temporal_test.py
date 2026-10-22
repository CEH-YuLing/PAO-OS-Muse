"""Explicit SDK-managed test CLI download; never production Temporal setup."""
import asyncio
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys
from pao.config import ROOT

sys.path.insert(0, str(ROOT / 'apps/api/tests'))
from temporal_fixture import cached_binary
from temporalio.testing import WorkflowEnvironment


async def main():
    assert version('temporalio') == '1.33.0', 'Review fixture cache when SDK lock changes'
    runtime = ROOT / '.runtime'; runtime.mkdir(exist_ok=True)
    directory = runtime / 'p62-temporal-bootstrap'; directory.mkdir(exist_ok=True)
    # SDK selects its compatible CLI version and the current OS/architecture.
    # This explicit provisioning step is the only place allowed to download.
    try:
        binary = cached_binary(ROOT)
    except ValueError as error:
        if str(error) != 'temporal_fixture_cache_missing_run_explicit_bootstrap':
            raise
        binary = None
    options = {'dev_server_existing_path': binary} if binary else {}
    async with await WorkflowEnvironment.start_local(ui=False,
            download_dest_dir=str(directory), **options) as env:
        await env.client.service_client.check_health()
    path = Path(cached_binary(ROOT))
    receipt = {'pass': True, 'platform': sys.platform, 'sdk': version('temporalio'),
        'binary_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'implicit_test_download': False, 'production_accepted': False}
    (runtime / 's6-temporal-binary.json').write_text(json.dumps(receipt), encoding='utf-8')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
