export type SettingsTeam={members:{id:string;email:string;role:'owner'|'admin'|'operator'|'analyst'}[];brands:{id:string;name:string}[];has_more:boolean};
export function settingsTeam(value:unknown):SettingsTeam;
