"""Audit locked runtime requirements using an isolated pinned tool environment."""
import hashlib,json,os,subprocess,sys
from pathlib import Path

def assess(report):
    if not isinstance(report,dict) or not isinstance(report.get('dependencies'),list) or not report['dependencies']:
        raise ValueError('audit_report_missing_dependencies')
    affected=[]
    for item in report['dependencies']:
        if not isinstance(item,dict) or not item.get('name') or 'skip_reason' in item or not isinstance(item.get('vulns'),list):
            raise ValueError('audit_incomplete_dependency')
        if item['vulns']:affected.append({'name':item['name'],'version':item['version'],'findings':[
            {key:v.get(key) for key in ('id','aliases','fix_versions')} for v in item['vulns']]})
    return {'audit_completed':True,'runtime_clean':not affected,'affected_packages':affected,'audited_count':len(report['dependencies'])}

def main():
    root=Path.cwd();lock=root/'requirements.lock';runtime=root/'.runtime';runtime.mkdir(exist_ok=True)
    tool=runtime/'python-audit-tool';assert not tool.exists(),'Fresh isolated audit tool directory required'
    result={'audit_completed':False,'runtime_clean':False,'production_accepted':False,
        'runtime_requirements_sha256':hashlib.sha256(lock.read_bytes()).hexdigest(),'tool':'pip-audit==2.10.1'}
    env={**os.environ,'PIP_DISABLE_PIP_VERSION_CHECK':'1','PIP_NO_INPUT':'1','PIP_DEFAULT_TIMEOUT':'30'}
    try:
        subprocess.run([sys.executable,'-m','venv',str(tool)],check=True,timeout=60,env=env)
        py=tool/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        with (runtime/'python-audit-tool.log').open('wb') as log:
            subprocess.run([str(py),'-m','pip','install','--no-cache-dir','pip-audit==2.10.1'],check=True,timeout=180,env=env,stdout=log,stderr=subprocess.STDOUT)
        checked=subprocess.run([str(py),'-m','pip_audit','--disable-pip','--no-deps','-r',str(lock),'-f','json'],capture_output=True,text=True,encoding='utf-8',timeout=90,env=env)
        (runtime/'python-audit-raw.json').write_text(checked.stdout,encoding='utf-8')
        (runtime/'python-audit-stderr.log').write_text(checked.stderr,encoding='utf-8')
        report=json.loads(checked.stdout);result.update(assess(report))
        if checked.returncode!=0 or not result['runtime_clean']:raise RuntimeError('runtime_advisory_gate_failed')
    finally:
        (runtime/'python-security.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)

if __name__=='__main__':main()
