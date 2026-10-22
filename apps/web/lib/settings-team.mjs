const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const plain=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const closed=(value,keys)=>plain(value)&&Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));
const text=value=>typeof value==='string'&&value.length>0&&value.length<=512&&!/[\x00-\x1f\x7f]/.test(value);
// Native /options is a bounded list of eligible grantees, NOT a full HR roster.
export function settingsTeam(value){
 if(!closed(value,['members','brands','has_more'])||typeof value.has_more!=='boolean'||!Array.isArray(value.members)||!Array.isArray(value.brands)||value.members.length>100||value.brands.length>100)throw new Error('settings_team_invalid');
 const seen=new Set(),brands=new Set();
 for(const row of value.members){
  if(!closed(row,['id','email','role'])||typeof row.id!=='string'||!uuid.test(row.id)||seen.has(row.id)||!text(row.email)||!['owner','admin','operator','analyst'].includes(row.role))throw new Error('settings_team_invalid');
  seen.add(row.id);
 }
 for(const row of value.brands){
  if(!closed(row,['id','name'])||typeof row.id!=='string'||!uuid.test(row.id)||brands.has(row.id)||!text(row.name))throw new Error('settings_team_invalid');
  brands.add(row.id);
 }
 return value;
}
