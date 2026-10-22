"""Restrictive harness metadata, NOT discovery, entitlement or an invented model.

The requested model id remains unchanged. Provider rejection stays a failure;
this local catalog is used solely to omit file/shell/parallel native tools.
"""
import re
from .contracts import CliFailure


def text_catalog(model,reasoning_effort=None):
    if not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/+-]{0,119}', model):
        raise CliFailure('cli_contract_invalid')
    if reasoning_effort is not None and reasoning_effort not in ('none','minimal','low','medium','high','xhigh','max'):
        raise CliFailure('cli_contract_invalid')
    return {'models': [{
        'slug': model, 'display_name': model, 'description': None,
        'base_instructions': 'You are PAO\'s text inference component. Follow the supplied conversation. '
                             'Return text or the requested JSON only. You have no external tools. '
                             'Do not claim that you executed any external action.',
        'default_reasoning_level': reasoning_effort or 'medium',
        'supported_reasoning_levels': ([{'effort':reasoning_effort,'description':'PAO pinned effort'}] if reasoning_effort else []),
        'shell_type': 'shell_command', 'visibility': 'list', 'supported_in_api': True,
        'priority': 0, 'upgrade': None, 'support_verbosity': False, 'default_verbosity': None,
        'apply_patch_tool_type': None, 'truncation_policy': {'mode': 'bytes', 'limit': 10000},
        'supports_image_detail_original': False, 'context_window': 32768,
        'max_context_window': 32768, 'experimental_supported_tools': []}]}
