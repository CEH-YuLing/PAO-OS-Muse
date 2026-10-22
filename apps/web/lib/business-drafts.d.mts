export function businessDraftKey(actor:string, workspace:string, brand:string, role:string):string;
export function saveBusinessDraft(key:string,value:unknown,now?:number):void;
export function readBusinessDraft(key:string,now?:number):unknown;
export function discardBusinessDraft(key:string):void;
export function clearBusinessDrafts():void;
