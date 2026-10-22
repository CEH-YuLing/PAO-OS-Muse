export const settingsTabs:string[];
export const connectionPlatforms:string[];
export function readBusinessLocation(search:string,workspace:string):{brand:string;plan:string};
export function businessLocationUrl(url:string,workspace:string,brand?:string,plan?:string):string;
export function readSettingsNavigation(search:string):{tab:string;platform:string};
export function settingsNavigationUrl(url:string,selection:{tab:string;platform:string;section?:string;modelConnection?:'client'|'api'}):string;
export function modelGrantEligible(grant:any,reference:any,actor:string,workspace:string,brand:string|null,now?:number):boolean;
