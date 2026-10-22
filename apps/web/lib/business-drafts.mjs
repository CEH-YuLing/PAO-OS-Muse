// Business authoring only; never persist credentials, grants, approvals or runs.
const drafts = new Map();
const TTL = 30 * 60 * 1000;
export function businessDraftKey(actor, workspace, brand, role) {
  return JSON.stringify([actor, workspace, brand || '', role]);
}
export function saveBusinessDraft(key, value, now = Date.now()) {
  drafts.delete(key);
  drafts.set(key, {value: structuredClone(value), expires: now + TTL});
  while (drafts.size > 20) drafts.delete(drafts.keys().next().value);
}
export function readBusinessDraft(key, now = Date.now()) {
  const row = drafts.get(key);
  if (!row || row.expires <= now) {drafts.delete(key); return null;}
  return structuredClone(row.value);
}
export function discardBusinessDraft(key) {drafts.delete(key);}
export function clearBusinessDrafts() {drafts.clear();}
