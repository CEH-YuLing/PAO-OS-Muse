export type MuseView={revision:number;connected:boolean;can_manage:boolean;models:{model:string;display_name:string;reasoning_efforts:string[];default_effort:string|null}[];observed_at?:string;account_state?:string;binary_version?:string;scope:'installation';connection_mode:'catalog_only'|'text_adapter';inference_enabled:boolean;inference_verified:false;credentials_stored_in_PAO:false};
export function museStatus(value:unknown):MuseView;
export function museError(message:string):string;
export type MuseLogin={status:string;verification_url?:string;user_code?:string};
export function museLogin(value:unknown):MuseLogin;
