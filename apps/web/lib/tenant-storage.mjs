const segment = value => encodeURIComponent(value).replaceAll('.', '%2E');
export function scopedStorageKey(actor, workspace, kind, resource = '') {
  if (!actor || !workspace) throw new Error('Chưa chọn ngữ cảnh doanh nghiệp.');
  return 'pao.scope.v1.' + [actor, workspace, kind, resource].map(segment).join('.');
}

export function clearActorStorage(storage, actor) {
  if (!actor) return;
  const prefix = 'pao.scope.v1.' + segment(actor) + '.';
  const keys = [];
  for (let index = 0; index < storage.length; index++) {
    const key = storage.key(index);
    if (key?.startsWith(prefix)) keys.push(key);
  }
  for (const key of keys) storage.removeItem(key);
}
