"""Real pg_tools transport for an isolated Linux-container test namespace.

No Docker socket, no primary database URL, no GitHub execution claim.
"""
import os
from pathlib import Path
import re
import subprocess
import sys


class PgTools:
    def __init__(self, root, url, env, populated, manifest, platform=None):
        platform = sys.platform if platform is None else platform
        run = env.get('PAO_S6_LINUX_RUN', '')
        if (platform != 'linux' or env.get('PAO_LINUX_LOCAL_RESTORE') != '1'
            or not re.fullmatch('[a-f0-9]{32}', run) or not populated or manifest
            or Path(root).as_posix() != '/workspace'
            or url.drivername != 'postgresql+asyncpg' or url.host != '127.0.0.1'
            or url.port != 5432 or url.database != 'pao_test' or url.username != 'pao'):
            raise ValueError('isolated_linux_test_restore_required')
        self.created = set()
        self.env = {**env, 'PGHOST': '127.0.0.1', 'PGPORT': '5432',
            'PGUSER': 'pao', 'PGPASSWORD': url.password or ''}

    def __call__(self, *args, **kwargs):
        args = list(args)
        if args and args[0] == '-i': args.pop(0)
        if len(args) < 3: raise ValueError('restore_command_required')
        args.pop(0)  # Existing transport's container argument is not executed.
        command, *options = args
        if command == 'pg_dump':
            if options != ['-U','pao','-d','pao_test','-Fc']:
                raise ValueError('test_dump_only')
        elif command in ('createdb','dropdb'):
            if (len(options) != 3 or options[:2] != ['-U','pao']
                or not re.fullmatch('pao_p7_restore_[a-f0-9]{32}', options[2])):
                raise ValueError('owned_clone_required')
            if command == 'dropdb' and options[2] not in self.created:
                raise ValueError('unowned_clone')
        elif command == 'pg_restore':
            if (len(options) != 6 or options[:3] != ['-U','pao','-d']
                or options[3] not in self.created
                or options[4:] != ['--no-owner','--exit-on-error']):
                raise ValueError('owned_restore_only')
        else:
            raise ValueError('unsupported_restore_command')
        result = subprocess.run([command,*options], check=True, env=self.env,
            timeout=90, **kwargs)
        if command == 'createdb': self.created.add(options[2])
        if command == 'dropdb': self.created.remove(options[2])
        return result
