export type CodexModels={version:number;current_model:string;models:{model:string;is_default:boolean}[];consent_required:boolean};
export function codexModelPath(wid:string,cid:string,action:'model'|'models'):string;
export function codexModels(value:unknown,wid:string,uid:string,cid:string):CodexModels;
