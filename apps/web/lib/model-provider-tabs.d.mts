export type ModelConnection='client'|'api';
export const modelConnectionTabs:{id:ModelConnection;label:string;description:string}[];
export const clientProviders:{id:string;name:string;detail:string;metadata:boolean}[];
export function readModelConnection(search:string):ModelConnection;
export function cliProfilesPath(workspace:string):string;
export type CliProfile={id:string;model:string;version:number;status:string;authentication_ready:boolean;profile_operation_pending:boolean};
export function cliProfileRows(value:unknown,workspace:string,actor:string):CliProfile[];
export function cliProfileLabel(row:CliProfile):string;
