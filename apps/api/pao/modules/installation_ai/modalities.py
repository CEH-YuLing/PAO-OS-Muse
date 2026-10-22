"""Conservative model metadata, not entitlement, tool authority or live proof.

Provider-declared output modalities take precedence. Known dedicated endpoints
are excluded from PAO's text adapter; unknown IDs remain explicitly unverified.
Never write inferred metadata back into immutable historical catalog journals.
"""
import re

VERSION = 'pao-model-modalities-v1'
OUTPUTS = {'text', 'image', 'audio', 'video', 'embedding', 'embeddings', 'moderation',
           'rerank', 'decisions', 'speech', 'transcription'}


def outputs(value):
    if (not isinstance(value, list) or not 1 <= len(value) <= len(OUTPUTS)
            or any(not isinstance(v, str) or v not in OUTPUTS for v in value)
            or len(set(value)) != len(value)):
        raise ValueError('ai_modalities_invalid')
    return sorted(value)


def metadata(provider, model, row=None):
    declared = (row or {}).get('provider_output_modalities')
    source = 'unknown'
    values = []
    if declared is not None:
        values = outputs(declared)
        source = 'provider_catalog'
    elif provider == 'codex_cli':
        values, source = ['text'], 'native_text_adapter'
    else:
        name = model.lower().rsplit('/', 1)[-1]
        # Dedicated image/audio/embedding/live endpoints must never masquerade
        # as chat just because /models returns their IDs.
        rules = (
            ('embedding', r'(?:^|[-_])embed(?:ding|dings)?(?:[-_]|$)'),
            ('moderation', r'(?:^|[-_])moderation(?:[-_]|$)'),
            ('video', r'^(?:sora|veo)(?:[-_.]|$)'),
            ('image', r'^(?:dall-e|gpt-image|chatgpt-image|imagen)(?:[-_.]|$)|(?:^|[-_])image(?:[-_]|$)'),
            ('audio', r'^(?:tts|whisper|lyria)(?:[-_.]|$)|(?:^|[-_])(?:audio|realtime|live|tts|transcribe|translate)(?:[-_]|$)'),
        )
        for kind, pattern in rules:
            if re.search(pattern, name):
                values, source = [kind], 'reviewed_endpoint_family'
                break
        if not values and provider == 'openai' and re.match(r'^(?:babbage|davinci|.*-instruct)(?:[-_.]|$)', name):
            source = 'dedicated_completion_endpoint'
        elif not values and ((provider == 'openai' and re.match(r'^(?:gpt-|chat-latest$|o[134](?:[-.]|$))', name))
                or (provider == 'anthropic' and name.startswith('claude-'))
                or (provider == 'gemini' and name.startswith('gemini-'))):
            values, source = ['text'], 'reviewed_text_family'
    supported = 'text' in values if source != 'unknown' else None
    return {'version': VERSION, 'output_modalities': values, 'evidence': source,
            'chat_supported': supported,
            'adapter': {'input_modalities': ['text'], 'output_modalities': ['text'],
                        'image_generation': False, 'audio_generation': False,
                        'native_tools': False},
            'availability': 'catalog_only'}


def detail(provider, row):
    return {**row, 'model_capabilities': metadata(provider, row['model'], row)}


def require_chat(provider, model, row=None):
    if metadata(provider, model, row)['chat_supported'] is False:
        raise ValueError('ai_model_not_chat_compatible')
