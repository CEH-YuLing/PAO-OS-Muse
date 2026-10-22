"""Verify a retained S0.3 checkpoint by restoring into an owned, fresh clone.

Never migrate the primary or reuse/drop an existing database. Check exact row
hashes, columns, constraints/index/trigger definitions, revision and archives.
The only removed database is the generated clone created by this invocation.
"""
import argparse
import asyncio
import json
from pathlib import Path
import re
import subprocess
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from pao.config import ROOT, settings
from pao.modules.operations.checkpoint import digest, verify
from pao.skills import execution_binding
from check_m2_restore import inspect
from check_p11_migration import CONTAINER, snapshot

SUPPORTED_REVISIONS=('0048','0049','0050','0051','0052','0053','0054','0055','0056','0057','0058','0059','0060','0061','0062','0063','0064','0065','0066','0067','0068','0069','0070','0071','0072','0073','0074','0075','0077')


def docker(*args, **kwargs):
    return subprocess.run(['docker', 'exec', *args], check=True, timeout=120, **kwargs)


def canonical_sql(value):
    """Only normalize PostgreSQL's equivalent unbounded-varchar literal arrays.

    Dump/reparse can move ::text[] from ARRAY to each varchar literal. Preserve
    literal values, order, other casts, parentheses and all nonmatching SQL.
    """
    if not isinstance(value, str):
        return value
    literal = r"'(?:[^']|'')*'"
    item = (r"(?:" + literal + r"::character varying(?:::text)?|\("
            + literal + r"::character varying\)::text)")
    pattern = re.compile(r"\b(?P<operator>ANY|ALL)\s*\(\s*(?P<array_wrap>\()?\s*ARRAY\[(?P<items>" + item
        + r"(?:,\s*" + item + r")*)\](?(array_wrap)\s*\))\s*(?P<array_cast>::text\[\])?\s*\)")
    def replace(match):
        items = match.group('items')
        if not (match.group('array_cast') or
                all(part.group().endswith('::text') for part in re.finditer(item, items))):
            return match.group()
        return match.group('operator') + ' (ARRAY[' + ', '.join(v + '::text' for v in re.findall(literal, items)) + '])'
    return pattern.sub(replace, value)


def definition_row(kind, row):
    # Never normalize defaults or function bodies: they may contain text data.
    return tuple(canonical_sql(value) if kind in ('constraints', 'indexes') and column == 2
                 else value for column, value in enumerate(row))


async def schema(url):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as db:
            checks = (
                """SELECT c.relname, a.attname, format_type(a.atttypid,a.atttypmod),
                    a.attnotnull, pg_get_expr(d.adbin,d.adrelid), a.attidentity,
                    a.attgenerated FROM pg_attribute a
                    JOIN pg_class c ON c.oid=a.attrelid
                    JOIN pg_namespace n ON n.oid=c.relnamespace
                    LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                    WHERE n.nspname='public' AND a.attnum>0 AND NOT a.attisdropped
                    ORDER BY c.relname,a.attnum""",
                """SELECT c.relname,k.conname,pg_get_constraintdef(k.oid,true)
                    FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
                    JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' ORDER BY c.relname,k.conname""",
                """SELECT tablename,indexname,indexdef FROM pg_indexes
                    WHERE schemaname='public' ORDER BY tablename,indexname""",
                """SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid,true)
                    FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
                    JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND NOT t.tgisinternal
                    ORDER BY c.relname,t.tgname""",
                """SELECT p.proname,pg_get_function_identity_arguments(p.oid),
                    pg_get_functiondef(p.oid) FROM pg_proc p
                    JOIN pg_namespace n ON n.oid=p.pronamespace
                    WHERE n.nspname='public' AND p.prokind='f'
                    ORDER BY p.proname,pg_get_function_identity_arguments(p.oid)""",
            )
            return [[definition_row(kind, row) for row in (await db.execute(text(sql))).tuples()]
                    for kind, sql in zip(('attributes', 'constraints', 'indexes', 'triggers', 'functions'), checks)]
    finally:
        await engine.dispose()


async def main(manifest_path, gd00_baseline=None):
    url = make_url(settings().database_url)
    if (ROOT.resolve() != Path('F:/PAO-ACOS') or url.database != 'pao_acos_local'
            or url.host != '127.0.0.1' or url.port != 15432 or url.username != 'pao'):
        raise RuntimeError('S0.3 requires the isolated ACOS primary')
    manifest = Path(manifest_path).resolve(strict=True)
    if not manifest.is_relative_to((ROOT / '.runtime/checkpoints').resolve()):
        raise RuntimeError('Checkpoint outside owned runtime')
    saved = json.loads(manifest.read_text(encoding='utf-8'))
    dump = Path(saved['database']['backup']).resolve(strict=True)
    archive = Path(saved['source']['path']).resolve(strict=True)
    assert dump.is_relative_to((ROOT / '.runtime').resolve())
    assert archive.is_relative_to(manifest.parent)
    assert digest(dump) == saved['database']['sha256']
    assert digest(archive) == saved['source']['sha256']
    assert saved['binding'] == execution_binding()
    verify(archive, saved['source']['files'])
    before = await snapshot(url)
    definitions = await schema(url)
    archives = await inspect(url)
    assert archives['revision'] == saved['database']['revision_before']
    assert archives['revision'] in SUPPORTED_REVISIONS, 'Unsupported SaaS checkpoint revision'
    name = 'pao_s03_restore_' + uuid4().hex
    assert re.fullmatch(r'pao_s03_restore_[0-9a-f]{32}', name)
    engine = create_async_engine(url)
    try:
        async with engine.connect() as db:
            assert not await db.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': name})
    finally:
        await engine.dispose()
    created = False
    try:
        docker(CONTAINER, 'createdb', '-U', 'pao', name)
        created = True
        with dump.open('rb') as data:
            docker('-i', CONTAINER, 'pg_restore', '-U', 'pao', '-d', name,
                   '--no-owner', '--exit-on-error', stdin=data)
        target = url.set(database=name)
        restored_rows=await snapshot(target)
        if restored_rows != before:
            # Report only table identifiers/counts; never rows or private bodies.
            differing=sorted(name for name in set(before[1])|set(restored_rows[1])
                if before[1].get(name)!=restored_rows[1].get(name) or before[0].get(name)!=restored_rows[0].get(name))
            print(json.dumps({'restore_row_difference':[{'table':name,
                'primary_count':before[1].get(name,{}).get('count'),
                'checkpoint_count':restored_rows[1].get(name,{}).get('count')} for name in differing]}))
            raise AssertionError('Restored row hashes/columns differ')
        restored_definitions = await schema(target)
        if restored_definitions != definitions:
            # Diagnose identifiers/counts only: never print function bodies/defaults.
            for kind, original, restored in zip(('attributes', 'constraints', 'indexes', 'triggers', 'functions'),
                                                definitions, restored_definitions):
                if original != restored:
                    removed = [row[:2] for row in original if row not in restored]
                    added = [row[:2] for row in restored if row not in original]
                    print(json.dumps({'schema_difference': kind, 'original_count': len(original),
                        'restored_count': len(restored), 'original_identifiers': removed[:12],
                        'restored_identifiers': added[:12]}))
            raise AssertionError('Restored schema definitions differ')
        assert await inspect(target) == archives, 'Restored revision/archive evidence differs'
        reader = None
        if gd00_baseline is not None:
            from gd00_baseline import owned_path
            from gd00_clone_reader import run_restored_reader
            folder = owned_path(gd00_baseline, ROOT/'.runtime')
            if not re.fullmatch(r'gd00-[0-9a-f]{32}', folder.name):
                raise ValueError('gd00_baseline_folder_denied')
            reader = run_restored_reader(target, saved, archive, folder)
            assert await snapshot(target) == restored_rows, 'Clone reader changed restored rows'
            assert await schema(target) == restored_definitions, 'Clone reader changed restored schema'
        assert await snapshot(url) == before, 'Primary changed during restore verification'
        assert await schema(url) == definitions
        print(json.dumps({'pass': True, 'revision': archives['revision'],
            'business_tables': len(before[0]), 'physical_tables': len(archives['counts']),
            'artifacts': len(archives['artifact_hashes']), 'row_hashes_exact': True,
            'schema_definitions_equivalent': True,
            'normalization': 'unbounded_varchar_literal_text_arrays_only', 'primary_unchanged': True,
            'binding': execution_binding(), 'manifest': str(manifest),
            'clone': name, 'external_calls': False, 'clone_reader': reader}))
    finally:
        if created:
            docker(CONTAINER, 'dropdb', '-U', 'pao', name)
            print('Removed only this invocation-owned restore clone; retained backup/source checkpoint.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    parser.add_argument('--gd00-baseline')
    args = parser.parse_args()
    asyncio.run(main(args.manifest, args.gd00_baseline))
