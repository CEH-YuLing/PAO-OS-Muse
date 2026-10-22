export const settingsSources:[string,string,string,string][];
export function settingsPath(path:string,scope:string,workspace:string):string;
export function validateSettingsStatus(key:string,data:unknown):unknown;
export function collectSettingsStatus(workspace:string,read:(path:string)=>Promise<unknown>):Promise<{data:Record<string,unknown>;failed:string[];responding:number}>;
export function evidenceValue(value:boolean|null|undefined):string;
export function connectionEvidence(kind:string,record:{configured:boolean;status?:string}|null):{configured:boolean|null;connected:boolean|null;healthy:null;accepted:null};
