export type ResourcePool = 'models' | 'reads' | 'metadata';
export type ResourceSnapshot = {workspace_id?: string; model_policy?: Record<string,number>; read_policy?: Record<string,number>; metadata_policy?: Record<string,number>; host_ceilings: Record<string,number>; usage: Record<string,number|null|string>; grants_authorized: false};
export const resourcePools: Record<ResourcePool,{title:string;policy:'model_policy'|'read_policy'|'metadata_policy';fields:Record<string,[string,number]>;usage:Record<string,string>;help:string}>;
export function validateResourceSnapshot(pool:ResourcePool,data:unknown,workspace:string):ResourceSnapshot;
export function resourceDraft(pool:ResourcePool,data:ResourceSnapshot):Record<string,string>;
export function resourcePayload(pool:ResourcePool,data:ResourceSnapshot,draft:Record<string,string>):Record<string,number>;
export function resourceErrorHelp(code:string):string;
