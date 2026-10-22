import test from 'node:test';import assert from 'node:assert/strict';
import {mcpEndpoint,mcpToken,mcpRows,mcpArguments,mcpDiscoveryRequest,mcpAudit,mcpSettingsError} from './mcp-settings.mjs';
const id='12345678-1234-1234-1234-123456789abc',workspace='abcdef12-1234-1234-1234-123456789abc',tool='mcp.'+id.replaceAll('-','')+'.read_report';
const row=()=>({id,workspace_id:workspace,endpoint:'https://fixture.example/mcp',status:'connected',protocol:'2025-11-25',version:2,secret_present:true,circuit_open:false,manifest_hash:'a'.repeat(64),permissions:[tool],tools:[{id:tool,name:'read_report',hash:'b'.repeat(64),input_schema:{type:'object'},output_schema:{type:'object'}}]});
test('HTTPS native endpoint profile, no URL secrets or normalized traversal',()=>{
 assert.equal(mcpEndpoint('https://FIXTURE.example:443/mcp'),'https://fixture.example/mcp');
 for(const value of ['http://fixture.example/mcp','https://u:secret@fixture.example/mcp','https://fixture.example/mcp?token=x','https://fixture.example/mcp#x','https://127.0.0.1/mcp','https://localhost/mcp','https://fixture.example:444/mcp','https://fixture.example/a/../mcp','https://fixture.example/%2f','https://fixture.example\\mcp'])assert.throws(()=>mcpEndpoint(value),/mcp_endpoint_invalid/);
});
test('bearer optional create, required rotation, no whitespace/prefix',()=>{
 assert.equal(mcpToken(''),'');assert.equal(mcpToken('fixture-token-not-real'),'fixture-token-not-real');
 for(const value of ['','short','Bearer fixture-token','fixture-token\n','fixture token not real','é'.repeat(20),'x'.repeat(2049)])assert.throws(()=>mcpToken(value,true),/mcp_token_invalid/);
});
test('snapshot is native workspace/namespace/version/status/permission bound',()=>{
 assert.equal(mcpRows([row()],workspace).length,1);assert.deepEqual(mcpRows([],workspace),[]);
 for(const change of [{workspace_id:id},{version:0},{version:NaN},{status:'healthy'},{protocol:'2026-07-28'},{secret_present:'true'},{circuit_open:0},{manifest_hash:'bad'},{permissions:['unrelated']},{permissions:[tool,tool]},{tools:[{...row().tools[0],id:'other'}]}])assert.throws(()=>mcpRows([{...row(),...change}],workspace),/mcp_response_invalid/);
 assert.throws(()=>mcpRows([row(),row()],workspace));assert.throws(()=>mcpRows({},workspace));
});
test('bound arguments object and length, never silently replace invalid input',()=>{
 assert.deepEqual(mcpArguments('{"text":"fixture"}'),{text:'fixture'});
 for(const value of ['[]','null','"string"','{bad}', ' '.repeat(65537)])assert.throws(()=>mcpArguments(value),/mcp_arguments_invalid/);
});
test('discovery nonce and version only, no token or grant in metadata request',()=>{
 const request=mcpDiscoveryRequest(id,2,workspace);assert.equal(request.headers['Idempotency-Key'],workspace);assert.deepEqual(JSON.parse(request.body),{version:2});assert.equal(request.path,'/v1/connectors/connections/'+id+'/test');
 assert.throws(()=>mcpDiscoveryRequest(id,2,'bad'));assert.throws(()=>mcpDiscoveryRequest('../escape',2,workspace));
});
test('audit projects IDs/actions, never arbitrary private data',()=>{
 assert.deepEqual(mcpAudit([{id,action:'revoked',data:{credential_purged:true,token:'fixture-private'},token:'fixture-private'}]),[{id,action:'revoked'}]);assert.throws(()=>mcpAudit([{id,action:'provider error token'}]));
});
test('error help never echoes arbitrary server error or credential',()=>{
 assert.ok(!mcpSettingsError('fixture-private-token').includes('fixture-private-token'));assert.match(mcpSettingsError('connector_revision_conflict'),/phiên bản/);assert.match(mcpSettingsError('tenant_metadata_daily_exhausted'),/tìm danh mục/);assert.match(mcpSettingsError('connector_auth_denied'),/đổi khóa/);assert.match(mcpSettingsError('connector_circuit_open'),/cooldown/);assert.match(mcpSettingsError('connector_protocol_invalid'),/không tự đổi giao thức/);
});
