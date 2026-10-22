"""Bounded response check against the current request credential only.

No secret registry, storage, logging or arbitrary decoding. Reject, never
partially redact/accept. Checks decoded JSON keys and values (including fields
the caller would discard), plus common single-layer representations. This is
defence in depth, not a guarantee against arbitrary exfiltration encodings.
"""
import base64
import json
from urllib.parse import quote

MAX_DEPTH = 32
MAX_NODES = 100000


class CredentialPayloadError(ValueError):
    """Stable code only; never include the credential or response text."""


def require_clean_payload(value, credential=None):
    forms = set()
    if credential:
        forms = {credential, json.dumps(credential, ensure_ascii=True)[1:-1],
                 json.dumps(credential, ensure_ascii=False)[1:-1],
                 quote(credential, safe='')}
        raw = credential.encode('utf-8')
        forms.update((base64.b64encode(raw).decode(),
                      base64.urlsafe_b64encode(raw).decode()))
        forms.discard('')
    # Iterator frames avoid allocating a second tree or recursing on input.
    stack = [(iter((value,)), 0)]
    nodes = 0
    while stack:
        items, depth = stack[-1]
        try:
            item = next(items)
        except StopIteration:
            stack.pop()
            continue
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise CredentialPayloadError('payload_complexity_limit')
        if isinstance(item, str):
            if any(form in item for form in forms):
                raise CredentialPayloadError('payload_credential_reflected')
        elif isinstance(item, dict):
            from itertools import chain
            stack.append((iter(chain(item.keys(), item.values())), depth + 1))
        elif isinstance(item, (list, tuple)):
            stack.append((iter(item), depth + 1))
