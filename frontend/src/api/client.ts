/**
 * Ortak API istemcisi.
 * - X-API-Token başlığını tüm isteklere ekler (backend APP_TOKEN tanımlıysa zorunlu).
 * - Kullanıcının görebileceği hataları konsola değil dönen value üzerinden de bildirir.
 */
export const BACKEND_BASE = (typeof window !== 'undefined')
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : 'http://127.0.0.1:8000';

export const getAuthToken = (): string => {
  try {
    return localStorage.getItem('deepbi_token') || '';
  } catch {
    return '';
  }
};

export const setAuthToken = (token: string): void => {
  try {
    if (token) localStorage.setItem('deepbi_token', token);
    else localStorage.removeItem('deepbi_token');
  } catch {
    /* localStorage kapalı olabilir */
  }
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T = any>(path: string, options: RequestInit = {}, timeoutMs = 30000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };
    if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    const token = getAuthToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
      headers['X-API-Token'] = token;
    }

    const res = await fetch(`${BACKEND_BASE}${path}`, { ...options, headers, signal: controller.signal });
    if (!res.ok) {
      // Oturum süresi doldu / geçersiz — uygulama login ekranına dönmek için dinler
      if (res.status === 401) {
        try { localStorage.removeItem('deepbi_token'); } catch { /* yoksay */ }
        window.dispatchEvent(new CustomEvent('deepbi:unauthorized'));
      }
      let detail = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      } catch { /* gövde JSON değil */ }
      throw new ApiError(res.status, detail);
    }
    return await res.json() as T;
  } finally {
    clearTimeout(timer);
  }
}
