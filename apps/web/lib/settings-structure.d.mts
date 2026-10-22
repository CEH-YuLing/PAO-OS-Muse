export const settingsGroups:{id:string;label:string;description:string}[];
export const settingsSections:Record<string,{id:string;label:string}[]>;
export function settingsSection(group:string,value:string|null):string;
