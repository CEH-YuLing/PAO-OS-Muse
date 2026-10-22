"use client";
import InstallationAISettings from './InstallationAISettings';
import {usePao} from '@/lib/PaoRuntimeContext';
export default function ModelAccessPanel({onDraftChange}:{onDraftChange?:(dirty:boolean)=>void}){const {activeWorkspace,me}=usePao();return <WorkspaceModelAccess key={`${activeWorkspace?.id}:${me?.id}:${activeWorkspace?.role}`} onDraftChange={onDraftChange}/>}
function WorkspaceModelAccess({onDraftChange}:{onDraftChange?:(dirty:boolean)=>void}){return <InstallationAISettings onDraftChange={onDraftChange}/>}
