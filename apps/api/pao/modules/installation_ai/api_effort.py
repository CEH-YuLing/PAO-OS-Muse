"""Reviewed API wire capabilities; annotate discovered exact IDs, never invent access.

Sources/date/limits: docs/GD01-AI-RESOURCES-2026-10-21.vi.md.
Unknown IDs keep the legacy request unchanged unless an explicit effort is requested.
"""
VERSION = 'api-effort-2026-10-21-v1'
_BASE = ('low', 'medium', 'high')
_FIVE = (*_BASE, 'xhigh', 'max')
_PROFILES = {
    'anthropic': {
        'claude-opus-4-5': (_BASE, 'high'),
        'claude-opus-4-6': ((*_BASE, 'max'), 'high'),
        'claude-sonnet-4-6': ((*_BASE, 'max'), 'high'),
        'claude-opus-4-7': (_FIVE, 'high'),
        'claude-opus-4-8': (_FIVE, 'high'),
        'claude-opus-5': (_FIVE, 'high'),
        'claude-opus-5-5': (_FIVE, 'medium'),
        'claude-sonnet-5': (_FIVE, 'high'),
        'claude-sonnet-5-5': (_FIVE, 'high'),
        'claude-haiku-5-5': (_FIVE, 'medium'),
    },
    # This adapter uses v1beta generateContent, not the newer Interactions API.
    # Budget-based 2.5 models, image, audio and live models are not annotated.
    'gemini': {
        'gemini-4-argon': (_BASE, 'medium'),
        'gemini-3.8-flash': (_BASE, 'medium'),
        'gemini-3.6-flash': (('minimal', *_BASE), 'medium'),
        'gemini-3.5-flash-lite': (('minimal', *_BASE), 'minimal'),
        'gemini-3.1-pro-preview': (_BASE, 'high'),
        'gemini-3-flash-preview': (('minimal', *_BASE), 'high'),
        'gemini-3-pro-preview': (('low', 'high'), 'high'),
    },
}


def metadata(provider, model):
    profile = _PROFILES.get(provider, {}).get(model) if isinstance(model, str) else None
    return {'reasoning_efforts': list(profile[0]) if profile else [],
            'default_effort': profile[1] if profile else None}


def validate(provider, model, effort):
    if not isinstance(model, str):
        raise ValueError('ai_model_invalid')
    if effort is not None and (not isinstance(effort, str)
            or effort not in metadata(provider, model)['reasoning_efforts']):
        raise ValueError('ai_effort_not_supported')


def payload(provider, model, effort, value):
    validate(provider, model, effort)
    if effort is None:
        return value
    if any(key in value for key in ('tools', 'tool_choice', 'thinking', 'output_config')):
        raise ValueError('ai_effort_text_only_required')
    if provider == 'anthropic':
        value.pop('temperature', None)
        value['output_config'] = {'effort': effort}
    elif provider == 'gemini':
        config = value['generationConfig']
        if 'thinkingConfig' in config:
            raise ValueError('ai_effort_parameter_conflict')
        config['thinkingConfig'] = {'thinkingLevel': effort}
    else:
        raise ValueError('ai_effort_not_supported')
    return value
