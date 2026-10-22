"""Only synthetic child used by the offline transport tests. Never imports PAO."""
import json
import os
import subprocess
import sys
import time


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main():
    # The parent attaches process containment BEFORE sending this first line.
    value = json.loads(sys.stdin.buffer.readline(1048577))
    mode = value['fixture']
    if mode == 'echo':
        emit({'type': 'delta', 'text': value['prompt']})
        emit({'type': 'completed'})
    elif mode == 'usage':
        emit({'type': 'delta', 'text': 'Kết quả mẫu'})
        emit({'type': 'completed', 'usage': {'input_tokens': 12, 'output_tokens': 4}})
    elif mode == 'sleep':
        time.sleep(60)
    elif mode == 'malformed':
        print('not-json SECRET_SENTINEL', flush=True)
    elif mode == 'stderr':
        print('SECRET_SENTINEL', file=sys.stderr, flush=True)
        sys.exit(9)
    elif mode == 'stderr_flood':
        sys.stderr.write('x' * 1048576)
        sys.stderr.flush()
    elif mode == 'flood':
        emit({'type': 'delta', 'text': 'x' * 200000})
    elif mode == 'incomplete':
        emit({'type': 'delta', 'text': 'partial'})
    elif mode == 'trailing':
        emit({'type': 'completed'})
        emit({'type': 'delta', 'text': 'after-terminal'})
    elif mode == 'false_success':
        emit({'type': 'completed'})
        sys.exit(7)
    elif mode == 'bad_usage':
        emit({'type': 'completed', 'usage': {'input_tokens': True, 'output_tokens': -1}})
    elif mode == 'duplicate':
        emit({'type': 'completed'})
        emit({'type': 'completed'})
    elif mode == 'duplicate_keys':
        print('{"type":"delta","type":"completed"}', flush=True)
    elif mode == 'env':
        emit({'type': 'delta', 'text': json.dumps(sorted(os.environ))})
        emit({'type': 'completed'})
    elif mode == 'tree':
        # Known synthetic child, not a provider CLI. Child is contained even
        # when its parent exits, without relying on a reused PID/taskkill.
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time;time.sleep(60)'])
        emit({'type': 'delta', 'text': str(child.pid)})
        sys.stdout.flush()
        os._exit(0)
    elif mode == 'delay':
        emit({'type': 'delta', 'text': 'first'})
        time.sleep(.15)
        emit({'type': 'delta', 'text': 'second'})
        emit({'type': 'completed'})
    else:
        sys.exit(8)


if __name__ == '__main__':
    main()
