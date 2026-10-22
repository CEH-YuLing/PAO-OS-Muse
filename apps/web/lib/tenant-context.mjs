// A saved preference is not authority. Resolve only against /v1/me membership.
export function resolveMembership(memberships, preferred = '') {
  if (preferred) return memberships.find(member => member.id === preferred) || null;
  return memberships.length === 1 ? memberships[0] : null;
}

export function assertTenantTicket(expected, current) {
  if (expected !== current) throw new Error('Ngữ cảnh doanh nghiệp đã thay đổi; kết quả cũ bị loại bỏ.');
}
