export type AgyView={status:'catalog_available'|'not_checked';models:string[];busy:boolean};
export function agyPath(workspace:string,action?:string):string;
export function agyView(value:unknown,workspace:string,actor:string):AgyView;
export function agyError(code:string):string;
export function agySmoke(value:unknown,workspace:string,actor:string):string;
