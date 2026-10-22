"""Bounded owned API/Web; API stays in fixture process, HTTP is genuine."""
import asyncio,json,os,socket,subprocess
from uuid import uuid4
import httpx,uvicorn
from pao.config import ROOT
from pao.main import app
from p63_browser_acceptance import OwnedServer

async def browser(script,env_name,fixture,label,direct_proxy=False):
    assert os.environ['DATABASE_URL'].endswith('/pao_test')
    directory=ROOT/'.runtime'/(label+'-browser-'+uuid4().hex);directory.mkdir()
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=OwnedServer(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',access_log=False,log_level='error'))
    task=asyncio.create_task(server.serve(sockets=[sock]));web=None
    try:
        for _ in range(100):
            if server.started:break
            await asyncio.sleep(.1)
        assert server.started
        with (directory/'web.log').open('w',encoding='utf-8') as log:
            probe=socket.socket();probe.bind(('127.0.0.1',3201));probe.close()
            web_env={**os.environ,'PAO_BUILD_CHECK':'1'}
            if direct_proxy:web_env['PAO_API_URL']=f'http://127.0.0.1:{port}'
            web=subprocess.Popen(['node','node_modules/next/dist/bin/next','dev','apps/web','--hostname','127.0.0.1','--port','3201'],cwd=ROOT,env=web_env,stdout=log,stderr=log)
            async with httpx.AsyncClient(timeout=3) as http:
                for _ in range(80):
                    assert web.poll() is None
                    try:
                        if (await http.get('http://127.0.0.1:3201/')).status_code==200:break
                    except httpx.HTTPError:pass
                    await asyncio.sleep(.5)
                else:raise AssertionError('Owned test Web not ready')
            payload={**fixture,'api':f'http://127.0.0.1:{port}','web':'http://127.0.0.1:3201','screenshot':str(directory/(label+'-mobile.png'))}
            result=await asyncio.to_thread(subprocess.run,['node',script],cwd=ROOT,env={**os.environ,env_name:json.dumps(payload)},capture_output=True,text=True,timeout=240 if direct_proxy else 150)
            reason=next((s for s in result.stderr.splitlines() if s.startswith('P6 browser failed at ')),'P6 browser subprocess failed')
            diagnostics=[s for s in result.stderr.splitlines() if s.startswith('Browser route diagnostic ')][:10]
            if diagnostics:reason+='; '+'; '.join(diagnostics)
            assert result.returncode==0,reason
            report=json.loads(result.stdout);assert report['pass'] and report['real_http']
            (directory/'browser.json').write_text(json.dumps(report),encoding='utf-8');return report
    finally:
        server.should_exit=True
        try:await asyncio.wait_for(task,10)
        finally:
            sock.close()
            if web and web.poll() is None:
                await asyncio.to_thread(subprocess.run,['taskkill.exe','/PID',str(web.pid),'/T','/F'],capture_output=True,timeout=10)
                await asyncio.to_thread(web.wait,10)
