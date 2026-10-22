export type WorkspaceAiConnection={id:string;provider:string;model:string;status:string;selected:boolean;available:boolean;is_default:boolean};
export type WorkspaceAiPolicy={workspace_id:string;revision:number;enabled:boolean;can_manage:boolean;connections:WorkspaceAiConnection[];default_connection_id:string|null};
export type WorkspaceAiDraft={selected:string[];defaultId:string;enabled:boolean;suggested:boolean};
export function workspaceAiPolicy(value:unknown,workspace:string):WorkspaceAiPolicy;
export function workspaceAiDraft(policy:WorkspaceAiPolicy):WorkspaceAiDraft;
export function workspaceAiSave(policy:WorkspaceAiPolicy,draft:WorkspaceAiDraft,requestKey:string,ack:boolean):{request_key:string;expected_revision:number;enabled:boolean;connection_ids:string[];default_connection_id:string|null;allow_enterprise_inference_ack:boolean};
export function workspaceAiSettingsUrl(workspace:string,section?:'access'|'providers'|'members',method?:'client'|'api'):string;
