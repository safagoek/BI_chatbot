import React, { useCallback, useEffect, useState } from 'react';
import {
  User as UserIcon,
  Cpu,
  Database,
  Users as UsersIcon,
  Plug,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  Plus,
  Trash2,
  KeyRound,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  ShieldAlert,
  Save,
  RefreshCw,
  ScrollText,
  CalendarClock,
  Mail,
} from 'lucide-react';
import { useBIStore } from '../context/store';
import { apiFetch, ApiError } from '../api/client';
import SourceManager from './SourceManager';

/* ────────────────────────────────────────────────────────────
   Types
   ──────────────────────────────────────────────────────────── */

interface AdminUser {
  id: string;
  username: string;
  display_name: string;
  role: 'admin' | 'user';
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  source_ids: string[] | null;
}

interface SettingsPayload {
  apiKey: string;
  baseUrl: string;
  model: string;
  apiKeyMasked?: boolean;
}

interface SimpleSource {
  id: string;
  type: string;
  display_name: string;
  is_active: boolean;
  labels: string[];
}

interface McpServer {
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  description?: string;
}

interface McpConfig {
  mcpServers: Record<string, McpServer>;
}

interface AuditItem {
  id: string;
  created_at: string;
  user_id: string | null;
  username: string | null;
  action: string;
  target: string | null;
  detail: Record<string, unknown> | null;
  request_id: string | null;
  ip: string | null;
}

interface AuditResponse {
  items: AuditItem[];
  total: number;
  limit: number;
  offset: number;
}

interface ScheduleRow {
  id: string;
  title: string;
  question: string;
  source_ids: string[];
  relationships: unknown;
  frequency: 'daily' | 'weekly';
  hour: number;
  day_of_week: number;
  email: string | null;
  active: boolean;
  last_run_at: string | null;
  last_status: string | null;
}

type Section =
  | 'account'
  | 'model'
  | 'sources'
  | 'mysources'
  | 'users'
  | 'mcp'
  | 'audit'
  | 'schedules';

/* ────────────────────────────────────────────────────────────
   Shared styling helpers (Linear/Vercel dark idiom)
   ──────────────────────────────────────────────────────────── */

const cardStyle: React.CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 12,
  padding: 18,
};

const labelStyle: React.CSSProperties = {
  fontSize: 10.5,
  fontWeight: 600,
  color: 'var(--color-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 34,
  padding: '0 12px',
  borderRadius: 8,
  border: '1px solid var(--color-border)',
  background: 'var(--color-surface2)',
  color: 'var(--color-text)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
};

const primaryBtn: React.CSSProperties = {
  height: 32,
  padding: '0 14px',
  borderRadius: 8,
  border: 'none',
  cursor: 'pointer',
  background: 'var(--color-accent)',
  color: '#fff',
  fontSize: 12,
  fontWeight: 600,
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  transition: 'background 150ms ease',
};

const ghostBtn: React.CSSProperties = {
  height: 28,
  padding: '0 10px',
  borderRadius: 7,
  border: '1px solid var(--color-border)',
  cursor: 'pointer',
  background: 'transparent',
  color: 'var(--color-text-2)',
  fontSize: 11.5,
  fontWeight: 500,
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  transition: 'background 150ms ease',
};

const Alert: React.FC<{ kind: 'ok' | 'err' | 'info'; children: React.ReactNode }> = ({ kind, children }) => {
  const palette = {
    ok: { bg: 'var(--color-success-subtle)', bd: 'rgba(52,211,153,0.25)', fg: 'var(--color-success)' },
    err: { bg: 'var(--color-danger-subtle)', bd: 'rgba(239,68,68,0.25)', fg: 'var(--color-danger)' },
    info: { bg: 'var(--color-accent-subtle)', bd: 'var(--color-accent-subtle2)', fg: 'var(--color-accent-fg)' },
  }[kind];
  const Icon = kind === 'ok' ? CheckCircle2 : kind === 'err' ? AlertCircle : ShieldCheck;
  return (
    <div
      className="flex items-center gap-2"
      style={{
        padding: '8px 10px',
        borderRadius: 8,
        background: palette.bg,
        border: `1px solid ${palette.bd}`,
        color: palette.fg,
        fontSize: 11.5,
      }}
    >
      <Icon size={14} style={{ flexShrink: 0 }} />
      <span>{children}</span>
    </div>
  );
};

const RoleChip: React.FC<{ role: 'admin' | 'user' }> = ({ role }) => (
  <span
    style={{
      fontSize: 10,
      fontWeight: 600,
      padding: '2px 8px',
      borderRadius: 6,
      background: role === 'admin' ? 'var(--color-accent-subtle)' : 'var(--color-surface2)',
      border: `1px solid ${role === 'admin' ? 'var(--color-accent-subtle2)' : 'var(--color-border)'}`,
      color: role === 'admin' ? 'var(--color-accent-fg)' : 'var(--color-muted)',
    }}
  >
    {role === 'admin' ? 'admin' : 'kullanıcı'}
  </span>
);

const friendlyError = (e: unknown, fallback: string): string => {
  if (e instanceof ApiError) {
    switch (e.message) {
      case 'INVALID_CREDENTIALS': return 'Mevcut şifre hatalı.';
      case 'PASSWORD_TOO_SHORT': return 'Şifre en az 8 karakter olmalı.';
      case 'USERNAME_TAKEN': return 'Bu kullanıcı adı zaten alınmış.';
      case 'INVALID_USERNAME': return 'Geçersiz kullanıcı adı (harf, rakam, nokta, alt çizgi).';
      case 'LAST_ADMIN': return 'Son yönetici devre dışı bırakılamaz / silinemez.';
      case 'CANNOT_DELETE_SELF': return 'Kendinizi silemezsiniz.';
      case 'INVALID_CONFIG': return 'MCP yapılandırması geçersiz.';
      default: return e.message || fallback;
    }
  }
  return fallback;
};

const fmtDateTime = (iso: string | null): string => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
};

/* ────────────────────────────────────────────────────────────
   Account section
   ──────────────────────────────────────────────────────────── */

const AccountSection: React.FC = () => {
  const user = useBIStore((s) => s.user);
  const language = useBIStore((s) => s.language);
  const tr = language !== 'en';

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  if (!user) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    if (next.length < 8) {
      setMsg({ kind: 'err', text: tr ? 'Yeni şifre en az 8 karakter olmalı.' : 'New password must be at least 8 characters.' });
      return;
    }
    if (next !== confirm) {
      setMsg({ kind: 'err', text: tr ? 'Yeni şifreler eşleşmiyor.' : 'Passwords do not match.' });
      return;
    }
    setBusy(true);
    try {
      await apiFetch('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      setMsg({ kind: 'ok', text: tr ? 'Şifre başarıyla değiştirildi.' : 'Password changed successfully.' });
      setCurrent(''); setNext(''); setConfirm('');
    } catch (err) {
      setMsg({ kind: 'err', text: friendlyError(err, tr ? 'Şifre değiştirilemedi.' : 'Failed to change password.') });
    } finally {
      setBusy(false);
    }
  };

  const field = (label: string, value: string) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={labelStyle}>{label}</span>
      <span style={{ fontSize: 13, color: 'var(--color-text)' }}>{value}</span>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 560 }}>
      <div style={cardStyle}>
        <div className="flex items-center gap-3" style={{ marginBottom: 16 }}>
          <div
            className="flex items-center justify-center"
            style={{
              width: 38, height: 38, borderRadius: 10,
              background: 'var(--color-accent-subtle)',
              color: 'var(--color-accent-fg)',
            }}
          >
            <UserIcon size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text)' }}>{user.display_name || user.username}</span>
              <RoleChip role={user.role} />
            </div>
            <span style={{ fontSize: 11.5, color: 'var(--color-muted)' }}>@{user.username}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          {field(tr ? 'Kullanıcı Adı' : 'Username', user.username)}
          {field(tr ? 'Görünen Ad' : 'Display Name', user.display_name || '—')}
          {field(tr ? 'Rol' : 'Role', user.role === 'admin' ? (tr ? 'Yönetici' : 'Admin') : tr ? 'Kullanıcı' : 'User')}
        </div>
        {user.must_change_password && (
          <div style={{ marginTop: 14 }}>
            <Alert kind="info">{tr ? 'Şifrenizi değiştirmeniz gerekiyor.' : 'You must change your password.'}</Alert>
          </div>
        )}
      </div>

      <div style={cardStyle}>
        <div className="flex items-center gap-2" style={{ marginBottom: 14 }}>
          <KeyRound size={14} style={{ color: 'var(--color-accent-fg)' }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>
            {tr ? 'Şifre Değiştir' : 'Change Password'}
          </span>
        </div>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={labelStyle}>{tr ? 'Mevcut Şifre' : 'Current Password'}</span>
            <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} style={inputStyle} placeholder="••••••••" />
          </label>
          <div style={{ display: 'flex', gap: 12 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: 1 }}>
              <span style={labelStyle}>{tr ? 'Yeni Şifre' : 'New Password'}</span>
              <input type="password" value={next} onChange={(e) => setNext(e.target.value)} style={inputStyle} placeholder={tr ? 'en az 8 karakter' : 'min 8 characters'} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: 1 }}>
              <span style={labelStyle}>{tr ? 'Yeni Şifre (Tekrar)' : 'Confirm Password'}</span>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} style={inputStyle} placeholder="••••••••" />
            </label>
          </div>
          {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
          <div>
            <button type="submit" disabled={busy || !current || !next} style={{ ...primaryBtn, opacity: busy || !current || !next ? 0.55 : 1 }}>
              {busy ? (tr ? 'Kaydediliyor…' : 'Saving…') : tr ? 'Şifreyi Güncelle' : 'Update Password'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

/* ────────────────────────────────────────────────────────────
   Model & LLM section (admin)
   ──────────────────────────────────────────────────────────── */

const LLM_PRESETS: { name: string; baseUrl: string; model: string }[] = [
  { name: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o' },
  { name: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1', model: 'google/gemini-2.5-flash' },
  { name: 'LM Studio', baseUrl: 'http://localhost:1234/v1', model: 'local-model' },
  { name: 'Ollama', baseUrl: 'http://localhost:11434/v1', model: 'llama3' },
  { name: 'Custom', baseUrl: '', model: '' },
];

const ModelSection: React.FC = () => {
  const language = useBIStore((s) => s.language);
  const tr = language !== 'en';

  const [preset, setPreset] = useState('Custom');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [storedKey, setStoredKey] = useState('');
  const [keyMasked, setKeyMasked] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<SettingsPayload>('/api/settings')
      .then((data) => {
        if (cancelled) return;
        setBaseUrl(data.baseUrl || '');
        setModel(data.model || '');
        setStoredKey(data.apiKey || '');
        setKeyMasked(Boolean(data.apiKeyMasked) || (data.apiKey || '').startsWith('••••'));
        const match = LLM_PRESETS.find((p) => p.baseUrl === data.baseUrl);
        setPreset(match ? match.name : 'Custom');
      })
      .catch(() => { if (!cancelled) setMsg({ kind: 'err', text: tr ? 'Ayarlar yüklenemedi.' : 'Failed to load settings.' }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyPreset = (name: string) => {
    setPreset(name);
    const p = LLM_PRESETS.find((x) => x.name === name);
    if (p && name !== 'Custom') {
      setBaseUrl(p.baseUrl);
      setModel(p.model);
    }
  };

  const handleSave = async () => {
    setMsg(null);
    setBusy(true);
    try {
      // Boş apiKey → mevcut (maskeli) anahtar korunur, maskeli değeri geri gönder
      const keyToSend = apiKey.trim() || storedKey;
      await apiFetch('/api/settings', {
        method: 'PUT',
        body: JSON.stringify({ apiKey: keyToSend, baseUrl, model }),
      });
      setStoredKey(keyToSend);
      setKeyMasked(true);
      setApiKey('');
      setMsg({ kind: 'ok', text: tr ? 'Model ayarları kaydedildi.' : 'Model settings saved.' });
    } catch (err) {
      setMsg({ kind: 'err', text: friendlyError(err, tr ? 'Ayarlar kaydedilemedi.' : 'Failed to save settings.') });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 560, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={cardStyle}>
        <div className="flex items-center gap-2" style={{ marginBottom: 14 }}>
          <Cpu size={14} style={{ color: 'var(--color-accent-fg)' }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>
            {tr ? 'Sağlayıcı & Model' : 'Provider & Model'}
          </span>
        </div>

        {loading ? (
          <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>{tr ? 'Yükleniyor…' : 'Loading…'}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Preset pill row */}
            <div className="flex flex-wrap" style={{ gap: 8 }}>
              {LLM_PRESETS.map((p) => (
                <button
                  key={p.name}
                  type="button"
                  onClick={() => applyPreset(p.name)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 999,
                    fontSize: 11.5,
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: preset === p.name ? 'var(--color-accent-subtle)' : 'var(--color-surface2)',
                    border: `1px solid ${preset === p.name ? 'var(--color-accent-subtle2)' : 'var(--color-border)'}`,
                    color: preset === p.name ? 'var(--color-accent-fg)' : 'var(--color-muted)',
                    transition: 'all 120ms ease',
                  }}
                >
                  {p.name}
                </button>
              ))}
            </div>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={labelStyle}>Base URL</span>
              <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} style={inputStyle} placeholder="https://api.openai.com/v1" />
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={labelStyle}>API Key</span>
              <div style={{ position: 'relative' }}>
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  style={{ ...inputStyle, paddingRight: 36 }}
                  placeholder={keyMasked ? 'kayıtlı anahtar kullanılıyor — değiştirmek için yeni anahtar girin' : 'sk-…'}
                />
                <button
                  type="button"
                  onClick={() => setShowKey((v) => !v)}
                  style={{
                    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--color-muted)', display: 'flex', padding: 4,
                  }}
                >
                  {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              {keyMasked && (
                <span style={{ fontSize: 10.5, color: 'var(--color-faint)', fontFamily: 'var(--font-mono)' }}>
                  {tr ? 'kayıtlı:' : 'stored:'} {storedKey.slice(0, 6)}…{storedKey.slice(-4)}
                </span>
              )}
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={labelStyle}>{tr ? 'Model' : 'Model'}</span>
              <input value={model} onChange={(e) => setModel(e.target.value)} style={inputStyle} placeholder="gpt-4o" />
            </label>

            {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}

            <div>
              <button type="button" onClick={handleSave} disabled={busy || !baseUrl.trim() || !model.trim()} style={{ ...primaryBtn, opacity: busy || !baseUrl.trim() || !model.trim() ? 0.55 : 1 }}>
                <Save size={13} />
                {busy ? (tr ? 'Kaydediliyor…' : 'Saving…') : tr ? 'Kaydet' : 'Save'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

/* ────────────────────────────────────────────────────────────
   Sources sections
   ──────────────────────────────────────────────────────────── */

const SourcesSection: React.FC = () => (
  <div style={{ minHeight: 480 }}>
    <SourceManager />
  </div>
);

const MySourcesSection: React.FC = () => {
  const [sources, setSources] = useState<SimpleSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    apiFetch<SimpleSource[]>('/api/sources')
      .then((data) => { if (!cancelled) setSources(Array.isArray(data) ? data : []); })
      .catch((e) => { if (!cancelled) setError(friendlyError(e, 'Kaynaklar yüklenemedi.')); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div style={{ maxWidth: 680 }}>
      <div style={cardStyle}>
        <div className="flex items-center gap-2" style={{ marginBottom: 14 }}>
          <Database size={14} style={{ color: 'var(--color-accent-fg)' }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>Veri Kaynaklarım</span>
          <span style={{ fontSize: 11, color: 'var(--color-faint)' }}>(salt okunur)</span>
        </div>
        {loading && <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>Yükleniyor…</div>}
        {error && <Alert kind="err">{error}</Alert>}
        {!loading && !error && sources.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>Size atanmış veri kaynağı yok. Yöneticinizle iletişime geçin.</div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {sources.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between"
              style={{
                padding: '10px 12px',
                borderRadius: 8,
                background: 'var(--color-surface2)',
                border: '1px solid var(--color-border)',
              }}
            >
              <div className="flex items-center gap-3" style={{ minWidth: 0 }}>
                <span
                  style={{
                    width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                    background: s.is_active ? 'var(--color-success)' : 'var(--color-faint)',
                    boxShadow: s.is_active ? '0 0 6px rgba(52,211,153,0.6)' : 'none',
                  }}
                />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.display_name}
                  </div>
                  {s.labels?.length > 0 && (
                    <div style={{ fontSize: 10.5, color: 'var(--color-faint)' }}>{s.labels.join(', ')}</div>
                  )}
                </div>
              </div>
              <span
                style={{
                  fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 6, flexShrink: 0,
                  background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                  color: 'var(--color-muted)', fontFamily: 'var(--font-mono)',
                }}
              >
                {s.type}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

/* ────────────────────────────────────────────────────────────
   Users section (admin)
   ──────────────────────────────────────────────────────────── */

const UsersSection: React.FC = () => {
  const me = useBIStore((s) => s.user);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [allSources, setAllSources] = useState<SimpleSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  // create form
  const [showCreate, setShowCreate] = useState(false);
  const [nuUsername, setNuUsername] = useState('');
  const [nuDisplay, setNuDisplay] = useState('');
  const [nuRole, setNuRole] = useState<'user' | 'admin'>('user');
  const [nuPassword, setNuPassword] = useState('');
  const [nuBusy, setNuBusy] = useState(false);
  const [createdInfo, setCreatedInfo] = useState<string | null>(null);

  // expanded row
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [resetPwd, setResetPwd] = useState('');
  const [permIds, setPermIds] = useState<Set<string>>(new Set());
  const [rowBusy, setRowBusy] = useState(false);
  const [rowSaved, setRowSaved] = useState(false);

  // two-step delete
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    try {
      const data = await apiFetch<AdminUser[]>('/api/admin/users');
      setUsers(Array.isArray(data) ? data : []);
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'Kullanıcılar yüklenemedi.') });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiFetch<AdminUser[]>('/api/admin/users'),
      apiFetch<SimpleSource[]>('/api/sources'),
    ])
      .then(([u, s]) => {
        if (cancelled) return;
        setUsers(Array.isArray(u) ? u : []);
        setAllSources(Array.isArray(s) ? s : []);
      })
      .catch((e) => { if (!cancelled) setMsg({ kind: 'err', text: friendlyError(e, 'Kullanıcılar yüklenemedi.') }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const toggleExpand = (u: AdminUser) => {
    if (expandedId === u.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(u.id);
    setResetPwd('');
    setRowSaved(false);
    setPermIds(new Set(u.source_ids ?? []));
    setConfirmDeleteId(null);
  };

  const handleCreate = async () => {
    setMsg(null);
    setCreatedInfo(null);
    if (!nuUsername.trim() || !nuPassword) return;
    setNuBusy(true);
    try {
      const res = await apiFetch<{ id: string; username: string; role: string }>('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify({
          username: nuUsername.trim(),
          password: nuPassword,
          display_name: nuDisplay.trim() || nuUsername.trim(),
          role: nuRole,
        }),
      });
      setCreatedInfo(`${res.username} — ilk şifre verildi, kullanıcı ilk girişte değiştirebilir.`);
      setNuUsername(''); setNuDisplay(''); setNuPassword(''); setNuRole('user');
      await loadUsers();
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'Kullanıcı oluşturulamadı.') });
    } finally {
      setNuBusy(false);
    }
  };

  const patchUser = async (id: string, body: Record<string, unknown>, okText: string) => {
    setMsg(null);
    setRowBusy(true);
    try {
      await apiFetch(`/api/admin/users/${id}`, { method: 'PUT', body: JSON.stringify(body) });
      setMsg({ kind: 'ok', text: okText });
      await loadUsers();
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'İşlem başarısız.') });
    } finally {
      setRowBusy(false);
    }
  };

  const handleDelete = async (id: string) => {
    setMsg(null);
    setRowBusy(true);
    try {
      await apiFetch(`/api/admin/users/${id}`, { method: 'DELETE' });
      setMsg({ kind: 'ok', text: 'Kullanıcı silindi.' });
      setConfirmDeleteId(null);
      if (expandedId === id) setExpandedId(null);
      await loadUsers();
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'Kullanıcı silinemedi.') });
    } finally {
      setRowBusy(false);
    }
  };

  const savePermissions = async (u: AdminUser) => {
    setMsg(null);
    setRowBusy(true);
    try {
      const ids = u.source_ids === null ? null : Array.from(permIds);
      await apiFetch(`/api/admin/users/${u.id}/permissions`, {
        method: 'PUT',
        body: JSON.stringify({ source_ids: ids }),
      });
      setRowSaved(true);
      await loadUsers();
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'İzinler kaydedilemedi.') });
    } finally {
      setRowBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 860, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Yeni kullanıcı paneli */}
      <div style={cardStyle}>
        <div className="flex items-center justify-between" style={{ marginBottom: showCreate ? 14 : 0 }}>
          <div className="flex items-center gap-2">
            <UsersIcon size={14} style={{ color: 'var(--color-accent-fg)' }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>Kullanıcılar</span>
            <span style={{ fontSize: 11, color: 'var(--color-faint)' }}>{users.length}</span>
          </div>
          <button
            type="button"
            onClick={() => { setShowCreate((v) => !v); setCreatedInfo(null); }}
            style={{ ...ghostBtn, color: 'var(--color-accent-fg)', borderColor: 'var(--color-accent-subtle2)', background: 'var(--color-accent-subtle)' }}
          >
            <Plus size={13} /> Yeni Kullanıcı
          </button>
        </div>

        {showCreate && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 14, borderTop: '1px solid var(--color-border)' }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '1 1 140px' }}>
                <span style={labelStyle}>Kullanıcı Adı</span>
                <input value={nuUsername} onChange={(e) => setNuUsername(e.target.value)} style={inputStyle} placeholder="ayse.k" />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '1 1 140px' }}>
                <span style={labelStyle}>Görünen Ad</span>
                <input value={nuDisplay} onChange={(e) => setNuDisplay(e.target.value)} style={inputStyle} placeholder="Ayşe K." />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '0 0 130px' }}>
                <span style={labelStyle}>Rol</span>
                <select value={nuRole} onChange={(e) => setNuRole(e.target.value as 'user' | 'admin')} style={{ ...inputStyle, cursor: 'pointer' }}>
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '1 1 140px' }}>
                <span style={labelStyle}>İlk Şifre</span>
                <input type="password" value={nuPassword} onChange={(e) => setNuPassword(e.target.value)} style={inputStyle} placeholder="en az 8 karakter" />
              </label>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleCreate}
                disabled={nuBusy || !nuUsername.trim() || nuPassword.length < 8}
                style={{ ...primaryBtn, opacity: nuBusy || !nuUsername.trim() || nuPassword.length < 8 ? 0.55 : 1 }}
              >
                <Plus size={13} /> {nuBusy ? 'Oluşturuluyor…' : 'Oluştur'}
              </button>
              {createdInfo && <Alert kind="ok">{createdInfo}</Alert>}
            </div>
          </div>
        )}
      </div>

      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}

      {/* Kullanıcı listesi */}
      {loading ? (
        <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>Yükleniyor…</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {users.map((u) => {
            const isSelf = me?.id === u.id;
            const isExpanded = expandedId === u.id;
            return (
              <div key={u.id} style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
                {/* Row header */}
                <div
                  className="flex items-center justify-between"
                  style={{ padding: '10px 14px', gap: 10, cursor: 'pointer' }}
                  onClick={() => toggleExpand(u)}
                >
                  <div className="flex items-center gap-3" style={{ minWidth: 0 }}>
                    <button type="button" className="btn-icon" style={{ background: 'none' }}>
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                    <div style={{ minWidth: 0 }}>
                      <div className="flex items-center gap-2">
                        <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text)' }}>{u.display_name || u.username}</span>
                        <RoleChip role={u.role} />
                        {u.must_change_password && (
                          <span className="flex items-center gap-1" style={{ fontSize: 10, color: 'var(--color-warning)' }}>
                            <ShieldAlert size={11} /> şifre değişecek
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>@{u.username}</span>
                    </div>
                  </div>
                  <div className="flex items-center" style={{ gap: 6 }} onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      title={u.is_active ? 'Aktif — devre dışı bırak' : 'Devre dışı — etkinleştir'}
                      onClick={() => patchUser(u.id, { is_active: !u.is_active }, u.is_active ? 'Kullanıcı devre dışı bırakıldı.' : 'Kullanıcı etkinleştirildi.')}
                      disabled={rowBusy || (isSelf && u.is_active)}
                      style={{
                        width: 32, height: 18, borderRadius: 999, position: 'relative', cursor: 'pointer',
                        border: '1px solid var(--color-border)', background: u.is_active ? 'var(--color-accent)' : 'var(--color-surface2)',
                        opacity: rowBusy || (isSelf && u.is_active) ? 0.4 : 1, transition: 'background 150ms ease', padding: 0,
                      }}
                    >
                      <span style={{
                        position: 'absolute', top: 1.5, width: 13, height: 13, borderRadius: '50%', background: '#fff',
                        left: u.is_active ? 16 : 2, transition: 'left 150ms ease',
                      }} />
                    </button>
                    <button
                      type="button"
                      className={confirmDeleteId === u.id ? 'btn btn-danger' : 'btn btn-ghost'}
                      style={{ height: 26, padding: '0 8px', fontSize: 11 }}
                      disabled={rowBusy || isSelf}
                      onClick={() => {
                        if (confirmDeleteId === u.id) {
                          handleDelete(u.id);
                        } else {
                          setConfirmDeleteId(u.id);
                          setTimeout(() => setConfirmDeleteId((cur) => (cur === u.id ? null : cur)), 3000);
                        }
                      }}
                      title={isSelf ? 'Kendinizi silemezsiniz' : 'Sil'}
                    >
                      {confirmDeleteId === u.id ? 'Emin misiniz?' : <><Trash2 size={12} /> Sil</>}
                    </button>
                  </div>
                </div>

                {/* Expanded panel */}
                {isExpanded && (
                  <div style={{ padding: '12px 14px 14px', borderTop: '1px solid var(--color-border)', background: 'var(--color-canvas)', display: 'flex', flexDirection: 'column', gap: 14 }}>
                    {/* Reset password */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <span style={labelStyle}>Şifre Sıfırla</span>
                      <div className="flex items-center" style={{ gap: 8 }}>
                        <input
                          type="password"
                          value={resetPwd}
                          onChange={(e) => setResetPwd(e.target.value)}
                          style={{ ...inputStyle, maxWidth: 240 }}
                          placeholder="yeni şifre (min 8)"
                        />
                        <button
                          type="button"
                          style={{ ...primaryBtn, opacity: resetPwd.length < 8 || rowBusy ? 0.55 : 1 }}
                          disabled={resetPwd.length < 8 || rowBusy}
                          onClick={() => patchUser(u.id, { password: resetPwd }, `${u.username} için şifre güncellendi.`).then(() => setResetPwd(''))}
                        >
                          <KeyRound size={12} /> Uygula
                        </button>
                      </div>
                    </div>

                    {/* Permissions */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div className="flex items-center gap-2">
                        <span style={labelStyle}>Kaynak İzinleri</span>
                        {u.source_ids === null && (
                          <span style={{ fontSize: 10.5, color: 'var(--color-accent-fg)' }}>(admin — tüm kaynaklara erişim)</span>
                        )}
                      </div>
                      {u.source_ids === null ? (
                        <div style={{ fontSize: 11.5, color: 'var(--color-muted)' }}>Bu kullanıcı tüm veri kaynaklarına erişebilir.</div>
                      ) : allSources.length === 0 ? (
                        <div style={{ fontSize: 11.5, color: 'var(--color-muted)' }}>Kaynak bulunamadı.</div>
                      ) : (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                          {allSources.map((s) => {
                            const checked = permIds.has(s.id);
                            return (
                              <label
                                key={s.id}
                                className="flex items-center gap-2"
                                style={{
                                  padding: '5px 10px', borderRadius: 8, cursor: 'pointer', fontSize: 11.5,
                                  background: checked ? 'var(--color-accent-subtle)' : 'var(--color-surface2)',
                                  border: `1px solid ${checked ? 'var(--color-accent-subtle2)' : 'var(--color-border)'}`,
                                  color: checked ? 'var(--color-accent-fg)' : 'var(--color-muted)',
                                  userSelect: 'none',
                                }}
                              >
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => setPermIds((prev) => {
                                    const n = new Set(prev);
                                    if (n.has(s.id)) n.delete(s.id); else n.add(s.id);
                                    return n;
                                  })}
                                  style={{ accentColor: 'var(--color-accent)', margin: 0 }}
                                />
                                {s.display_name}
                              </label>
                            );
                          })}
                        </div>
                      )}
                      {u.source_ids !== null && (
                        <div className="flex items-center gap-3" style={{ marginTop: 2 }}>
                          <button
                            type="button"
                            style={{ ...ghostBtn, color: 'var(--color-accent-fg)', borderColor: 'var(--color-accent-subtle2)', background: 'var(--color-accent-subtle)' }}
                            disabled={rowBusy}
                            onClick={() => savePermissions(u)}
                          >
                            <Save size={12} /> İzinleri Kaydet
                          </button>
                          {rowSaved && <span style={{ fontSize: 11, color: 'var(--color-success)' }}>Kaydedildi ✓</span>}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

/* ────────────────────────────────────────────────────────────
   MCP section (admin)
   ──────────────────────────────────────────────────────────── */

const McpSection: React.FC = () => {
  const [config, setConfig] = useState<McpConfig | null>(null);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<McpConfig>('/api/mcp/config');
      setConfig(data);
      setText(JSON.stringify(data, null, 2));
      setMsg(null);
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'MCP yapılandırması yüklenemedi.') });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  const handleSave = async () => {
    setMsg(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch (e) {
      setMsg({ kind: 'err', text: `Geçersiz JSON: ${e instanceof Error ? e.message : 'parse hatası'}` });
      return;
    }
    setBusy(true);
    try {
      await apiFetch('/api/mcp/config', { method: 'PUT', body: JSON.stringify({ config: parsed }) });
      setMsg({ kind: 'ok', text: 'MCP yapılandırması kaydedildi.' });
      await loadConfig();
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'MCP yapılandırması kaydedilemedi.') });
    } finally {
      setBusy(false);
    }
  };

  const servers: [string, McpServer][] = config?.mcpServers ? Object.entries(config.mcpServers) : [];

  return (
    <div style={{ maxWidth: 780, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Sunucu listesi */}
      <div style={cardStyle}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
          <div className="flex items-center gap-2">
            <Plug size={14} style={{ color: 'var(--color-accent-fg)' }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>MCP Sunucuları</span>
            <span style={{ fontSize: 11, color: 'var(--color-faint)' }}>{servers.length}</span>
          </div>
          <button type="button" className="btn btn-ghost" style={{ height: 26 }} onClick={loadConfig} disabled={loading}>
            <RefreshCw size={12} /> Yenile
          </button>
        </div>
        {loading && <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>Yükleniyor…</div>}
        {!loading && servers.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>Tanımlı MCP sunucusu yok.</div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {servers.map(([name, srv]) => (
            <div
              key={name}
              style={{
                padding: '10px 12px', borderRadius: 8, background: 'var(--color-surface2)',
                border: '1px solid var(--color-border)',
              }}
            >
              <div className="flex items-center gap-2" style={{ marginBottom: 3 }}>
                <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text)', fontFamily: 'var(--font-mono)' }}>{name}</span>
                {srv.description && <span style={{ fontSize: 10.5, color: 'var(--color-faint)' }}>— {srv.description}</span>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {srv.command}
                {srv.args && srv.args.length > 0 ? ` ${srv.args.join(' ')}` : ''}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* JSON editor */}
      <div style={cardStyle}>
        <div className="flex items-center justify-between" style={{ marginBottom: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>Yapılandırma (JSON)</span>
          <button type="button" onClick={handleSave} disabled={busy || loading} style={{ ...primaryBtn, opacity: busy || loading ? 0.55 : 1 }}>
            <Save size={13} /> {busy ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          spellCheck={false}
          className="font-mono"
          style={{
            width: '100%', minHeight: 220, resize: 'vertical',
            background: 'var(--color-code-bg)', color: 'var(--color-code-fg)',
            border: '1px solid var(--color-border)', borderRadius: 8,
            fontSize: 11.5, lineHeight: 1.6, padding: 12, outline: 'none',
            boxSizing: 'border-box',
          }}
        />
        {msg && <div style={{ marginTop: 10 }}><Alert kind={msg.kind}>{msg.text}</Alert></div>}
        <p style={{ fontSize: 10.5, color: 'var(--color-faint)', marginTop: 10, marginBottom: 0 }}>
          Sunucu tanımları <code className="font-mono" style={{ fontSize: 10.5, color: 'var(--color-accent-fg)' }}>.agents/mcp_config.json</code> dosyasına yazılır; agent oturumu yeniden başlatınca geçerli olur.
        </p>
      </div>
    </div>
  );
};

/* ────────────────────────────────────────────────────────────
   Audit log section (admin)
   ──────────────────────────────────────────────────────────── */

const AUDIT_LIMIT = 50;

const detailSummary = (d: AuditItem['detail']): string => {
  if (d === null || d === undefined) return '—';
  let text: string;
  try {
    text = typeof d === 'string' ? d : JSON.stringify(d);
  } catch {
    text = String(d);
  }
  if (!text) return '—';
  return text.length > 60 ? `${text.slice(0, 60)}…` : text;
};

const AuditSection: React.FC = () => {
  const [items, setItems] = useState<AuditItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // filtre inputları — "Yenile" ile uygulanır
  const [actionInput, setActionInput] = useState('');
  const [userIdInput, setUserIdInput] = useState('');
  const [appliedAction, setAppliedAction] = useState('');
  const [appliedUserId, setAppliedUserId] = useState('');

  const fetchPage = useCallback(async (action: string, userId: string, off: number, append: boolean) => {
    if (append) setLoadingMore(true); else setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('limit', String(AUDIT_LIMIT));
      params.set('offset', String(off));
      if (action.trim()) params.set('action', action.trim());
      if (userId.trim()) params.set('user_id', userId.trim());
      const data = await apiFetch<AuditResponse>(`/api/admin/audit?${params.toString()}`);
      const rows = Array.isArray(data?.items) ? data.items : [];
      setItems((prev) => (append ? [...prev, ...rows] : rows));
      setTotal(typeof data?.total === 'number' ? data.total : rows.length);
      setOffset(off);
      setMsg(null);
    } catch (e) {
      setMsg(friendlyError(e, 'Denetim kayıtları yüklenemedi.'));
    } finally {
      if (append) setLoadingMore(false); else setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPage('', '', 0, false); }, [fetchPage]);

  const handleRefresh = () => {
    setAppliedAction(actionInput);
    setAppliedUserId(userIdInput);
    fetchPage(actionInput, userIdInput, 0, false);
  };

  const hasMore = items.length < total;

  const thStyle: React.CSSProperties = {
    textAlign: 'left', fontSize: 10.5, fontWeight: 600, color: 'var(--color-muted)',
    textTransform: 'uppercase', letterSpacing: '0.05em', padding: '8px 10px',
    borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap',
  };
  const tdStyle: React.CSSProperties = {
    fontSize: 12, color: 'var(--color-text-2)', padding: '8px 10px',
    borderBottom: '1px solid var(--color-border)', verticalAlign: 'top',
  };

  return (
    <div style={{ maxWidth: 960, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Filtre satırı */}
      <div style={cardStyle}>
        <div className="flex items-end" style={{ gap: 10, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '1 1 180px' }}>
            <span style={labelStyle}>Aksiyon (ön ek)</span>
            <input
              value={actionInput}
              onChange={(e) => setActionInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleRefresh(); }}
              style={inputStyle}
              placeholder="örn. user."
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '1 1 180px' }}>
            <span style={labelStyle}>Kullanıcı ID</span>
            <input
              value={userIdInput}
              onChange={(e) => setUserIdInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleRefresh(); }}
              style={inputStyle}
              placeholder="boş = tümü"
            />
          </label>
          <button type="button" className="btn btn-ghost" style={{ height: 34 }} onClick={handleRefresh} disabled={loading}>
            <RefreshCw size={12} /> Yenile
          </button>
        </div>
      </div>

      {msg && <Alert kind="err">{msg}</Alert>}

      {/* Kayıt tablosu */}
      <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--color-muted)' }}>Yükleniyor…</div>
        ) : items.length === 0 ? (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--color-muted)' }}>Henüz denetim kaydı yok.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={thStyle}>Zaman</th>
                  <th style={thStyle}>Kullanıcı</th>
                  <th style={thStyle}>Aksiyon</th>
                  <th style={thStyle}>Hedef</th>
                  <th style={thStyle}>Detay</th>
                  <th style={thStyle}>İstek</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.id}>
                    <td style={{ ...tdStyle, whiteSpace: 'nowrap', color: 'var(--color-muted)' }}>{fmtDateTime(it.created_at)}</td>
                    <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>{it.username || '—'}</td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          fontSize: 10.5, fontWeight: 600, padding: '2px 7px', borderRadius: 6,
                          background: 'var(--color-accent-subtle)', border: '1px solid var(--color-accent-subtle2)',
                          color: 'var(--color-accent-fg)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap',
                        }}
                      >
                        {it.action}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={it.target ?? undefined}>
                      {it.target || '—'}
                    </td>
                    <td style={{ ...tdStyle, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--color-muted)' }} title={detailSummary(it.detail)}>
                      {detailSummary(it.detail)}
                    </td>
                    <td style={{ ...tdStyle, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--color-faint)' }} title={it.request_id ?? undefined}>
                      {it.request_id || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Sayfalama */}
      {!loading && hasMore && (
        <div>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => fetchPage(appliedAction, appliedUserId, offset + AUDIT_LIMIT, true)}
            disabled={loadingMore}
          >
            {loadingMore ? 'Yükleniyor…' : `Daha yükle (${items.length}/${total})`}
          </button>
        </div>
      )}
    </div>
  );
};

/* ────────────────────────────────────────────────────────────
   Scheduled reports section (all users)
   ──────────────────────────────────────────────────────────── */

const DAY_NAMES = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'];

const frequencyLabel = (s: ScheduleRow): string => {
  const hh = String(s.hour).padStart(2, '0');
  return s.frequency === 'weekly'
    ? `Her ${DAY_NAMES[s.day_of_week] ?? '?'} ${hh}:00`
    : `Her gün ${hh}:00`;
};

const StatusChip: React.FC<{ status: string | null }> = ({ status }) => {
  if (!status) return <span style={{ fontSize: 10.5, color: 'var(--color-faint)' }}>hiç çalışmadı</span>;
  const s = status.toLowerCase();
  const color = /success|ok|complete/.test(s)
    ? 'var(--color-success)'
    : /fail|error/.test(s)
      ? 'var(--color-danger)'
      : 'var(--color-muted)';
  return (
    <span
      style={{
        fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 6,
        background: 'var(--color-surface2)', border: '1px solid var(--color-border)',
        color, fontFamily: 'var(--font-mono)',
      }}
    >
      {status}
    </span>
  );
};

const SchedulesSection: React.FC = () => {
  const storeSources = useBIStore((s) => s.sources);

  const [rows, setRows] = useState<ScheduleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  // create form
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState('');
  const [question, setQuestion] = useState('');
  const [frequency, setFrequency] = useState<'daily' | 'weekly'>('daily');
  const [hour, setHour] = useState(9);
  const [dayOfWeek, setDayOfWeek] = useState(0);
  const [email, setEmail] = useState('');
  const [selSources, setSelSources] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  // row actions
  const [rowBusy, setRowBusy] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const loadSchedules = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<ScheduleRow[]>('/api/schedules');
      setRows(Array.isArray(data) ? data : []);
      setMsg(null);
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'Zamanlanmış raporlar yüklenemedi.') });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSchedules(); }, [loadSchedules]);

  const handleCreate = async () => {
    setMsg(null);
    if (!title.trim() || !question.trim()) return;
    setBusy(true);
    try {
      await apiFetch('/api/schedules', {
        method: 'POST',
        body: JSON.stringify({
          title: title.trim(),
          question: question.trim(),
          source_ids: Array.from(selSources),
          frequency,
          hour,
          day_of_week: frequency === 'weekly' ? dayOfWeek : 0,
          email: email.trim() || null,
        }),
      });
      setMsg({ kind: 'ok', text: 'Zamanlanmış rapor oluşturuldu.' });
      setTitle(''); setQuestion(''); setEmail(''); setSelSources(new Set());
      setFrequency('daily'); setHour(9); setDayOfWeek(0);
      setShowCreate(false);
      await loadSchedules();
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'Rapor oluşturulamadı.') });
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (r: ScheduleRow) => {
    setMsg(null);
    setRowBusy(true);
    try {
      await apiFetch(`/api/schedules/${r.id}`, {
        method: 'PUT',
        body: JSON.stringify({ active: !r.active }),
      });
      await loadSchedules();
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'Rapor güncellenemedi.') });
    } finally {
      setRowBusy(false);
    }
  };

  const handleDelete = async (id: string) => {
    setMsg(null);
    setRowBusy(true);
    try {
      await apiFetch(`/api/schedules/${id}`, { method: 'DELETE' });
      setMsg({ kind: 'ok', text: 'Zamanlanmış rapor silindi.' });
      setConfirmDeleteId(null);
      await loadSchedules();
    } catch (e) {
      setMsg({ kind: 'err', text: friendlyError(e, 'Rapor silinemedi.') });
    } finally {
      setRowBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 780, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Yeni rapor paneli */}
      <div style={cardStyle}>
        <div className="flex items-center justify-between" style={{ marginBottom: showCreate ? 14 : 0 }}>
          <div className="flex items-center gap-2">
            <CalendarClock size={14} style={{ color: 'var(--color-accent-fg)' }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>Zamanlanmış Raporlar</span>
            <span style={{ fontSize: 11, color: 'var(--color-faint)' }}>{rows.length}</span>
          </div>
          <button
            type="button"
            onClick={() => setShowCreate((v) => !v)}
            style={{ ...ghostBtn, color: 'var(--color-accent-fg)', borderColor: 'var(--color-accent-subtle2)', background: 'var(--color-accent-subtle)' }}
          >
            <Plus size={13} /> Yeni Rapor
          </button>
        </div>

        {showCreate && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 14, borderTop: '1px solid var(--color-border)' }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '2 1 200px' }}>
                <span style={labelStyle}>Başlık</span>
                <input value={title} onChange={(e) => setTitle(e.target.value)} style={inputStyle} placeholder="Haftalık satış özeti" />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '3 1 260px' }}>
                <span style={labelStyle}>Soru</span>
                <input value={question} onChange={(e) => setQuestion(e.target.value)} style={inputStyle} placeholder="/forecast gelecek ay ciro … veya doğal dil" />
              </label>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '0 0 120px' }}>
                <span style={labelStyle}>Sıklık</span>
                <select value={frequency} onChange={(e) => setFrequency(e.target.value as 'daily' | 'weekly')} style={{ ...inputStyle, cursor: 'pointer' }}>
                  <option value="daily">Günlük</option>
                  <option value="weekly">Haftalık</option>
                </select>
              </label>
              {frequency === 'weekly' && (
                <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '0 0 140px' }}>
                  <span style={labelStyle}>Gün</span>
                  <select value={dayOfWeek} onChange={(e) => setDayOfWeek(Number(e.target.value))} style={{ ...inputStyle, cursor: 'pointer' }}>
                    {DAY_NAMES.map((d, i) => (
                      <option key={d} value={i}>{d}</option>
                    ))}
                  </select>
                </label>
              )}
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '0 0 110px' }}>
                <span style={labelStyle}>Saat</span>
                <select value={hour} onChange={(e) => setHour(Number(e.target.value))} style={{ ...inputStyle, cursor: 'pointer' }}>
                  {Array.from({ length: 24 }, (_, h) => (
                    <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: '1 1 180px' }}>
                <span style={labelStyle}>E-posta (opsiyonel)</span>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} style={inputStyle} placeholder="rapor@firma.com" />
              </label>
            </div>
            {storeSources.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={labelStyle}>Kaynaklar</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {storeSources.map((s) => {
                    const checked = selSources.has(s.id);
                    return (
                      <label
                        key={s.id}
                        className="flex items-center gap-2"
                        style={{
                          padding: '5px 10px', borderRadius: 8, cursor: 'pointer', fontSize: 11.5,
                          background: checked ? 'var(--color-accent-subtle)' : 'var(--color-surface2)',
                          border: `1px solid ${checked ? 'var(--color-accent-subtle2)' : 'var(--color-border)'}`,
                          color: checked ? 'var(--color-accent-fg)' : 'var(--color-muted)',
                          userSelect: 'none',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => setSelSources((prev) => {
                            const n = new Set(prev);
                            if (n.has(s.id)) n.delete(s.id); else n.add(s.id);
                            return n;
                          })}
                          style={{ accentColor: 'var(--color-accent)', margin: 0 }}
                        />
                        {s.display_name}
                      </label>
                    );
                  })}
                </div>
              </div>
            )}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleCreate}
                disabled={busy || !title.trim() || !question.trim()}
                style={{ ...primaryBtn, opacity: busy || !title.trim() || !question.trim() ? 0.55 : 1 }}
              >
                <Plus size={13} /> {busy ? 'Oluşturuluyor…' : 'Oluştur'}
              </button>
              <span style={{ fontSize: 10.5, color: 'var(--color-faint)' }}>
                E-posta boş bırakılırsa rapor e-postası gönderilmez.
              </span>
            </div>
          </div>
        )}
      </div>

      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}

      {/* Rapor listesi */}
      {loading ? (
        <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>Yükleniyor…</div>
      ) : rows.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>Henüz zamanlanmış rapor yok.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {rows.map((r) => (
            <div key={r.id} style={{ ...cardStyle, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="flex items-center justify-between" style={{ gap: 10 }}>
                <div style={{ minWidth: 0 }}>
                  <div className="flex items-center gap-2" style={{ flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text)' }}>{r.title}</span>
                    <span
                      style={{
                        fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 6,
                        background: 'var(--color-surface2)', border: '1px solid var(--color-border)',
                        color: 'var(--color-muted)',
                      }}
                    >
                      {frequencyLabel(r)}
                    </span>
                  </div>
                  <div className="flex items-center" style={{ marginTop: 4, minWidth: 0 }}>
                    {r.question.startsWith('/') ? (
                      <span
                        style={{
                          fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--color-accent-fg)',
                          background: 'var(--color-accent-subtle)', border: '1px solid var(--color-accent-subtle2)',
                          padding: '1px 7px', borderRadius: 5, overflow: 'hidden', textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap', maxWidth: 460,
                        }}
                        title={r.question}
                      >
                        {r.question}
                      </span>
                    ) : (
                      <span style={{ fontSize: 11.5, color: 'var(--color-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.question}>
                        {r.question}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center" style={{ gap: 6, flexShrink: 0 }}>
                  <button
                    type="button"
                    title={r.active ? 'Aktif — duraklat' : 'Duraklatılmış — etkinleştir'}
                    onClick={() => toggleActive(r)}
                    disabled={rowBusy}
                    style={{
                      width: 32, height: 18, borderRadius: 999, position: 'relative', cursor: 'pointer',
                      border: '1px solid var(--color-border)', background: r.active ? 'var(--color-accent)' : 'var(--color-surface2)',
                      opacity: rowBusy ? 0.4 : 1, transition: 'background 150ms ease', padding: 0,
                    }}
                  >
                    <span style={{
                      position: 'absolute', top: 1.5, width: 13, height: 13, borderRadius: '50%', background: '#fff',
                      left: r.active ? 16 : 2, transition: 'left 150ms ease',
                    }} />
                  </button>
                  <button
                    type="button"
                    className={confirmDeleteId === r.id ? 'btn btn-danger' : 'btn btn-ghost'}
                    style={{ height: 26, padding: '0 8px', fontSize: 11 }}
                    disabled={rowBusy}
                    onClick={() => {
                      if (confirmDeleteId === r.id) {
                        handleDelete(r.id);
                      } else {
                        setConfirmDeleteId(r.id);
                        setTimeout(() => setConfirmDeleteId((cur) => (cur === r.id ? null : cur)), 3000);
                      }
                    }}
                    title="Sil"
                  >
                    {confirmDeleteId === r.id ? 'Emin misiniz?' : <><Trash2 size={12} /> Sil</>}
                  </button>
                </div>
              </div>
              <div className="flex items-center" style={{ gap: 12, flexWrap: 'wrap' }}>
                <span
                  className="flex items-center gap-1"
                  style={{ fontSize: 10.5, color: r.email ? 'var(--color-muted)' : 'var(--color-faint)' }}
                >
                  <Mail size={11} /> {r.email || 'e-posta yok'}
                </span>
                <StatusChip status={r.last_status} />
                {r.last_run_at && (
                  <span style={{ fontSize: 10.5, color: 'var(--color-faint)' }}>
                    son koşu: {fmtDateTime(r.last_run_at)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/* ────────────────────────────────────────────────────────────
   SettingsPage — section nav + content
   ──────────────────────────────────────────────────────────── */

const SettingsPage: React.FC<{ initialSection?: string }> = ({ initialSection = 'account' }) => {
  const user = useBIStore((s) => s.user);
  const isAdmin = user?.role === 'admin';

  const sections: { id: Section; label: string; icon: React.ReactNode; adminOnly: boolean }[] = [
    { id: 'account', label: 'Hesap', icon: <UserIcon size={14} />, adminOnly: false },
    { id: 'model', label: 'Model & LLM', icon: <Cpu size={14} />, adminOnly: true },
    { id: 'sources', label: 'Veri Kaynakları', icon: <Database size={14} />, adminOnly: true },
    { id: 'mysources', label: 'Veri Kaynaklarım', icon: <Database size={14} />, adminOnly: false },
    { id: 'schedules', label: 'Zamanlanmış Raporlar', icon: <CalendarClock size={14} />, adminOnly: false },
    { id: 'users', label: 'Kullanıcılar', icon: <UsersIcon size={14} />, adminOnly: true },
    { id: 'mcp', label: 'MCP Bağlantıları', icon: <Plug size={14} />, adminOnly: true },
    { id: 'audit', label: 'Denetim Kayıtları', icon: <ScrollText size={14} />, adminOnly: true },
  ];

  const visible = sections.filter((s) => isAdmin || !s.adminOnly);
  const initial = (visible.find((s) => s.id === initialSection)?.id ?? 'account') as Section;
  const [section, setSection] = useState<Section>(initial);

  // Rol değişirse / başlangıç bölümü yöneticiye özelse güvenli bölüme dön
  useEffect(() => {
    if (!visible.some((s) => s.id === section)) setSection('account');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  const renderSection = () => {
    switch (section) {
      case 'account': return <AccountSection />;
      case 'model': return <ModelSection />;
      case 'sources': return <SourcesSection />;
      case 'mysources': return <MySourcesSection />;
      case 'schedules': return <SchedulesSection />;
      case 'users': return <UsersSection />;
      case 'mcp': return <McpSection />;
      case 'audit': return <AuditSection />;
      default: return <AccountSection />;
    }
  };

  const titles: Record<Section, { title: string; subtitle: string }> = {
    account: { title: 'Hesap', subtitle: 'Profil bilgileri ve şifre yönetimi' },
    model: { title: 'Model & LLM', subtitle: 'LLM sağlayıcı, API anahtarı ve model ayarları' },
    sources: { title: 'Veri Kaynakları', subtitle: 'Veritabanı bağlantılarını ekle, düzenle ve yönet' },
    mysources: { title: 'Veri Kaynaklarım', subtitle: 'Erişim izniniz olan veri kaynakları' },
    schedules: { title: 'Zamanlanmış Raporlar', subtitle: 'Periyodik rapor sorularınızı planlayın ve yönetin' },
    users: { title: 'Kullanıcılar', subtitle: 'Kullanıcı yönetimi, izinler ve şifre sıfırlama' },
    mcp: { title: 'MCP Bağlantıları', subtitle: 'Model Context Protocol sunucu yapılandırması' },
    audit: { title: 'Denetim Kayıtları', subtitle: 'Sistemdeki kullanıcı işlemlerinin kaydı' },
  };

  return (
    <div className="flex" style={{ height: '100%', minHeight: 0, background: 'var(--color-bg)' }}>
      {/* Sol nav */}
      <aside
        className="flex flex-col"
        style={{
          width: 224, flexShrink: 0, borderRight: '1px solid var(--color-border)',
          padding: '16px 10px', gap: 2, background: 'var(--color-canvas)', overflowY: 'auto',
        }}
      >
        <div style={{ padding: '0 10px 14px' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.01em' }}>Ayarlar</div>
          {user && (
            <div className="flex items-center gap-2" style={{ marginTop: 6 }}>
              <span style={{ fontSize: 11.5, color: 'var(--color-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 110 }}>
                {user.display_name || user.username}
              </span>
              <RoleChip role={user.role} />
            </div>
          )}
        </div>
        <div style={{ height: 1, background: 'var(--color-border)', margin: '0 6px 10px' }} />
        {visible.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSection(s.id)}
            className={`nav-item${section === s.id ? ' active' : ''}`}
          >
            <span style={{ display: 'inline-flex' }}>{s.icon}</span>
            {s.label}
          </button>
        ))}
      </aside>

      {/* Sağ içerik */}
      <main style={{ flex: 1, minWidth: 0, overflowY: 'auto', padding: '24px 28px' }}>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: 'var(--color-text)', margin: 0, letterSpacing: '-0.02em' }}>
            {titles[section].title}
          </h2>
          <p style={{ fontSize: 12, color: 'var(--color-muted)', margin: '4px 0 0' }}>{titles[section].subtitle}</p>
        </div>
        {renderSection()}
      </main>
    </div>
  );
};

export default SettingsPage;
