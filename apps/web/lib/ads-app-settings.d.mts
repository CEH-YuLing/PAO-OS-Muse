import type {AdsProvider} from './ads-settings.mjs';
export type AppStatus={workspace_id:string;provider:AdsProvider;mode:'managed'|'byo';revision:number;explicit_selection:boolean;client_id:string;api_version:string;redirect_uri:string;secret_present:boolean;developer_token_present:boolean;login_customer_id:string;platform_enabled:boolean;configured:boolean;external_verified:boolean;reconnect_required:boolean};
export function appStatus(value:unknown,workspace:string,provider:AdsProvider):AppStatus;
export function appPayload(status:AppStatus,form:{mode:'managed'|'byo';clientId:string;secret:string;apiVersion:string;developerToken:string;loginId:string}):Record<string,unknown>;
export function appError(code:string):string;
