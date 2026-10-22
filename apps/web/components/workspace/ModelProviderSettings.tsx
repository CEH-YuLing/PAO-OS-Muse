'use client';
import {useEffect,useState} from 'react';
import {SectionTabs} from './SectionNavigation';
import CloudModelSettings from './CloudModelSettings';
import ClientModelSettings from './ClientModelSettings';
import InstallationAISettings from './InstallationAISettings';
import {modelConnectionTabs,type ModelConnection} from '@/lib/model-provider-tabs.mjs';
import './model-provider-settings.css';
import './model-provider-cards.css';

export default function ModelProviderSettings({value,onChange,onDraftChange}:{value:ModelConnection;onChange:(value:ModelConnection)=>void;onDraftChange?:(dirty:boolean)=>void}){
 const [providerDirty,setProviderDirty]=useState(false),[resourceDirty,setResourceDirty]=useState(false);
 useEffect(()=>{onDraftChange?.(providerDirty||resourceDirty)},[providerDirty,resourceDirty,onDraftChange]);
 useEffect(()=>()=>onDraftChange?.(false),[onDraftChange]);
 return <section className="mp-settings" aria-label="Nhà cung cấp mô hình">
  <p className="ux-context-note">Một chủ sở hữu hoặc nhóm 2–3 người: cấu hình AI tại đây, sau đó chọn tại AI mặc định. Client được ưu tiên hiển thị; API là tùy chọn. Không cần mời nhân sự để bắt đầu và không tự chuyển dự phòng trả phí.</p>
  <SectionTabs id="model-connection" label="Phương thức kết nối mô hình" items={modelConnectionTabs} value={value} onChange={next=>onChange(next as ModelConnection)}/>
  <div role="tabpanel" id={'model-connection-panel-'+value} aria-labelledby={'model-connection-tab-'+value}>
   {value==='client'?<ClientModelSettings onDraftChange={setProviderDirty}/>:<CloudModelSettings onDraftChange={setProviderDirty}/>}
  </div>
  <InstallationAISettings onDraftChange={setResourceDirty}/>
 </section>;
}
