import test from 'node:test';
import assert from 'node:assert/strict';
import {initialRuntime, applyRuntimeEvent, visualState} from './runtime-state.mjs';
const event = (seq, type, data = {}, run_id = 'run-a') => ({seq, type, data, run_id});

test('observable lifecycle and actual active agents, no activity inferred from core', () => {
  let s = initialRuntime('run-a');
  s = applyRuntimeEvent(s, event(1, 'run.queued'));
  assert.equal(s.state, 'processing'); assert.deepEqual(s.activeAgents, []);
  s = applyRuntimeEvent(s, event(2, 'agent.started', {agent_key: 'chief_of_staff'}));
  assert.deepEqual(s.activeAgents, ['chief_of_staff']); assert.equal(s.state, 'reasoning');
  s = applyRuntimeEvent(s, event(3, 'core.reasoning'));
  s = applyRuntimeEvent(s, event(4, 'core.speaking'));
  s = applyRuntimeEvent(s, event(5, 'response.delta', {text: 'Xin chào'}));
  assert.equal(s.state, 'speaking'); assert.equal(s.response, 'Xin chào');
  s = applyRuntimeEvent(s, event(6, 'agent.completed', {agent_key: 'chief_of_staff'}));
  assert.deepEqual(s.activeAgents, []);
  s = applyRuntimeEvent(s, event(7, 'run.completed'));
  assert.equal(s.state, 'standby'); assert.equal(s.terminal, 'completed');
});

test('replay ignores duplicate, out of order and other run events', () => {
  let s = applyRuntimeEvent(initialRuntime('run-a'), event(2, 'response.delta', {text: 'Một'}));
  const saved = s;
  for (const e of [event(2, 'response.delta', {text: 'Một'}), event(1, 'core.processing'), event(3, 'response.delta', {text: 'khác'}, 'run-b')]) {
    s = applyRuntimeEvent(s, e); assert.equal(s, saved);
  }
  s = applyRuntimeEvent(s, event(3, 'response.delta', {text: ' lần'}));
  assert.equal(s.response, 'Một lần');
  assert.equal(initialRuntime('run-b').response, '');
});

for (const status of ['failed', 'cancelled']) test(`${status} clears agents, preserves partial response and ignores late deltas`, () => {
  let s = initialRuntime('run-a');
  for (const e of [event(1, 'agent.started', {agent_key: 'chief_of_staff'}), event(2, 'response.delta', {text: 'Một phần'}), event(3, `run.${status}`)]) s = applyRuntimeEvent(s, e);
  assert.equal(s.state, 'standby'); assert.deepEqual(s.activeAgents, []); assert.equal(s.response, 'Một phần');
  assert.equal(applyRuntimeEvent(s, event(4, 'response.delta', {text: 'late'})), s);
});

test('only matching agent terminal event deactivates its node', () => {
  let s = initialRuntime('run-a');
  for (const e of [event(1, 'agent.started', {agent_key: 'researcher'}), event(2, 'agent.started', {agent_key: 'editor'}), event(3, 'agent.failed', {agent_key: 'researcher'})]) s = applyRuntimeEvent(s, e);
  assert.deepEqual(s.activeAgents, ['editor']);
});

test('legacy Phase 1 events and visual adapter remain compatible', () => {
  let s = initialRuntime('run-a');
  for (const e of [event(1, 'agent.started', {agent_key: 'chief_of_staff'}), event(2, 'response.delta', {text: 'Cũ'}), event(3, 'run.completed')]) s = applyRuntimeEvent(s, e);
  assert.equal(s.response, 'Cũ'); assert.equal(s.state, 'standby');
  assert.equal(visualState('standby'), 'idle'); assert.equal(visualState('reasoning'), 'thinking');
  assert.equal(visualState('listening'), 'thinking'); assert.equal(visualState('speaking'), 'speaking');
});
