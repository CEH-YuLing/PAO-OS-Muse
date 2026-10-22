"""Per-invocation transport policy; never bypass identity, tools or loop guards."""
from contextvars import ContextVar

PROVIDER_MANAGED = ContextVar('pao_provider_managed_tokens', default=False)
TRANSPORT_BYTES = 8 * 1024 * 1024  # Memory/transport safety, not a model token cap.


def automatic(policy):
    # Historical Run snapshots without this field retain their original budgets.
    return policy.get('token_mode') == 'provider'
