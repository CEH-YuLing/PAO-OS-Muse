// Presentation only: model availability and execution authority remain server-side.
export const chatModelTabs = [
 {id:'client',label:'Kết nối qua Client'},
 {id:'api',label:'Kết nối qua API'},
];
export const chatModelProviders = [
 {id:'codex_cli',name:'Codex',tab:'client'},
 {id:'claude_code',name:'Claude',tab:'client'},
 {id:'antigravity',name:'Antigravity',tab:'client'},
 {id:'muse',name:'Muse',tab:'client'},
 {id:'openai',name:'OpenAI',tab:'api'},
 {id:'anthropic',name:'Claude',tab:'api'},
 {id:'gemini',name:'Google Gemini',tab:'api'},
 {id:'openrouter',name:'OpenRouter',tab:'api'},
];
export const chatEffortLabels = {none:'Tắt suy luận tùy chọn',minimal:'Tối thiểu',low:'Thấp',medium:'Trung bình',high:'Cao',xhigh:'Rất cao',max:'Tối đa',ultra:'Chuyên sâu'};
export const chatModelKey = value => JSON.stringify(value.installation_resource_id
 ?[value.provider,value.model,null,null,null,value.installation_resource_id]
 :value.personal_cli_source_id?[value.provider,value.model,null,null,value.personal_cli_source_id]
 :value.enterprise_source_id?[value.provider,value.model,value.grant_id||null,value.enterprise_source_id]
 :[value.provider,value.model,value.grant_id||null]);

export function chatProviderName(provider){
 const found=chatModelProviders.find(row=>row.id===provider);
 return found?`${found.tab==='api'?'API-':''}${found.name}`:provider==='ollama'?'Ollama':provider;
}
export function chatModelSummary(value){
 return value?`${chatProviderName(value.provider)} — ${value.model}`:'Chưa chọn mô hình';
}
export function chatModelOptions(catalog,grants,current){
 const options=new Map();
 for(const engine of catalog?.engines||[]){
  if(engine.error)continue;
  for(const model of engine.models){
   const selection={provider:engine.provider,model,
    ...(engine.enterprise_source_id?{enterprise_source_id:engine.enterprise_source_id}:{}),
    ...(engine.personal_cli_source_id?{personal_cli_source_id:engine.personal_cli_source_id}:{}),
    ...(engine.installation_resource_id?{installation_resource_id:engine.installation_resource_id}:{}),
   };
   const detail=engine.model_details?.find(row=>row.model===model);
   const origin=engine.installation_resource_id?'AI dùng chung':engine.personal_cli_source_id?'Cá nhân':engine.enterprise_source_id?'Doanh nghiệp':engine.local?'Trên máy':'Kết nối API';
   options.set(chatModelKey(selection),{key:chatModelKey(selection),selection,label:detail?.display_name||model,detail,origin,available:detail?.model_capabilities?.chat_supported!==false});
  }
 }
 if(catalog?.scope!=='installation')for(const grant of grants?.items||[]){
  const selection={provider:grant.provider,model:grant.model,grant_id:grant.grant_id};
  options.set(chatModelKey(selection),{key:chatModelKey(selection),selection,label:grant.model,origin:'Quyền cũ',available:true});
 }
 if(current&&!options.has(chatModelKey(current))){
  options.set(chatModelKey(current),{key:chatModelKey(current),selection:current,label:current.model,origin:'Đã lưu · Cần kiểm tra lại nguồn',available:false});
 }
 return [...options.values()];
}
export function filterChatModels(options,query,modality='all'){
 const value=query.trim().toLocaleLowerCase('vi');
 return options.filter(row=>`${row.label} ${row.selection.model} ${chatProviderName(row.selection.provider)}`.toLocaleLowerCase('vi').includes(value)
  &&(modality==='all'||modality==='unknown'&&!row.detail?.model_capabilities?.output_modalities?.length||row.detail?.model_capabilities?.output_modalities?.includes(modality)));
}
