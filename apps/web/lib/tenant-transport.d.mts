export type TenantTicket = {revision: number; controller: AbortController};
export function createTenantTransport(): {
  ticket(): TenantTicket;
  assert(ticket: TenantTicket): void;
  invalidate(): number;
  request(ticket: TenantTicket, path: string, init?: RequestInit, fetcher?: typeof fetch): Promise<Response>;
  objectUrl(ticket: TenantTicket, blob: Blob): string;
  releaseUrl(url: string): void;
};
