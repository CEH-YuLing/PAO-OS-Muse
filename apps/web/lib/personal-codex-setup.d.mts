export type PersonalCodexView={workspace_id:string;actor_id:string;revision:number;enabled:boolean;make_default:boolean;ready:boolean;connection_id:string|null;connections:{id:string;model:string;status:string;authentication_ready:boolean;operation_pending:boolean}[]};
export function personalCodexPath(workspace:string):string;
export function personalCodexView(value:unknown,workspace:string,actor:string):PersonalCodexView;
export function personalCodexSave(value:PersonalCodexView,draft:{enabled:boolean;makeDefault:boolean;connection:string},requestKey:string,ack:boolean):{request_key:string;expected_revision:number;connection_id:string|null;enabled:boolean;make_default:boolean;allow_personal_inference_ack:boolean};
export function connectPersonalCodex(request:(path:string,method?:string,body?:unknown)=>Promise<unknown>,workspace:string,actor:string,connection:string,requestKey:string,isCurrent:()=>boolean):Promise<PersonalCodexView>;
