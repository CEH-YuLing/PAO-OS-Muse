// Closed storage-only contracts: no untrusted provider text or token fields.
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const hash=/^[0-9a-f]{64}$/;
const reasons=new Set(['ready','no_legacy_peers','legacy_already_mapped','host_telegram_must_be_off','legacy_scope_conflict','legacy_peer_limit','legacy_private_destination_required','legacy_actor_unavailable','legacy_session_scope_invalid','legacy_active_run','legacy_delivery_inflight','legacy_history_limit']);
const common=['workspace_id','peer_count','binding_count','held_delivery_count','authority','transport_active','provider_calls','history_rewritten'];
function fail(){throw new Error('telegram_mapping_response_invalid')}
function exact(value,keys){if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||keys.some(k=>!Object.hasOwn(value,k)))fail()}
function count(value,max){if(!Number.isSafeInteger(value)||value<0||value>max)fail()}
function scope(value,workspace){if(!uuid.test(workspace)||value.workspace_id!==workspace||value.authority!=='storage_only'||value.transport_active!==false||value.provider_calls!==false||value.history_rewritten!==false)fail();count(value.peer_count,100);count(value.binding_count,100);count(value.held_delivery_count,20000);if(value.binding_count>value.peer_count)fail()}
export function legacyPreview(value,workspace){
 exact(value,[...common,'eligible','reason','expected_version','preview_hash','peers']);scope(value,workspace);
 if(typeof value.eligible!=='boolean'||!reasons.has(value.reason)||value.expected_version!==0||!Array.isArray(value.peers)||value.peers.length!==value.peer_count)fail();
 if(value.eligible){if(value.reason!=='ready'||value.peer_count===0||!hash.test(value.preview_hash)||typeof value.preview_hash!=='string')fail()}
 else if(value.reason==='ready'||value.preview_hash!==null||value.peer_count||value.binding_count||value.held_delivery_count)fail();
 const ids=new Set();let bound=0;
 for(const peer of value.peers){exact(peer,['source_peer_id','actor_id','telegram_user_id','chat_id','bound']);if(!uuid.test(peer.source_peer_id)||!uuid.test(peer.actor_id)||typeof peer.telegram_user_id!=='string'||!(/^[1-9][0-9]{0,15}$/).test(peer.telegram_user_id)||peer.chat_id!==peer.telegram_user_id||typeof peer.bound!=='boolean'||ids.has(peer.source_peer_id))fail();ids.add(peer.source_peer_id);bound+=Number(peer.bound)}
 if(bound!==value.binding_count)fail();return value;
}
export function legacyMapping(value,workspace){
 if(value===null)return null;exact(value,[...common,'mapping_id','connection_id','owner_id','version','status']);scope(value,workspace);
 if(!uuid.test(value.mapping_id)||!uuid.test(value.connection_id)||!uuid.test(value.owner_id)||value.peer_count===0||!((value.status==='staged'&&value.version===1)||(value.status==='revoked'&&value.version===2)))fail();return value;
}
export function legacyRequest(workspace,action,value,key){
 if(!uuid.test(key))fail();const base='/v1/telegram/legacy/'+workspace;
 if(action==='apply'){const preview=legacyPreview(value,workspace);if(!preview.eligible)fail();return {path:base+'/apply',method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_key:key,expected_version:0,preview_hash:preview.preview_hash,data_only_ack:true,no_history_replay_ack:true})}}
 if(action==='revoke'){const mapping=legacyMapping(value,workspace);if(!mapping||mapping.status!=='staged')fail();return {path:base+'/revoke',method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_key:key,mapping_id:mapping.mapping_id,version:mapping.version,no_legacy_fallback_ack:true})}}
 fail();
}
export function legacyReason(reason){return ({ready:'Có thể tạo thế hệ kết nối mới, đang tắt.',no_legacy_peers:'Không có peer Telegram cũ cần chuyển. Không tạo kết nối giả.',legacy_already_mapped:'Bot cũ đã được chuyển; không thể quay lại transport dùng chung.',host_telegram_must_be_off:'Phải tắt bot dùng chung trước khi chuyển.',legacy_scope_conflict:'Dữ liệu cũ chưa thuộc một SME duy nhất. Cần xử lý phạm vi trước.',legacy_active_run:'Có tác vụ cũ đang chạy; chờ kết thúc trước.',legacy_delivery_inflight:'Có lượt gửi đang xử lý; chưa được chuyển.'})[reason]||'Dữ liệu cũ chưa đủ điều kiện an toàn để chuyển; cần kiểm tra quyền và phạm vi.'}
export function legacyError(){return 'Chưa xác định kết quả cuối. Đã bỏ bản xem trước và xác nhận; thao tác bị khóa. Chờ request kết thúc rồi Đọc lại chuyển đổi Telegram để đối chiếu. Không tự gửi lại.'}
