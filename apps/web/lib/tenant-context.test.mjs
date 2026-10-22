import {test} from 'node:test';
import assert from 'node:assert/strict';
import {resolveMembership, assertTenantTicket} from './tenant-context.mjs';

const memberships = [{id: 'a', role: 'owner'}, {id: 'b', role: 'viewer'}];
test('multiple SMEs require selection; single SME can initialize explicitly', () => {
  assert.equal(resolveMembership(memberships), null);
  assert.equal(resolveMembership([]), null);
  assert.deepEqual(resolveMembership([memberships[0]]), memberships[0]);
});
test('stored selection preserves the selected SME role, not first membership', () => {
  assert.deepEqual(resolveMembership(memberships, 'b'), memberships[1]);
});
test('tampered or revoked stored selection never falls back silently', () => {
  assert.equal(resolveMembership(memberships, 'outsider'), null);
  assert.equal(resolveMembership([memberships[0]], 'b'), null);
});
test('late response from another tenant generation is rejected', () => {
  assert.doesNotThrow(() => assertTenantTicket(2, 2));
  assert.throws(() => assertTenantTicket(1, 2), /kết quả cũ/);
});
