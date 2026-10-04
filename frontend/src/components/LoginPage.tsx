import React, { useState } from 'react';
import { useBIStore } from '../context/store';
import { LogIn, Eye, EyeOff, AlertCircle } from 'lucide-react';

/**
 * LoginPage — SaaS giriş ekranı.
 * Main admin ilk girişte admin / admin123 kullanır; sistem şifre değiştirmeyi zorunlu tutar.
 */
const LoginPage: React.FC = () => {
  const login = useBIStore((s) => s.login);
  const language = useBIStore((s) => s.language);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const tr = language !== 'en';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password || busy) return;
    setBusy(true);
    setError('');
    const res = await login(username.trim(), password);
    if (!res.ok) setError(res.error || (tr ? 'Giriş başarısız.' : 'Login failed.'));
    setBusy(false);
  };

  return (
    <div
      className="w-screen h-screen flex items-center justify-center"
      style={{ background: 'var(--color-bg)' }}
    >
      {/* Arka plan aura */}
      <div
        className="pointer-events-none absolute"
        style={{
          inset: 0,
          background:
            'radial-gradient(ellipse 60% 40% at 20% 0%, rgba(201,100,66,0.10) 0%, transparent 100%), radial-gradient(ellipse 40% 30% at 85% 90%, rgba(201,100,66,0.06) 0%, transparent 100%)',
        }}
      />

      <div
        className="relative flex flex-col items-center"
        style={{ width: 380 }}
      >
        {/* Marka */}
        <div
          className="flex items-center justify-center"
          style={{
            width: 48,
            height: 48,
            borderRadius: 14,
            background: 'linear-gradient(135deg, #c96442 0%, #b8532f 60%, #a34628 100%)',
            boxShadow: '0 8px 24px rgba(201,100,66,0.25)',
            marginBottom: 16,
          }}
        >
          <span style={{ fontSize: 20, fontWeight: 800, color: '#fff' }}>D</span>
        </div>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text)', letterSpacing: '-0.02em', margin: 0 }}>
          DeepBI Analytics Studio
        </h1>
        <p style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 6, marginBottom: 28 }}>
          {tr ? 'Devam etmek için giriş yapın' : 'Sign in to continue'}
        </p>

        {/* Kart */}
        <form
          onSubmit={handleSubmit}
          style={{
            width: '100%',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 14,
            padding: 24,
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
          }}
        >
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {tr ? 'Kullanıcı Adı' : 'Username'}
            </span>
            <input
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={tr ? 'kullanıcı adı' : 'username'}
              style={{
                height: 36,
                padding: '0 12px',
                borderRadius: 8,
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface2)',
                color: 'var(--color-text)',
                fontSize: 13,
                outline: 'none',
              }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {tr ? 'Şifre' : 'Password'}
            </span>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{
                  width: '100%',
                  height: 36,
                  padding: '0 36px 0 12px',
                  borderRadius: 8,
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface2)',
                  color: 'var(--color-text)',
                  fontSize: 13,
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                style={{
                  position: 'absolute',
                  right: 8,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--color-muted)',
                  display: 'flex',
                  padding: 4,
                }}
              >
                {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </label>

          {error && (
            <div
              className="flex items-center gap-2"
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                background: 'var(--color-danger-subtle)',
                border: '1px solid rgba(239,68,68,0.25)',
                color: 'var(--color-danger)',
                fontSize: 11.5,
              }}
            >
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy || !username.trim() || !password}
            className="flex items-center justify-center gap-2"
            style={{
              height: 38,
              borderRadius: 8,
              border: 'none',
              cursor: busy ? 'wait' : 'pointer',
              background: 'var(--color-accent)',
              color: '#fff',
              fontSize: 13,
              fontWeight: 600,
              opacity: busy || !username.trim() || !password ? 0.6 : 1,
              transition: 'background 150ms ease',
            }}
          >
            <LogIn size={15} />
            {busy ? (tr ? 'Giriş yapılıyor…' : 'Signing in…') : tr ? 'Giriş Yap' : 'Sign In'}
          </button>
        </form>

        <p style={{ fontSize: 10.5, color: 'var(--color-faint)', marginTop: 18, textAlign: 'center' }}>
          {tr
            ? 'Erişim bilginiz yoksa sistem yöneticinizle iletişime geçin.'
            : 'Contact your system administrator for access.'}
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
