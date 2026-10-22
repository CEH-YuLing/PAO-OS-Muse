"""Explicitly enable/disable local Meta Copilot writes without accepting secrets."""
import argparse
from pao.config import ROOT


def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--enable',action='store_true');group.add_argument('--disable',action='store_true')
    args=parser.parse_args()
    if args.enable and input('Type ENABLE META WRITE to continue: ')!='ENABLE META WRITE':
        raise SystemExit('Confirmation did not match; configuration unchanged')
    path=ROOT/'.env';lines=path.read_text(encoding='utf-8').splitlines()
    lines=[line for line in lines if not line.startswith('META_WRITE_ENABLED=')]
    lines.append('META_WRITE_ENABLED='+('true' if args.enable else 'false'))
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Meta Write '+('enabled' if args.enable else 'disabled')+'. Restart API/worker and reconnect Meta to refresh OAuth scopes.')


if __name__=='__main__':main()
