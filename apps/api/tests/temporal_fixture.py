"""Platform-specific, pre-provisioned Temporal CLI for integration tests only."""
import os
from pathlib import Path
import sys
import asyncio
from datetime import timedelta


def cached_binary(root, platform=None):
    platform = sys.platform if platform is None else platform
    if platform not in ('win32', 'linux'):
        raise ValueError('unsupported_temporal_fixture_platform')
    runtime = Path(root).resolve() / '.runtime'
    name = 'temporal-sdk-python-1.33.0' + ('.exe' if platform == 'win32' else '')
    candidates = sorted(runtime.glob('p62-temporal-*/' + name))
    if not candidates:
        raise ValueError('temporal_fixture_cache_missing_run_explicit_bootstrap')
    path = candidates[-1]
    if path.is_symlink() or not path.resolve().is_relative_to(runtime.resolve()):
        raise ValueError('temporal_fixture_outside_runtime')
    with path.open('rb') as source:
        magic = source.read(4)
    if (platform == 'win32' and not magic.startswith(b'MZ')
            or platform == 'linux' and magic != b'\x7fELF'):
        raise ValueError('temporal_fixture_wrong_platform')
    if platform == 'linux' and not os.access(path, os.X_OK):
        raise ValueError('temporal_fixture_not_executable')
    return str(path)


async def namespace_ready(client, timeout=5):
    """Prepare the dev fixture's namespace, never retry a business command.

    A listening gRPC socket is not proof that Temporal's namespace is registered.
    Keep one bounded setup deadline and disable SDK retries on each read probe.
    Missing/failed readiness must fail the test, not skip the delivery assertion.
    """
    from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest
    from temporalio.service import RPCError, RPCStatusCode
    async def wait():
        while True:
            try:
                value=await client.workflow_service.describe_namespace(
                    DescribeNamespaceRequest(namespace=client.namespace),
                    retry=False,timeout=timedelta(seconds=min(timeout,1)))
                if value.namespace_info.state == 1:
                    return
            except RPCError as error:
                if error.status not in (RPCStatusCode.UNAVAILABLE,RPCStatusCode.DEADLINE_EXCEEDED,RPCStatusCode.NOT_FOUND):
                    raise
            await asyncio.sleep(.05)
    await asyncio.wait_for(wait(),timeout)
