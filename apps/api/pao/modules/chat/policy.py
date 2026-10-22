"""Explicit privacy/budget preference, frozen on run and rechecked on each call."""
from ...config import settings
from ..engines.contract import EngineFailure


def default_policy():
    return {'version':'p3-policy-v1','token_mode':'provider' if settings().provider_managed_tokens else 'bounded','privacy':'local_only','context_tokens':settings().context_tokens,
            'max_bytes':16384,'max_output_tokens':settings().output_tokens,'max_run_tokens':32768,
            'max_calls':8,'require_reported_usage':False,'pricing':None,'cloud_references':False}


def policy_for(chat):
    return {**default_policy(), **((chat.chat_profile or {}).get('policy') or {})}


def enforce(provider, pinned, current):
    if provider not in ('ollama','knowledge') and (pinned.get('privacy') != 'cloud_allowed' or current.get('privacy') != 'cloud_allowed'):
        raise EngineFailure('cloud_egress_denied')
    if pinned.get('version') != 'p3-policy-v1':
        raise EngineFailure('chat_policy_incompatible')


def run_policy(run):
    return (run.engine_snapshot or {}).get('chat_policy') or default_policy()
