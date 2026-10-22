import type {components} from '../../../packages/contracts/schema';
type S=components['schemas'];
export type LegacyPreview=S['TelegramLegacyPreview'];
export type LegacyMapping=S['TelegramLegacyMappingOut'];
export function legacyPreview(value:unknown,workspace:string):LegacyPreview;
export function legacyMapping(value:unknown,workspace:string):LegacyMapping|null;
export function legacyRequest(workspace:string,action:'apply'|'revoke',value:LegacyPreview|LegacyMapping,key:string):{path:string;method:'POST';headers:{'Content-Type':'application/json'};body:string};
export function legacyReason(reason:string):string;
export function legacyError():string;
