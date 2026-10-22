"""Channel-independent, deterministic management command grammar; no shell."""
import shlex

COMMANDS = ('help','status','brain','tasks','memory','model','usage','compact','export','stop')


def parse(text):
    if not text.startswith('/'):
        return None
    try:
        parts = shlex.split(text)
    except ValueError:
        return ('invalid', [])
    name = parts[0][1:].lower() if parts else 'invalid'
    name={'start':'help','cancel':'stop'}.get(name,name)
    if name == 'goal':
        return ('goal', parts[1:])
    if name in COMMANDS:
        return (name, parts[1:])
    return None if name=='skill' else ('unknown',parts[1:])
