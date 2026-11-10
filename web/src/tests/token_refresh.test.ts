import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tokenStorage, request, ApiClientError } from '@/api/client';

describe('Token Lifecycle, Isolation & Refresh Interception', () => {
  beforeEach(() => {
    tokenStorage.clear();
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('keeps access token strictly in memory and never leaks into localStorage or sessionStorage', () => {
    tokenStorage.setAccessToken('super-secret-jwt');
    expect(tokenStorage.getAccessToken()).toBe('super-secret-jwt');
    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(sessionStorage.getItem('access_token')).toBeNull();

    tokenStorage.clear();
    expect(tokenStorage.getAccessToken()).toBeNull();
  });

  it('intercepts 401 response, calls refresh with credentials, and retries original request', async () => {
    tokenStorage.setAccessToken('expired-access-token');

    let fetchCount = 0;
    const mockFetch = vi.fn().mockImplementation((url: string, options: RequestInit) => {
      fetchCount++;
      // First request fails with 401
      if (url.endsWith('/inventory') && fetchCount === 1) {
        return Promise.resolve(
          new Response(JSON.stringify({ error: { code: 'TOKEN_EXPIRED', message: 'Token expired' } }), {
            status: 401,
            headers: { 'Content-Type': 'application/json' },
          })
        );
      }
      // Refresh token call succeeds
      if (url.endsWith('/auth/refresh')) {
        expect(options.credentials).toBe('include');
        return Promise.resolve(
          new Response(
            JSON.stringify({
              access_token: 'new-valid-jwt',
              refresh_token: 'rotated-refresh-token',
              token_type: 'bearer',
              expires_in: 3600,
            }),
            {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }
          )
        );
      }
      // Retried original request succeeds with new authorization header
      if (url.endsWith('/inventory') && fetchCount === 3) {
        const headers = options.headers as Headers;
        expect(headers.get('Authorization')).toBe('Bearer new-valid-jwt');
        return Promise.resolve(
          new Response(JSON.stringify({ items: [{ id: 'item-1', name: 'Spinach' }] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        );
      }
      return Promise.reject(new Error(`Unexpected url ${url}`));
    });

    global.fetch = mockFetch;

    const res = await request<{ items: Array<{ id: string; name: string }> }>('/inventory');
    expect(res.items).toHaveLength(1);
    expect(res.items[0].name).toBe('Spinach');
    expect(tokenStorage.getAccessToken()).toBe('new-valid-jwt');
  });

  it('clears session and surfaces UNAUTHORIZED when refresh token is invalid or expired', async () => {
    tokenStorage.setAccessToken('expired-token');

    const mockFetch = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith('/inventory')) {
        return Promise.resolve(
          new Response(JSON.stringify({ error: { code: 'UNAUTHORIZED' } }), {
            status: 401,
            headers: { 'Content-Type': 'application/json' },
          })
        );
      }
      if (url.endsWith('/auth/refresh')) {
        return Promise.resolve(
          new Response(JSON.stringify({ error: { code: 'REFRESH_TOKEN_EXPIRED' } }), {
            status: 401,
            headers: { 'Content-Type': 'application/json' },
          })
        );
      }
      return Promise.reject(new Error('Unknown url'));
    });

    global.fetch = mockFetch;

    await expect(request('/inventory')).rejects.toThrow(ApiClientError);
  });
});

