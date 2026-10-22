export function resolveMembership<T extends {id: string}>(memberships: T[], preferred?: string): T | null;
export function assertTenantTicket(expected: number, current: number): void;
