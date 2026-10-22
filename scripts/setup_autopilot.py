"""Explicitly enable or disable both local Phase 13 Autopilot runtime gates."""
import argparse
from pao.config import ROOT


def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--enable',action='store_true');group.add_argument('--disable',action='store_true')
    args=parser.parse_args()
    if args.enable and input('Type ENABLE LIMITED AUTOPILOT to continue: ')!='ENABLE LIMITED AUTOPILOT':
        raise SystemExit('Confirmation did not match; configuration unchanged')
    path=ROOT/'.env';lines=path.read_text(encoding='utf-8').splitlines()
    names=('ADS_AUTOPILOT_GLOBAL_ENABLED=','META_AUTOPILOT_ENABLED=')
    lines=[line for line in lines if not line.startswith(names)]
    value='true' if args.enable else 'false'
    lines.extend([f'ADS_AUTOPILOT_GLOBAL_ENABLED={value}',f'META_AUTOPILOT_ENABLED={value}'])
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Limited Autopilot runtime gates '+('enabled' if args.enable else 'disabled')+'. Restart API and worker.')


if __name__=='__main__':main()
