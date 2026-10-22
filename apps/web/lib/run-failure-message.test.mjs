import test from 'node:test';
import assert from 'node:assert/strict';
import {runFailureMessage} from './run-failure-message.mjs';

test('no error is empty',()=>{for(const value of [null,undefined,''])assert.equal(runFailureMessage(value),'');});
test('Codex failure is not an Ollama diagnosis or an invented root cause',()=>{
  const value=runFailureMessage('cli_provider_failed');
  assert.match(value,/Codex/);assert.match(value,/chưa xác định/);assert.doesNotMatch(value,/Ollama/);
  assert.match(value,/không tự thử lại/);assert.match(value,/Hạn mức.*chưa xác định/);
});
for(const code of ['cli_access_denied','cli_timeout','cli_profile_busy','cli_cleanup_failed','cli_binary_changed','cli_tool_event_denied','cli_plan_invalid','cli_runtime_failed',
    'engine_provider_rate_limited','engine_provider_authentication','engine_provider_temporary','engine_resource_cooling_down','engine_timeout',
    'engine_output_budget_exhausted','engine_budget_exhausted','context_transport_limit','engine_provider_context_exceeded','engine_provider_limits_unknown']){
  test(`safe actionable message: ${code}`,()=>{const value=runFailureMessage(code);assert.ok(value.includes(code));assert.doesNotMatch(value,/Ollama/);assert.match(value,/không tự thử lại/);});
}
test('unknown input is never reflected or treated as a provider code',()=>{
  for(const value of ['SECRET_SENTINEL','https://example.com/?token=SECRET_SENTINEL',{message:'SECRET_SENTINEL'},1]){
    const result=runFailureMessage(value);assert.doesNotMatch(result,/SECRET_SENTINEL|https:\/\//);assert.match(result,/không suy ra/);
  }
});
