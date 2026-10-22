export const stateLabels = {
  standby: 'Sẵn sàng', listening: 'Đang tiếp nhận', processing: 'Đang xử lý',
  reasoning: 'Đang tạo câu trả lời', speaking: 'Đang trả lời',
};

export function initialRuntime(runId = '') {
  return {runId, cursor: 0, state: 'standby', response: '', trace: [], activeAgents: [], terminal: null};
}

/** Pure replay projection. Only actual agent events can activate a node. */
export function applyRuntimeEvent(current, event) {
  if (event.run_id !== current.runId || !Number.isInteger(event.seq) || event.seq <= current.cursor || current.terminal) return current;
  const next = {...current, cursor: event.seq};
  if (event.type !== 'response.delta') next.trace = [...current.trace.slice(-99), event];
  if (['run.queued', 'run.started', 'core.processing', 'memory.search.started', 'plan.started'].includes(event.type)) next.state = 'processing';
  if (event.type === 'core.reasoning') next.state = 'reasoning';
  if (event.type === 'core.speaking') next.state = 'speaking';
  if (event.type === 'core.standby') next.state = 'standby';
  const key = event.data?.agent_key;
  if (event.type === 'agent.started' && typeof key === 'string' && key) {
    next.activeAgents = [...new Set([...current.activeAgents, key])];
    // Compatibility with persisted Phase 1 events without core.reasoning.
    if (next.state !== 'speaking') next.state = 'reasoning';
  }
  if (['agent.completed', 'agent.failed', 'agent.cancelled'].includes(event.type)) {
    next.activeAgents = current.activeAgents.filter(id => id !== key);
  }
  if (event.type === 'response.delta') {
    next.response += typeof event.data?.text === 'string' ? event.data.text : '';
    next.state = 'speaking';
  }
  if (['run.completed', 'run.failed', 'run.cancelled'].includes(event.type)) {
    next.terminal = event.type.slice(4);
    next.state = 'standby'; next.activeAgents = [];
  }
  return next;
}

export function visualState(state) {
  return state === 'speaking' ? 'speaking' : state === 'standby' ? 'idle' : 'thinking';
}
