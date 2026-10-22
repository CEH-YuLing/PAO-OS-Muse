import type {components} from '../../../packages/contracts/schema';
export type RuntimeState = 'standby' | 'listening' | 'processing' | 'reasoning' | 'speaking';
export type RuntimeEvent = components['schemas']['RunEvent'];
export type Projection = {
  runId: string; cursor: number; state: RuntimeState; response: string;
  trace: RuntimeEvent[]; activeAgents: string[]; terminal: 'completed' | 'failed' | 'cancelled' | null;
};
export const stateLabels: Record<RuntimeState, string>;
export function initialRuntime(runId?: string): Projection;
export function applyRuntimeEvent(current: Projection, event: RuntimeEvent): Projection;
export function visualState(state: RuntimeState): 'idle' | 'thinking' | 'speaking';
