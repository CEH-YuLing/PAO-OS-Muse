"""Reviewed text-only OpenAI Chat Completions effort contract, not discovery.

IDs still come from authenticated /models. This exact-ID table only annotates
returned IDs. Never infer capabilities for prefixes, snapshots or fine-tunes.
Sources/review date: docs/OPENAI-EFFORT-2026-10-20.vi.md. No token, endpoint,
service tier, reasoning mode, tool permission or fallback is configured here.
"""
VERSION = 'openai-chat-effort-2026-10-20-v1'
_LEVELS = ('low', 'medium', 'high', 'xhigh', 'max')
_PROFILES = {
    'gpt-6-astra': (_LEVELS, None),
    'gpt-6.1-sol': (_LEVELS, 'medium'),
    'gpt-6-luna': (('none', *_LEVELS), 'medium'),
}


def metadata(model):
    profile = _PROFILES.get(model) if isinstance(model, str) else None
    return {'reasoning_efforts': list(profile[0]) if profile else [],
            'default_effort': profile[1] if profile else None}


def validate(model, effort):
    if not isinstance(model, str):
        raise ValueError('ai_model_invalid')
    if effort is not None and (not isinstance(effort, str) or effort not in metadata(model)['reasoning_efforts']):
        raise ValueError('ai_effort_not_supported')


def payload(model, effort, value):
    """Mutate only the reviewed parameter fields; never increase token bounds."""
    validate(model, effort)
    if model not in _PROFILES:
        return value  # Legacy/unknown model with no explicit effort is unchanged.
    if any(key in value for key in ('tools', 'functions', 'tool_choice', 'reasoning')):
        raise ValueError('ai_effort_text_only_required')
    # The native PAO runner owns tools; this adapter sends text/JSON only.
    for key in ('temperature', 'top_p', 'top_logprobs', 'logprobs'):
        value.pop(key, None)
    if 'max_tokens' in value:
        if 'max_completion_tokens' in value:
            raise ValueError('ai_effort_token_limit_conflict')
        value['max_completion_tokens'] = value.pop('max_tokens')
    if effort is not None:
        value['reasoning_effort'] = effort
    return value
