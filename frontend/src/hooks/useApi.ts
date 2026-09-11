import { API_BASE } from '../lib/constants';

async function apiGet(path: string) {
  try {
    const r = await fetch(`${API_BASE}${path}`);
    if (r.ok) return await r.json();
  } catch {}
  return null;
}

async function apiPost(path: string, body: any) {
  try {
    const r = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (r.ok) return await r.json();
  } catch {}
  return null;
}

async function apiDelete(path: string) {
  try {
    const r = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
    return r.ok;
  } catch {
    return false;
  }
}

async function apiPut(path: string, body: any) {
  try {
    const r = await fetch(`${API_BASE}${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (r.ok) return await r.json();
  } catch {}
  return null;
}

export function useApi() {
  return { apiGet, apiPost, apiDelete, apiPut };
}
