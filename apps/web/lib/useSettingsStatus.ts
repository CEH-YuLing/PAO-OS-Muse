"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from './PaoRuntimeContext';
import {collectSettingsStatus} from './settings-status.mjs';

export function useSettingsStatus(workspace:string){
  const {apiRaw}=usePao(),epoch=useRef(0),controller=useRef<AbortController|null>(null);
  const [data,setData]=useState<Record<string,unknown>>({}),[failed,setFailed]=useState<string[]>([]);
  const [loading,setLoading]=useState(true),[observed,setObserved]=useState('');
  const load=useCallback(async()=>{
    const ticket=++epoch.current;controller.current?.abort();const abort=new AbortController();controller.current=abort;
    // Drop all old observations first, including successful rows from a former refresh.
    setData({});setFailed([]);setObserved('');setLoading(true);
    if(!workspace){setLoading(false);return}
    const result=await collectSettingsStatus(workspace,async path=>{
      const response=await apiRaw(path,{signal:AbortSignal.any([abort.signal,AbortSignal.timeout(15000)])});
      return response.json();
    });
    if(ticket!==epoch.current||abort.signal.aborted)return;
    setData(result.data);setFailed(result.failed);setObserved(new Date().toLocaleString('vi-VN'));setLoading(false);
  },[apiRaw,workspace]);
  useEffect(()=>{const localEpoch=epoch,localController=controller;void load();return()=>{localEpoch.current++;localController.current?.abort()}},[load]);
  return {data,failed,loading,observed,load};
}
