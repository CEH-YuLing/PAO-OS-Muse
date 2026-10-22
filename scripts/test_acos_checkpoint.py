"""Source archive only; no database, Docker, network or credentials."""
from zipfile import ZipFile
import pytest
from backup_acos_checkpoint import source_archive
from pao.modules.operations.checkpoint import verify


def test_frontend_declarations_are_backed_up_and_verified(tmp_path):
    library=tmp_path/'apps/web/lib'
    library.mkdir(parents=True)
    (library/'tenant.d.mts').write_text('export type Ticket = number;',encoding='utf-8')
    (library/'tenant.mjs').write_text('export const ticket = 1;',encoding='utf-8')
    (library/'.env.private.d.mts').write_text('must not be archived',encoding='utf-8')
    (tmp_path/'.env').write_text('SECRET=fixture-must-not-be-archived',encoding='utf-8')
    runtime=tmp_path/'.runtime'
    runtime.mkdir()
    (runtime/'private.d.mts').write_text('not source',encoding='utf-8')
    target=runtime/'source.zip'
    files=source_archive(tmp_path,target)
    assert set(files)=={'apps/web/lib/tenant.d.mts','apps/web/lib/tenant.mjs'}
    verify(target,files)
    with ZipFile(target) as saved:
        assert saved.read('apps/web/lib/tenant.d.mts')==b'export type Ticket = number;'
    with pytest.raises(FileExistsError):source_archive(tmp_path,target)


def test_absent_frontend_library_preserves_existing_source_policy(tmp_path):
    (tmp_path/'README.md').write_text('fixture',encoding='utf-8')
    files=source_archive(tmp_path,tmp_path/'source.zip')
    assert set(files)=={'README.md'}


def test_nested_jsx_included_but_secrets_and_generated_code_excluded(tmp_path):
    components=tmp_path/'apps/web/components/nested';components.mkdir(parents=True)
    (components/'Orb.jsx').write_text('export default function Orb(){return null}',encoding='utf-8')
    (components/'.env.private.jsx').write_text('private fixture',encoding='utf-8')
    for folder in ('node_modules','.pao-build-check','.runtime'):
        generated=tmp_path/'apps/web'/folder;generated.mkdir()
        (generated/'NotSource.jsx').write_text('generated fixture',encoding='utf-8')
    files=source_archive(tmp_path,tmp_path/'source.zip')
    assert set(files)=={'apps/web/components/nested/Orb.jsx'}
    verify(tmp_path/'source.zip',files)


def test_infrastructure_build_and_bootstrap_sources_are_not_lost(tmp_path):
    infra=tmp_path/'infra';infra.mkdir()
    (infra/'api.Dockerfile').write_text('FROM python:3.12-slim',encoding='utf-8')
    temporal=infra/'temporal';temporal.mkdir()
    (temporal/'setup.sh').write_text('#!/bin/sh\nexit 0\n',encoding='utf-8')
    (temporal/'.env.private.sh').write_text('private fixture',encoding='utf-8')
    files=source_archive(tmp_path,tmp_path/'source.zip')
    assert set(files)=={'infra/api.Dockerfile','infra/temporal/setup.sh'}
    verify(tmp_path/'source.zip',files)


def test_exact_codex_dockerfile_is_included_without_broadening_to_arbitrary_files(tmp_path):
    codex=tmp_path/'infra/codex-local';codex.mkdir(parents=True)
    (codex/'Dockerfile').write_text('FROM pinned-synthetic-image',encoding='utf-8')
    (codex/'.env').write_text('private fixture',encoding='utf-8')
    unknown=tmp_path/'infra/unreviewed';unknown.mkdir()
    (unknown/'Dockerfile').write_text('not reviewed',encoding='utf-8')
    files=source_archive(tmp_path,tmp_path/'source.zip')
    assert set(files)=={'infra/codex-local/Dockerfile'}
    verify(tmp_path/'source.zip',files)
