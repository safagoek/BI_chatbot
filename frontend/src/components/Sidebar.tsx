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
      className="flex flex-col shrink-0 z-20 select-none overflow-hidden"
      style={{
        width: 240,
        height: '100vh',
        background: 'var(--color-bg)',
        borderRight: '1px solid var(--color-border)',
      }}
    >
      {/* ── Fluent Navigation Header ── */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{
          height: 56,
          background: 'var(--color-canvas)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Brand Icon — premium gradient with a subtle neon glow */}
          <div
            className="flex items-center justify-center shrink-0 shadow-[0_0_12px_rgba(99,102,241,0.35)]"
            style={{
              width: 28, height: 28,
              background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
              color: '#ffffff',
              borderRadius: '8px',
              fontSize: 10,
              fontWeight: 800,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.05em',
              flexShrink: 0,
            }}
          >
            BI
          </div>
          <div className="min-w-0">
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.015em', lineHeight: 1.2 }}>DeepBI</div>
            <div style={{ fontSize: 9.5, color: 'var(--color-muted)', fontFamily: 'var(--font-sans)', fontWeight: 500, letterSpacing: '0.02em', textTransform: 'uppercase' }}>Analytics Studio</div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => setLanguage(language === 'tr' ? 'en' : 'tr')}
            className="shrink-0 cursor-pointer hover:border-indigo-500/40 hover:text-indigo-400 transition-all duration-200"
            style={{
              padding: '3px 7px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
              color: 'var(--color-text-2)',
              fontSize: 10,
              fontWeight: 600,
              fontFamily: 'var(--font-sans)',
              cursor: 'pointer',
            }}
            title={language === 'tr' ? 'Switch to English' : "Türkçe'ye Geç"}
          >
            {language.toUpperCase()}
          </button>

          <button
            onClick={onToggleTheme}
            className="btn-icon shrink-0 cursor-pointer hover:border-indigo-500/40 hover:text-indigo-400 transition-all duration-200"
            style={{ padding: 5, borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            title={theme === 'dark' ? (language === 'tr' ? 'Aydınlık Mod' : 'Light Mode') : (language === 'tr' ? 'Karanlık Mod' : 'Dark Mode')}
          >
            {theme === 'dark' ? <Sun size={12} className="text-amber-400" /> : <Moon size={12} className="text-indigo-400" />}
          </button>
        </div>
      </div>

      {/* ── Fluent Navigation Rail Body ── */}
      <div className="flex-1 flex flex-col px-3 pt-4 pb-2 min-h-0 overflow-hidden">

        {/* Section label — Premium caption style */}
        <div
          className="flex items-center justify-between px-1 mb-2.5 shrink-0"
          style={{ fontSize: 9.5, color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}
        >
          <span>{t.notebooks}</span>
          <button
            onClick={() => setShowSourcePicker(true, 'create')}
            className="btn-icon cursor-pointer hover:border-indigo-500/40 hover:text-indigo-400 transition-all duration-200"
            style={{ padding: 4, borderRadius: '6px' }}
            title={language === 'tr' ? 'Yeni Çalışma Oturumu Aç' : 'Open New Study Session'}
          >
            <Plus size={12} />
          </button>
        </div>

        {/* Search — Premium SearchBox style */}
        <div className="px-0 mb-3 shrink-0">
          <input
            value={sessionFilter}
            onChange={(e) => setSessionFilter(e.target.value)}
            placeholder={t.search}
            className="input w-full hover:border-indigo-500/20 focus:border-indigo-500/50 transition-all duration-200"
            style={{ paddingTop: 6, paddingBottom: 6, fontSize: 11, borderRadius: '8px', fontFamily: 'var(--font-mono)' }}
          />
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto space-y-1.5 pr-0.5 min-h-0 scrollbar-thin">
          {filteredSessions.map(s => {
            const active = activeSessionId === s.id;
            const isEditing = editingSessionId === s.id;
            return (
              <div
                key={s.id}
                onClick={() => !isEditing && selectSession(s.id)}
                className={`flex items-center justify-between group cursor-pointer transition-all duration-200 rounded-lg ${
                  active 
                    ? 'bg-indigo-500/10 border border-indigo-500/20 shadow-[0_0_8px_rgba(99,102,241,0.05)]' 
                    : 'hover:bg-gh-surface border border-transparent hover:border-gh-border/50'
                }`}
                style={{ padding: '6px 10px' }}
              >
                {isEditing ? (
                  <div className="flex items-center gap-2 min-w-0 flex-1" onClick={(e) => e.stopPropagation()}>
                    <FileText size={11} style={{ color: '#6366f1', flexShrink: 0 }} />
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
                      className="bg-transparent border-b border-indigo-500 text-xs text-gh-text outline-none w-full font-mono"
                      style={{ fontSize: 11 }}
                    />
                  </div>
                ) : (
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <div 
                      className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                        active 
                          ? 'bg-indigo-500 shadow-[0_0_6px_#6366f1] scale-110' 
                          : 'bg-zinc-500/40 group-hover:bg-zinc-400'
                      }`}
                    />
                    <span
                      className="truncate flex-1 font-mono text-[11px] font-medium"
                      style={{ color: active ? 'var(--color-text)' : 'var(--color-muted)' }}
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
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all shrink-0">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingSessionId(s.id);
                        setEditingTitle(s.title);
                      }}
                      className="btn-icon cursor-pointer hover:text-indigo-400 hover:border-indigo-500/40 transition-colors"
                      style={{ padding: 2.5, borderRadius: '4px' }}
                      title={language === 'tr' ? 'Yeniden Adlandır' : 'Rename'}
                    >
                      <Edit size={10} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                      className="btn-icon cursor-pointer hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/30 transition-colors"
                      style={{ padding: 2.5, color: 'var(--color-danger)', borderColor: 'transparent', borderRadius: '4px' }}
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
            <div className="px-2 py-6 text-center font-mono" style={{ fontSize: 10, color: 'var(--color-faint)' }}>
              {t.noResults}
            </div>
          )}
        </div>
      </div>

      {/* ── Fluent Active Dataset Section ── */}
      <div className="px-3 py-4 shrink-0" style={{ borderTop: '1px solid var(--color-border)' }}>
        <div
          className="flex items-center justify-between mb-2.5 px-1"
          style={{ fontSize: 9.5, color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}
        >
          <span>{t.activeDataset}</span>
          <button
            onClick={() => { fetchSources(); fetchFiles(); }}
            className="btn-icon cursor-pointer hover:border-indigo-500/40 hover:text-indigo-400 hover:rotate-180 transition-all duration-300"
            style={{ padding: 3, borderRadius: '4px' }}
            title={language === 'tr' ? 'Yenile' : 'Refresh'}
          >
            <RefreshCw size={10} />
          </button>
        </div>

        {activeSource ? (
          <div
            onClick={onOpenSources}
            className="cursor-pointer transition-all duration-200 hover:-translate-y-[1px] hover:shadow-md"
            style={{
              background: 'rgba(99, 102, 241, 0.04)',
              border: '1px solid rgba(99, 102, 241, 0.15)',
              borderLeft: '4px solid #6366f1',
              padding: '10px 12px',
              borderRadius: '10px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
            }}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              {activeSource.isDb
                ? <Database size={12} style={{ color: '#818cf8', flexShrink: 0 }} />
                : <HardDrive size={12} style={{ color: '#818cf8', flexShrink: 0 }} />}
              <div className="min-w-0 flex-1">
                <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--color-text)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.015em' }} className="truncate">
                  {activeSource.label}
                </div>
                <div style={{ fontSize: 9.5, color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', marginTop: 2, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.02em' }}>
                  {activeSource.type}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div
            onClick={onOpenSources}
            className="cursor-pointer hover:border-indigo-500/30 hover:text-indigo-400/80 transition-all duration-200"
            style={{
              border: '1.5px dashed var(--color-border)',
              padding: '12px 10px',
              fontSize: 10.5,
              color: 'var(--color-faint)',
              borderRadius: '10px',
              textAlign: 'center',
              fontFamily: 'var(--font-mono)',
              fontWeight: 500,
            }}
          >
            {t.noDataset}
          </div>
        )}
      </div>

      {/* ── Fluent Command Bar Footer ── */}
      <div
        className="px-3 py-3 shrink-0 flex items-center gap-2"
        style={{ borderTop: '1px solid var(--color-border)', background: 'var(--color-canvas)' }}
      >
        <button
          onClick={onOpenSources}
          className="btn btn-ghost cursor-pointer flex-1 hover:bg-indigo-500/10 hover:text-indigo-400 hover:border-indigo-500/20 transition-all duration-200"
          style={{ fontSize: 11.5, padding: '7px 12px', gap: 6, justifyContent: 'flex-start', borderRadius: '8px', border: '1px solid transparent', fontFamily: 'var(--font-mono)' }}
        >
          <Database size={12} className="text-zinc-400 group-hover:text-indigo-400" />
          <span>{t.sources}</span>
        </button>
        <button
          onClick={onOpenSettings}
          className="btn btn-ghost cursor-pointer flex-1 hover:bg-indigo-500/10 hover:text-indigo-400 hover:border-indigo-500/20 transition-all duration-200"
          style={{ fontSize: 11.5, padding: '7px 12px', gap: 6, justifyContent: 'flex-start', borderRadius: '8px', border: '1px solid transparent', fontFamily: 'var(--font-mono)' }}
        >
          <Settings size={12} className="text-zinc-400 group-hover:text-indigo-400" />
          <span>{t.settings}</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
