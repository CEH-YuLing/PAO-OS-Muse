"""Container fixture: real CLI metadata only, empty home and network=none.

No login, prompt or attempt to read host credentials. Not a native PAO job.
"""
import hashlib,json,os,re,subprocess,sys,time
from pathlib import Path

def main():
    assert sys.argv[1:] in ([],['--fixture-hang'])
    if sys.argv[1:]:
        # No CLI invocation. The host harness must tear down this owned container.
        time.sleep(120)
        raise RuntimeError('Host timeout guard did not stop the fixture')
    assert os.getuid()==65534
    assert os.environ['HOME']=='/profile' and os.environ['CLAUDE_CONFIG_DIR']=='/profile/.claude'
    assert not any(k.startswith(('ANTHROPIC_','CLAUDE_CODE_OAUTH','OPENAI_','GEMINI_','GOOGLE_','AWS_')) for k in os.environ)
    assert not any(Path(p).exists() for p in ('/profile/.claude/.credentials.json','/host','/app/.env','/var/run/docker.sock'))
    assert not any(Path('/workspace').iterdir())
    root_readonly=False
    try:
        with Path('/ea3-should-be-denied').open('x') as f:f.write('fixture')
    except OSError as exc:
        root_readonly=exc.errno==30
    assert root_readonly
    managed=json.loads(Path('/etc/claude-code/managed-settings.json').read_text())
    assert managed['disableAllHooks'] is True and managed['autoMemoryEnabled'] is False
    assert 'mcp__*' in managed['permissions']['deny']
    Path('/profile/.claude').mkdir(mode=0o700)
    Path('/tmp/ea3-scratch').touch()
    data={}
    for name,args in (('version',['--version']),('help',['--help']),('auth_status',['auth','status','--json'])):
        result=subprocess.run(['/usr/local/bin/claude',*args],cwd='/workspace',stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        assert len(result.stdout)+len(result.stderr)<=262144
        if name=='version':
            assert result.returncode==0 and result.stdout.decode().strip()=='2.1.220 (Claude Code)'
            data['version']='2.1.220'
        elif name=='help':
            assert result.returncode==0
            flags=set(re.findall(r'(?<![\w-])--[a-z][a-zA-Z-]*',result.stdout.decode()))
            required={'--print','--tools','--mcp-config','--strict-mcp-config','--settings','--setting-sources',
                      '--model','--output-format','--no-session-persistence','--disable-slash-commands'}
            assert required <= flags
            data['required_flags_present']=True
        else:
            auth=json.loads(result.stdout.decode())
            assert result.returncode==1 and auth.get('loggedIn') is False
            assert auth.get('authMethod') in (None,'none')
            data['empty_profile_authentication']='not_authenticated'
    # Unauthenticated CLI preflight with synthetic-only input and no network.
    # No real provider request is possible. This is NOT a successful inference.
    work=Path('/tmp/ea3-work');(work/'.claude').mkdir(parents=True)
    hook={'hooks':{'SessionStart':[{'hooks':[{'type':'command','command':'touch /tmp/ea3-hook-ran'}]}]}}
    for target in (Path('/profile/.claude/settings.json'),work/'.claude/settings.json'):
        target.write_text(json.dumps(hook))
    (work/'.mcp.json').write_text(json.dumps({'mcpServers':{'sentinel':{'command':'sh','args':['-c','touch /tmp/ea3-mcp-ran']}}}))
    argv=['/usr/local/bin/claude','--print','--input-format','text','--output-format','stream-json','--verbose',
          '--tools','','--permission-mode','dontAsk','--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
          '--setting-sources','','--settings',json.dumps({'disableAllHooks':True,'autoMemoryEnabled':False}),
          '--disable-slash-commands','--no-session-persistence']
    run=subprocess.run(argv,input=b'Synthetic offline unauthenticated preflight only.\n',cwd=work,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    assert len(run.stdout)+len(run.stderr)<=262144
    values=[json.loads(line) for line in run.stdout.decode().splitlines() if line]
    init=[v for v in values if v.get('type')=='system' and v.get('subtype')=='init']
    final=[v for v in values if v.get('type')=='result']
    assert len(init)==len(final)==1 and run.returncode!=0
    assert init[0].get('tools')==[] and init[0].get('mcp_servers')==[] and init[0].get('plugins',[])==[]
    # Measured CLI2.1.220 emits subtype=success even for a failed unauthenticated
    # turn. is_error=true and nonzero exit are authoritative; never subtype alone.
    assert final[0].get('is_error') is True
    assert not Path('/tmp/ea3-hook-ran').exists() and not Path('/tmp/ea3-mcp-ran').exists()
    data.update({'unauthenticated_print_denied':True,'preauth_init_tools':0,'preauth_init_mcp':0,
                 'synthetic_user_project_hook_not_run':True,'synthetic_project_mcp_not_run':True,
                 'result_subtype':final[0].get('subtype')})
    sha=hashlib.sha256(Path('/usr/local/bin/claude').read_bytes()).hexdigest()
    print(json.dumps({'pass':True,'binary_sha256':sha,**data,'uid':os.getuid(),'root_readonly':True,
                     'provider_calls':0,'inference_called':False,'login_started':False,
                     'tool_isolation_live_verified':False,'native_PAO_job':False}))

if __name__=='__main__':main()
