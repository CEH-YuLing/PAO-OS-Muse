export type TelegramConnection={id:string;workspace_id:string;bot_user_id:string|null;kind:string;generation:number;status:string;mode:string;editable:boolean;identity_verified:boolean;live_accepted:boolean};
export type TelegramConnections={workspace_id:string;runtime_available:boolean;can_manage:boolean;can_pair:boolean;connections:TelegramConnection[]};
export type TelegramTeam={peers:{id:string;user_id:string;telegram_user_id:string;version:number;enabled:boolean;allow_chat:boolean;allow_reports:boolean}[];pairings:{id:string;status:string;expected_user_id:string;observed_user_id:string|null;expired:boolean;expires_at:string}[]};
export function telegramConnections(value:unknown,workspace:string):TelegramConnections;
export function telegramTeam(value:unknown):TelegramTeam;
export function pairingCommand(value:unknown):string;
export function telegramError(code?:string):string;
export function telegramState(code:string):string;
