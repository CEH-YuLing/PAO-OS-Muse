export type CodexLogin={connection_id:string;operation_id:string|null;version:number;status:string;expires_in:number;user_code:string|null;verification_url:string|null};
export function codexLoginPath(workspace:string,connection?:string,action?:string):string;
export function codexLoginCapability(value:unknown):boolean;
export function codexLoginView(value:unknown,connection:string):CodexLogin;
export const codexLoginLabels:Record<string,string>;
