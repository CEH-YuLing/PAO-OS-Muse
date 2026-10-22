export const settingsTabs = ['general','organization','team','capabilities','integrations','ai','safety','system'];
import {normalizeConnectionPlatform} from './connection-catalog.mjs';
export {connectionPlatforms} from './connection-catalog.mjs';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function readBusinessLocation(search, workspace) {
  const query=new URLSearchParams(search);
  if(query.get('sme')!==workspace)return {brand:'',plan:''};
  return {brand:uuid.test(query.get('brand')||'')?query.get('brand'):'',plan:uuid.test(query.get('plan')||'')?query.get('plan'):''};
}
export function businessLocationUrl(url, workspace, brand='', plan='') {
  const result=new URL(url);result.searchParams.set('sme',workspace);
  for(const [key,value] of [['brand',brand],['plan',plan]]){if(uuid.test(value))result.searchParams.set(key,value);else result.searchParams.delete(key);}
  return result.pathname+result.search+result.hash;
}
export function readSettingsNavigation(search) {
  const query = new URLSearchParams(search);
  return {tab: settingsTabs.includes(query.get('tab')) ? query.get('tab') : 'general',
    platform: normalizeConnectionPlatform(query.get('platform'))};
}
export function settingsNavigationUrl(url, selection) {
  const result = new URL(url);
  result.searchParams.set('tab', selection.tab);
  if (selection.tab === 'integrations') result.searchParams.set('platform', selection.platform);
  else result.searchParams.delete('platform');
  if(selection.section)result.searchParams.set('section',selection.section);else result.searchParams.delete('section');
  if(selection.tab==='ai'&&(!selection.section||selection.section==='providers')&&selection.modelConnection)
    result.searchParams.set('model_connection',selection.modelConnection==='api'?'api':'client');
  else result.searchParams.delete('model_connection');
  return result.pathname + result.search + result.hash;
}
export function modelGrantEligible(grant, reference, actor, workspace, brand, now = Date.now()) {
  return reference.kind === 'model' && reference.status === 'staged' && reference.workspace_id === workspace &&
    grant.workspace_id === workspace && grant.reference_id === reference.id && grant.reference_revision === reference.revision &&
    grant.grantee_id === actor && grant.status === 'staged' && grant.model_consent_recorded === true &&
    grant.brand_id === brand && Date.parse(grant.expires_at) > now;
}
