// Advisory lookup only. Never runs audit fix or changes manifests/dependencies.
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
function assess(runtime,full){
 const counts=runtime?.metadata?.vulnerabilities,all=full?.metadata?.vulnerabilities;
 const valid=v=>v&&['critical','high','moderate','low','total'].every(k=>Number.isInteger(v[k])&&v[k]>=0);
 return {runtime_gate_pass:!!(valid(counts)&&counts.critical===0&&counts.high===0),runtime:valid(counts)?counts:null,
  full:valid(all)?all:null,dev_review_pending:!valid(all)||all.critical>0||all.high>0,production_accepted:false};
}
function main(){
 const npm=path.resolve(path.dirname(process.execPath),process.platform==='win32'?'node_modules/npm/bin/npm-cli.js':'../lib/node_modules/npm/bin/npm-cli.js');
 function audit(extra){const result=spawnSync(process.execPath,[npm,'audit','--json','--package-lock-only','--registry=https://registry.npmjs.org','--fetch-retries=0','--fetch-timeout=30000',...extra],{encoding:'utf8',timeout:65000,maxBuffer:8*1024*1024});
  if(result.error||![0,1].includes(result.status))throw Error('Advisory service unavailable; not a clean audit');const data=JSON.parse(result.stdout);if(data.error||!data.metadata)throw Error('Invalid advisory response');return data;}
 const runtime=audit(['--omit=dev']),full=audit([]),result=assess(runtime,full);
 fs.mkdirSync('.runtime',{recursive:true});fs.writeFileSync('.runtime/js-security.json',JSON.stringify({observed_at:new Date().toISOString(),...result,advisories:{runtime,full}},null,2));
 console.log(JSON.stringify(result));if(!result.runtime_gate_pass)process.exitCode=1;
}
module.exports={assess};if(require.main===module){try{main();}catch(e){console.error('Dependency security gate unavailable or invalid; no clean claim.');process.exitCode=1;}}
