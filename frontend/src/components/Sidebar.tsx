import React, { useState, useEffect } from 'react';
import { useBIStore } from '../context/store';
import { translations } from '../context/translations';
import {
  FileText, Database, RefreshCw,
  Plus, Trash2, Edit, HardDrive, LogOut
} from 'lucide-react';

interface SidebarProps {
  onOpenSources: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onOpenSources }) => {
  const user = useBIStore((s) => s.user);
  const logout = useBIStore((s) => s.logout);
  const sources = useBIStore((s) => s.sources);
  const files = useBIStore((s) => s.files);
  const activeSourceId = useBIStore((s) => s.activeSourceId);
  const sessions = useBIStore((s) => s.sessions);
  const activeSessionId = useBIStore((s) => s.activeSessionId);
  const selectSession = useBIStore((s) => s.selectSession);
  const deleteSession = useBIStore((s) => s.deleteSession);
  const fetchSessions = useBIStore((s) => s.fetchSessions);
  const renameSession = useBIStore((s) => s.renameSession);
  const fetchSources = useBIStore((s) => s.fetchSources);
  const fetchFiles = useBIStore((s) => s.fetchFiles);
  const setShowSourcePicker = useBIStore((s) => s.setShowSourcePicker);
  const language = useBIStore((s) => s.language);

  const t = translations[language];

  const [sessionFilter, setSessionFilter] = useState('');
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');

  useEffect(() => {
    fetchSources();
    fetchFiles();
    fetchSessions();
  }, []);

  const filteredSessions = sessions.filter(s =>
    s.title.toLowerCase().includes(sessionFilter.trim().toLowerCase())
  );

  const activeSource = React.useMemo(() => {
    const dbMatch = sources.find(s => s.id === activeSourceId);
    if (dbMatch) return { label: dbMatch.display_name, type: dbMatch.type, isDb: true };
    const fileMatch = files.find(f => f.id === activeSourceId);
    if (fileMatch) return { label: fileMatch.alias, type: language === 'tr' ? 'Excel/CSV' : 'Excel/CSV', isDb: false };
    return null;
  }, [sources, files, activeSourceId, language]);

  const iconBtn = (): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'var(--color-muted)',
    borderRadius: '6px',
    border: '1px solid transparent',
    transition: 'background 0.15s, color 0.15s',
  });

  return (
    <aside
      className="flex flex-col shrink-0 z-20 select-none overflow-hidden"
      style={{
        width: 240,
        height: '100vh',
        background: 'var(--color-bg)',
        borderRight: '1px solid var(--color-border)',
      }}
    >
      {/* ── Brand Header ── */}
      <div
        className="flex items-center justify-between px-3 shrink-0"
        style={{
          height: 52,
          borderBottom: '1px solid var(--color-border2)',
        }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Brand mark — coral gradient with a soft glow */}
          <div
            className="flex items-center justify-center shrink-0 shadow-[0_0_14px_rgba(201,100,66,0.25)]"
            style={{
              width: 26, height: 26,
              background: 'linear-gradient(135deg, #c96442 0%, #b8532f 60%, #a34628 100%)',
              color: '#ffffff',
              borderRadius: '7px',
              fontSize: 9.5,
              fontWeight: 800,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.05em',
              flexShrink: 0,
            }}
          >
            BI
          </div>
          <div className="min-w-0">
            <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--color-text)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.01em', lineHeight: 1.25 }}>DeepBI</div>
            <div style={{ fontSize: 9, color: 'var(--color-faint)', fontFamily: 'var(--font-sans)', fontWeight: 500, letterSpacing: '0.04em', textTransform: 'uppercase' }}>Analytics Studio</div>
          </div>
        </div>
      </div>

      {/* ── Sessions ── */}
      <div className="flex-1 flex flex-col px-2.5 pt-3.5 pb-2 min-h-0 overflow-hidden">

        {/* Section label */}
        <div
          className="flex items-center justify-between px-1.5 mb-2 shrink-0"
          style={{ fontSize: 9.5, color: 'var(--color-faint)', fontFamily: 'var(--font-sans)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}
        >
          <span>{t.notebooks}</span>
          <button
            onClick={() => setShowSourcePicker(true, 'create')}
            className="btn-icon cursor-pointer hover:bg-[var(--color-surface2)] hover:text-[var(--color-text)] transition-colors duration-150"
            style={{ ...iconBtn(), padding: 3.5, cursor: 'pointer' }}
            title={language === 'tr' ? 'Yeni Çalışma Oturumu Aç' : 'Open New Study Session'}
          >
            <Plus size={13} />
          </button>
        </div>

        {/* Search */}
        <div className="px-0.5 mb-2.5 shrink-0">
          <input
            value={sessionFilter}
            onChange={(e) => setSessionFilter(e.target.value)}
            placeholder={t.search}
            className="input w-full focus:border-[var(--color-border-focus)] transition-colors duration-150"
            style={{ paddingTop: 6, paddingBottom: 6, fontSize: 11, borderRadius: '8px', fontFamily: 'var(--font-sans)' }}
          />
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto space-y-0.5 pr-0.5 min-h-0 scrollbar-thin">
          {filteredSessions.map(s => {
            const active = activeSessionId === s.id;
            const isEditing = editingSessionId === s.id;
            return (
              <div
                key={s.id}
                onClick={() => !isEditing && selectSession(s.id)}
                className={`flex items-center justify-between group cursor-pointer transition-colors duration-150 ${
                  active
                    ? 'bg-[var(--color-surface2)]'
                    : 'hover:bg-[var(--color-surface)]'
                }`}
                style={{
                  padding: '6px 8px',
                  borderRadius: '8px',
                  boxShadow: active ? 'inset 2px 0 0 var(--color-accent)' : 'none',
                }}
              >
                {isEditing ? (
                  <div className="flex items-center gap-2 min-w-0 flex-1" onClick={(e) => e.stopPropagation()}>
                    <FileText size={11} style={{ color: 'var(--color-accent-fg)', flexShrink: 0 }} />
                    <input
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          if (editingTitle.trim()) renameSession(s.id, editingTitle.trim());
                          setEditingSessionId(null);
                        } else if (e.key === 'Escape') {
                          setEditingSessionId(null);
                        }
                      }}
                      onBlur={() => {
                        if (editingTitle.trim()) renameSession(s.id, editingTitle.trim());
                        setEditingSessionId(null);
                      }}
                      autoFocus
                      className="bg-transparent text-xs text-gh-text outline-none w-full font-mono"
                      style={{ fontSize: 11, borderBottom: '1px solid var(--color-accent)' }}
                    />
                  </div>
                ) : (
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <div
                      className="w-1.5 h-1.5 rounded-full shrink-0 transition-all duration-200"
                      style={{
                        background: active ? 'var(--color-accent)' : 'var(--color-disabled)',
                        boxShadow: active ? '0 0 5px rgba(201,100,66,0.45)' : 'none',
                        opacity: active ? 1 : 0.55,
                      }}
                    />
                    <span
                      className="truncate flex-1 font-sans text-[11.5px]"
                      style={{ color: active ? 'var(--color-text)' : 'var(--color-muted)', fontWeight: active ? 500 : 400, letterSpacing: '-0.005em' }}
                      onDoubleClick={(e) => {
                        e.stopPropagation();
                        setEditingSessionId(s.id);
                        setEditingTitle(s.title);
                      }}
                      title={t.renameTooltip}
                    >
                      {s.title}
                    </span>
                  </div>
                )}
                {!isEditing && (
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingSessionId(s.id);
                        setEditingTitle(s.title);
                      }}
                      className="btn-icon cursor-pointer hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
                      style={{ padding: 3, borderRadius: '4px', color: 'var(--color-faint)', border: 'none', display: 'flex', alignItems: 'center' }}
                      title={language === 'tr' ? 'Yeniden Adlandır' : 'Rename'}
                    >
                      <Edit size={10} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                      className="btn-icon cursor-pointer hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
                      style={{ padding: 3, color: 'var(--color-faint)', border: 'none', borderRadius: '4px', display: 'flex', alignItems: 'center' }}
                      title={language === 'tr' ? 'Oturumu Kapat' : 'Close Session'}
                    >
                      <Trash2 size={10} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}

          {filteredSessions.length === 0 && (
            <div
              className="px-2 py-6 text-center font-sans"
              style={{ fontSize: 10.5, color: 'var(--color-faint)', lineHeight: 1.5, whiteSpace: 'pre-line' }}
            >
              {sessions.length === 0
                ? (language === 'tr' ? 'Henüz oturum yok.\nİlk mesajınla bir oturum başlat.' : 'No sessions yet.\nStart one with your first message.')
                : t.noResults}
            </div>
          )}
        </div>
      </div>

      {/* ── Active Dataset ── */}
      <div className="px-2.5 py-3 shrink-0" style={{ borderTop: '1px solid var(--color-border2)' }}>
        <div
          className="flex items-center justify-between mb-2 px-1.5"
          style={{ fontSize: 9.5, color: 'var(--color-faint)', fontFamily: 'var(--font-sans)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}
        >
          <span>{t.activeDataset}</span>
          <button
            onClick={() => { fetchSources(); fetchFiles(); }}
            className="btn-icon cursor-pointer hover:bg-[var(--color-surface2)] hover:text-[var(--color-text)] transition-colors duration-150"
            style={{ ...iconBtn(), padding: 3.5, cursor: 'pointer' }}
            title={language === 'tr' ? 'Yenile' : 'Refresh'}
          >
            <RefreshCw size={11} />
          </button>
        </div>

        {activeSource ? (
          <div
            onClick={onOpenSources}
            className="cursor-pointer transition-colors duration-150 hover:bg-[var(--color-surface2)]"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderLeft: '2px solid var(--color-accent)',
              padding: '9px 11px',
              borderRadius: '8px',
            }}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              {activeSource.isDb
                ? <Database size={13} style={{ color: 'var(--color-accent-fg)', flexShrink: 0 }} />
                : <HardDrive size={13} style={{ color: 'var(--color-accent-fg)', flexShrink: 0 }} />}
              <div className="min-w-0 flex-1">
                <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-text)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.01em' }} className="truncate">
                  {activeSource.label}
                </div>
                <div style={{ fontSize: 9.5, color: 'var(--color-faint)', fontFamily: 'var(--font-mono)', marginTop: 2, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                  {activeSource.type}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div
            onClick={onOpenSources}
            className="cursor-pointer hover:border-[var(--color-border)] hover:text-[var(--color-muted)] transition-colors duration-150"
            style={{
              border: '1px dashed var(--color-border)',
              padding: '11px 10px',
              fontSize: 10.5,
              color: 'var(--color-faint)',
              borderRadius: '8px',
              textAlign: 'center',
              fontFamily: 'var(--font-sans)',
              fontWeight: 500,
            }}
          >
            {t.noDataset}
          </div>
        )}
      </div>

      {/* Oturum: kullanıcı bilgisi + çıkış */}
      {user && (
        <div style={{ padding: '8px 10px 10px', borderTop: '1px solid var(--color-border2)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 26, height: 26, borderRadius: 8, flexShrink: 0,
              background: 'linear-gradient(135deg, #c96442, #b8532f)',
              color: '#fff', fontSize: 11, fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              textTransform: 'uppercase',
            }}>
              {(user.display_name || user.username).charAt(0)}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {user.display_name || user.username}
              </div>
              <div style={{ fontSize: 9.5, color: user.role === 'admin' ? 'var(--color-accent-fg)' : 'var(--color-faint)' }}>
                {user.role === 'admin' ? 'Yönetici' : 'Kullanıcı'}
              </div>
            </div>
            <button
              onClick={logout}
              title="Çıkış yap"
              style={{
                width: 26, height: 26, borderRadius: 6, flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'transparent', border: '1px solid transparent',
                color: 'var(--color-faint)', cursor: 'pointer',
              }}
              className="hover:bg-[var(--color-surface2)] hover:text-[var(--color-danger)] transition-colors duration-150"
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
