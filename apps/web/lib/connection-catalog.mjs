// Presentation-only taxonomy. An entry is not an installed/healthy connector.
export const connectionGroups = [
 {id:'ads',name:'Tài nguyên quảng cáo',description:'Ứng dụng, tài khoản và quyền quảng cáo',defaultPlatform:'meta'},
 {id:'bots',name:'Hệ thống BOT',description:'Bot, đội ngũ và kênh làm việc',defaultPlatform:'telegram'},
 {id:'plugins',name:'Ứng dụng và plugin',description:'Kho ứng dụng theo lĩnh vực',defaultPlatform:'plugins_all'},
 {id:'mcp',name:'MCP / Công cụ',description:'Máy chủ MCP riêng và quyền công cụ',defaultPlatform:'mcp'},
];
export const connectionItems = [
 {id:'meta',group:'ads',name:'Meta Ads',hint:'Ứng dụng và tài khoản',implemented:true},
 {id:'tiktok',group:'ads',name:'TikTok Ads',hint:'Vị trí chờ',implemented:false},
 {id:'google',group:'ads',name:'Google Ads',hint:'Ứng dụng và tài khoản',implemented:true},
 {id:'gpt_ads',group:'ads',name:'GPT Ads',hint:'Vị trí chờ',implemented:false},
 {id:'telegram',group:'bots',name:'Telegram Bot',hint:'Bot và đội ngũ',implemented:true},
 {id:'zalo_bot',group:'bots',name:'Zalo Bot',hint:'Vị trí chờ',implemented:false},
 {id:'lark',group:'bots',name:'Lark / Feishu',hint:'Vị trí chờ',implemented:false},
 {id:'discord',group:'bots',name:'Discord',hint:'Vị trí chờ',implemented:false},
 {id:'slack',group:'bots',name:'Slack',hint:'Vị trí chờ',implemented:false},
 {id:'whatsapp',group:'bots',name:'WhatsApp',hint:'Vị trí chờ',implemented:false},
 {id:'plugins_all',group:'plugins',name:'Kho ứng dụng',hint:'Tất cả mục quy hoạch',implemented:false},
 {id:'plugins_sales',group:'plugins',name:'Bán hàng',hint:'Danh mục chờ',implemented:false},
 {id:'plugins_social',group:'plugins',name:'Mạng xã hội',hint:'Danh mục chờ',implemented:false},
 {id:'plugins_marketing',group:'plugins',name:'Marketing',hint:'Danh mục chờ',implemented:false},
 {id:'plugins_messaging',group:'plugins',name:'Nhắn tin',hint:'Danh mục chờ',implemented:false},
 {id:'plugins_advertising',group:'plugins',name:'Quảng cáo',hint:'Danh mục chờ',implemented:false},
 {id:'plugins_creative',group:'plugins',name:'Sáng tạo',hint:'Danh mục chờ',implemented:false},
 {id:'plugins_office',group:'plugins',name:'Văn phòng',hint:'Danh mục chờ',implemented:false},
 {id:'plugins_website',group:'plugins',name:'Website',hint:'Danh mục chờ',implemented:false},
 {id:'mcp',group:'mcp',name:'MCP / Công cụ',hint:'Máy chủ và quyền',implemented:true},
];
export const pluginApps = [
 {id:'haravan',name:'Haravan',category:'plugins_sales'},
 {id:'pancake',name:'Pancake',category:'plugins_sales'},
 {id:'sapo',name:'Sapo',category:'plugins_sales'},
 {id:'botcake',name:'Botcake',category:'plugins_messaging'},
 {id:'zalo_oa',name:'Zalo OA',category:'plugins_messaging'},
 {id:'webcake',name:'Webcake',category:'plugins_website'},
 {id:'ladipage',name:'Ladipage',category:'plugins_website'},
];
const aliases={botcake:'plugins_messaging',zalo:'plugins_messaging'};
export const connectionPlatforms=connectionItems.map(item=>item.id);
export function normalizeConnectionPlatform(value){
 if(typeof value!=='string')return 'meta';
 if(Object.hasOwn(aliases,value))return aliases[value];
 return connectionPlatforms.includes(value)?value:'meta';
}
export function connectionItem(value){return connectionItems.find(item=>item.id===normalizeConnectionPlatform(value));}
export function itemsInGroup(group){return connectionItems.filter(item=>item.group===group);}
export function appsInCategory(category){return category==='plugins_all'?[...pluginApps]:pluginApps.filter(app=>app.category===category);}
export function tabTarget(key,index,length){
 if(!Number.isInteger(length)||length<1||!Number.isInteger(index)||index<0||index>=length)return null;
 return key==='ArrowRight'?(index+1)%length:key==='ArrowLeft'?(index+length-1)%length:key==='Home'?0:key==='End'?length-1:null;
}
