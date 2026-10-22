export type MetaHostStatus={app_id:string;api_version:string;redirect_uri:string;secret_present:boolean;revision:string;restart_required:boolean;write_enabled:boolean;autopilot_enabled:boolean;scope:'installation_local'};
export function metaAppCallback(value:string):string;
export function metaAppStatus(value:unknown):MetaHostStatus;
export function metaAppPayload(status:MetaHostStatus,draft:{appId:string;version:string;callback:string;secret:string}):{app_id:string;api_version:string;redirect_uri:string;revision:string;app_secret?:string};
export function metaAppError(code:string):string;
