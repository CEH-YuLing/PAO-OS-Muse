from zipfile import ZipFile
import check_phase3_readiness as check

def test_added_or_mutated_runtime_source_cannot_reuse_ci(tmp_path,monkeypatch):
 root=tmp_path/'source';source=root/'apps/api/pao/core.py';source.parent.mkdir(parents=True);source.write_text('baseline')
 receipt=tmp_path/'receipt';receipt.mkdir()
 with ZipFile(receipt/'source.zip','w') as z:z.write(source,'apps/api/pao/core.py')
 monkeypatch.setattr(check,'ROOT',root)
 assert check.current_source(receipt,'ci')
 extra=source.parent/'unverified.py';extra.write_text('must reject')
 assert not check.current_source(receipt,'ci')
 extra.unlink();source.write_text('changed')
 assert not check.current_source(receipt,'ci')

def test_generated_cache_is_not_misrepresented_as_runtime_source(tmp_path):
 root=tmp_path;source=root/'apps/api/pao/core.py';source.parent.mkdir(parents=True);source.write_text('baseline')
 cache=root/'apps/web/.next';cache.mkdir(parents=True);(cache/'generated.js').write_text('generated')
 metadata=root/'apps/api/pao_backend.egg-info';metadata.mkdir();(metadata/'requires.txt').write_text('generated package metadata')
 assert check.runtime_source_names(root)=={'apps/api/pao/core.py'}
