import React, { useState, useEffect } from 'react';
import { useBIStore } from '../context/store';
import { translations } from '../context/translations';
import {
  FileText, Database, Settings, RefreshCw,
  Plus, Trash2, Edit, HardDrive, Sun, Moon
} from 'lucide-react';

interface SidebarProps {
  onOpenSettings: () => void;
  onOpenSources: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onOpenSettings, onOpenSources, theme, onToggleTheme }) => {
  const {
    sources, files,
    activeSourceId,
    sessions, activeSessionId,
    selectSession, deleteSession, fetchSessions,
    renameSession,
    fetchSources, fetchFiles,
    setShowSourcePicker,
    language, setLanguage
  } = useBIStore();

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

  return (
    <aside
      className="flex flex-col border-r bg-gh-canvas border-gh-border shrink-0 z-20 select-none overflow-hidden"
      style={{ width: 240, height: '100vh' }}
    >
      {/* ── Brand Header ── */}
      <div
        className="flex items-center justify-between px-4 shrink-0 border-b border-gh-border"
        style={{ height: 48, background: 'var(--color-canvas)' }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Amber mark — no gradient, no rounded */}
          <div
            className="flex items-center justify-center shrink-0 font-black text-[9px] tracking-widest"
            style={{
              width: 26, height: 26,
              background: 'linear-gradient(135deg, var(--color-accent) 0%, var(--color-accent-fg) 100%)',
              color: '#ffffff',
              borderRadius: '6px',
              letterSpacing: '0.05em'
            }}
          >
            DB
          </div>
          <div className="min-w-0">
            <div className="font-bold text-xs text-gh-text tracking-tight truncate font-mono">DeepBI</div>
            <div className="text-[8px] text-gh-muted font-mono uppercase tracking-widest">Analytics Studio</div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => setLanguage(language === 'tr' ? 'en' : 'tr')}
            className="shrink-0 cursor-pointer font-mono font-bold text-[9px] border border-gh-border hover:border-gh-accent rounded transition-all"
            style={{
              padding: '3px 6px',
              background: 'var(--color-surface)',
              color: 'var(--color-accent)',
            }}
            title={language === 'tr' ? 'Switch to English' : "Türkçe'ye Geç"}
          >
            {language.toUpperCase()}
          </button>

          <button
            onClick={onToggleTheme}
            className="btn-icon shrink-0 cursor-pointer"
            style={{ padding: 5 }}
            title={theme === 'dark' ? (language === 'tr' ? 'Aydınlık Mod' : 'Light Mode') : (language === 'tr' ? 'Karanlık Mod' : 'Dark Mode')}
          >
            {theme === 'dark' ? <Sun size={12} /> : <Moon size={12} />}
          </button>
        </div>
      </div>

      {/* ── Analiz Defterleri ── */}
      <div className="flex-1 flex flex-col px-3 pt-3 pb-2 min-h-0 overflow-hidden">

        {/* Section label */}
        <div
          className="flex items-center justify-between px-1 mb-2 shrink-0"
          style={{ fontSize: 9, color: 'var(--color-accent)', fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.10em', textTransform: 'uppercase' }}
        >
          <span>{t.notebooks}</span>
          <button
            onClick={() => setShowSourcePicker(true, 'create')}
            className="btn-icon cursor-pointer"
            style={{ padding: 3 }}
            title={language === 'tr' ? 'Yeni Çalışma Oturumu Aç' : 'Open New Study Session'}
          >
            <Plus size={11} />
          </button>
        </div>

        {/* Search */}
        <div className="px-0 mb-2 shrink-0">
          <input
            value={sessionFilter}
            onChange={(e) => setSessionFilter(e.target.value)}
            placeholder={t.search}
            className="input text-xs w-full"
            style={{ paddingTop: 5, paddingBottom: 5, fontSize: 11 }}
          />
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto space-y-px pr-0.5 min-h-0">
          {filteredSessions.map(s => {
            const active = activeSessionId === s.id;
            const isEditing = editingSessionId === s.id;
            return (
              <div
                key={s.id}
                onClick={() => !isEditing && selectSession(s.id)}
                className={`flex items-center justify-between group cursor-pointer transition-all ${
                  active ? 'nav-item active' : 'nav-item'
                }`}
                style={{ padding: '6px 8px' }}
              >
                {isEditing ? (
                  <div className="flex items-center gap-2 min-w-0 flex-1" onClick={(e) => e.stopPropagation()}>
                    <FileText size={11} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
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
                      className="bg-transparent border-b border-gh-accent text-xs text-gh-text outline-none w-full font-mono"
                      style={{ fontSize: 11 }}
                    />
                  </div>
                ) : (
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span
                      className="font-mono"
                      style={{ color: active ? 'var(--color-accent)' : 'var(--color-faint)', fontSize: 9 }}
                    >›</span>
                    <span
                      className="truncate flex-1 font-mono"
                      style={{ fontSize: 11, color: active ? 'var(--color-accent)' : 'var(--color-muted)' }}
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
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-all shrink-0">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingSessionId(s.id);
                        setEditingTitle(s.title);
                      }}
                      className="btn-icon cursor-pointer"
                      style={{ padding: 2 }}
                      title={language === 'tr' ? 'Yeniden Adlandır' : 'Rename'}
                    >
                      <Edit size={9} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                      className="btn-icon cursor-pointer"
                      style={{ padding: 2, color: 'var(--color-danger)', borderColor: 'var(--color-danger)' }}
                      title={language === 'tr' ? 'Oturumu Kapat' : 'Close Session'}
                    >
                      <Trash2 size={9} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}

          {filteredSessions.length === 0 && (
            <div className="px-2 py-4 text-center font-mono" style={{ fontSize: 10, color: 'var(--color-faint)' }}>
              {t.noResults}
            </div>
          )}
        </div>
      </div>

      {/* ── Aktif Veri Kümesi ── */}
      <div className="px-3 py-3 shrink-0" style={{ borderTop: '1px solid var(--color-border)' }}>
        <div
          className="flex items-center justify-between mb-2"
          style={{ fontSize: 9, color: 'var(--color-accent)', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, letterSpacing: '0.10em', textTransform: 'uppercase' }}
        >
          <span>{t.activeDataset}</span>
          <button
            onClick={() => { fetchSources(); fetchFiles(); }}
            className="btn-icon cursor-pointer"
            style={{ padding: 2 }}
            title={language === 'tr' ? 'Yenile' : 'Refresh'}
          >
            <RefreshCw size={9} />
          </button>
        </div>

        {activeSource ? (
          <div
            onClick={onOpenSources}
            className="cursor-pointer transition-all"
            style={{
              borderLeft: '3px solid var(--color-accent)',
              background: 'var(--color-accent-subtle)',
              border: '1px solid var(--color-border)',
              borderLeftColor: 'var(--color-accent)',
              borderLeftWidth: 3,
              padding: '8px 10px',
              borderRadius: '10px'
            }}
          >
            <div className="flex items-center gap-2 min-w-0">
              {activeSource.isDb
                ? <Database size={11} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />
                : <HardDrive size={11} style={{ color: 'var(--color-accent)', flexShrink: 0 }} />}
              <div className="min-w-0 flex-1">
                <div className="font-bold truncate font-mono" style={{ fontSize: 11, color: 'var(--color-text)' }}>
                  {activeSource.label}
                </div>
                <div className="font-mono uppercase tracking-widest" style={{ fontSize: 8, color: 'var(--color-muted)', marginTop: 1 }}>
                  {activeSource.type}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div
            onClick={onOpenSources}
            className="cursor-pointer transition-all font-mono text-center"
            style={{
              border: '1px dashed var(--color-border)',
              padding: '8px 10px',
              fontSize: 10,
              color: 'var(--color-faint)',
              borderRadius: '10px'
            }}
          >
            {t.noDataset}
          </div>
        )}
      </div>

      {/* ── Footer Actions ── */}
      <div
        className="px-3 py-2.5 shrink-0 grid grid-cols-2 gap-1.5"
        style={{ borderTop: '1px solid var(--color-border)', background: 'var(--color-bg)' }}
      >
        <button
          onClick={onOpenSources}
          className="btn btn-ghost cursor-pointer"
          style={{ fontSize: 10, padding: '6px 10px', gap: 5 }}
        >
          <Database size={11} />
          <span>{t.sources}</span>
        </button>
        <button
          onClick={onOpenSettings}
          className="btn btn-ghost cursor-pointer"
          style={{ fontSize: 10, padding: '6px 10px', gap: 5 }}
        >
          <Settings size={11} />
          <span>{t.settings}</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
