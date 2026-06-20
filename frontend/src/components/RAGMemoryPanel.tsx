import React, { useEffect, useState } from 'react';
import { useBIStore, BACKEND_BASE } from '../context/store';
import { Trash2, RefreshCw, ThumbsUp, ThumbsDown, Minus } from 'lucide-react';

interface RAGEntry {
  question: string;
  intent: string;
  source_id: string;
  feedback: string;
  execution_success: boolean;
}

const FEEDBACK_ICONS: Record<string, React.ReactNode> = {
  positive: <ThumbsUp size={11} style={{ color: '#10b981' }} />,
  negative: <ThumbsDown size={11} style={{ color: '#ef4444' }} />,
  neutral: <Minus size={11} style={{ color: '#6b7280' }} />,
};

const RAGMemoryPanel: React.FC = () => {
  const { language } = useBIStore();
  const [entries, setEntries] = useState<RAGEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [filter, setFilter] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_BASE}/api/rag/memory`);
      if (!res.ok) throw new Error();
      setEntries(await res.json());
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const b64 = (s: string) => btoa(encodeURIComponent(s).replace(/%([0-9A-F]{2})/g, (_, p1) => String.fromCharCode(parseInt(p1, 16))));

  const handleDelete = async (question: string) => {
    const key = b64(question);
    setDeletingKey(question);
    try {
      await fetch(`${BACKEND_BASE}/api/rag/memory/${key}`, { method: 'DELETE' });
      setEntries((prev) => prev.filter((e) => e.question !== question));
    } catch { /* silent */ } finally {
      setDeletingKey(null);
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm(language === 'tr' ? 'Tüm RAG belleği silinecek. Emin misiniz?' : 'All RAG memory will be deleted. Are you sure?')) return;
    setClearing(true);
    try {
      await fetch(`${BACKEND_BASE}/api/rag/memory`, { method: 'DELETE' });
      setEntries([]);
    } catch { /* silent */ } finally {
      setClearing(false);
    }
  };

  const filtered = entries.filter(
    (e) =>
      e.question.toLowerCase().includes(filter.toLowerCase()) ||
      e.source_id.toLowerCase().includes(filter.toLowerCase()) ||
      e.intent.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--color-bg)' }}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 shrink-0"
        style={{ height: 52, borderBottom: '1px solid var(--color-border)', background: 'var(--color-canvas)' }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.015em' }}>
            {language === 'tr' ? 'RAG Sorgu Belleği' : 'RAG Query Memory'}
          </div>
          <div style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'var(--font-mono)' }}>
            {entries.length} {language === 'tr' ? 'kayıtlı sorgu' : 'stored queries'}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="btn-icon cursor-pointer hover:border-indigo-500/40 hover:text-indigo-400 transition-all"
            style={{ padding: '5px 8px', borderRadius: 6, fontSize: 10, display: 'flex', alignItems: 'center', gap: 4 }}
            title={language === 'tr' ? 'Yenile' : 'Refresh'}
          >
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={handleClearAll}
            disabled={clearing || entries.length === 0}
            className="btn-icon cursor-pointer hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/30 transition-all"
            style={{ padding: '5px 8px', borderRadius: 6, fontSize: 10, display: 'flex', alignItems: 'center', gap: 4, color: 'var(--color-danger)' }}
          >
            <Trash2 size={11} />
            <span style={{ fontFamily: 'var(--font-mono)' }}>{language === 'tr' ? 'Tümünü Sil' : 'Clear All'}</span>
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="px-4 py-3 shrink-0" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={language === 'tr' ? 'Sorgu, kaynak veya intent ara...' : 'Search question, source, or intent...'}
          className="input w-full"
          style={{ fontSize: 11, padding: '6px 10px', borderRadius: 8 }}
        />
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        {loading ? (
          <div className="flex justify-center py-10" style={{ color: 'var(--color-faint)', fontSize: 11 }}>
            {language === 'tr' ? 'Yükleniyor...' : 'Loading...'}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-10" style={{ color: 'var(--color-faint)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
            {language === 'tr' ? 'Kayıt bulunamadı.' : 'No entries found.'}
          </div>
        ) : (
          filtered.map((entry) => (
            <div
              key={entry.question}
              style={{
                background: 'var(--color-canvas)',
                border: '1px solid var(--color-border)',
                borderRadius: 10,
                padding: '10px 14px',
                position: 'relative',
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div style={{ fontSize: 12, color: 'var(--color-text)', fontFamily: 'var(--font-sans)', fontWeight: 500, lineHeight: 1.4, wordBreak: 'break-word' }}>
                    {entry.question}
                  </div>
                  <div className="flex items-center gap-3 mt-2">
                    <span
                      style={{
                        fontSize: 9.5, fontFamily: 'var(--font-mono)', fontWeight: 600,
                        background: entry.intent === 'sql_query' ? 'rgba(6,182,212,0.1)' : 'rgba(168,85,247,0.1)',
                        color: entry.intent === 'sql_query' ? '#06b6d4' : '#a855f7',
                        border: `1px solid ${entry.intent === 'sql_query' ? 'rgba(6,182,212,0.2)' : 'rgba(168,85,247,0.2)'}`,
                        padding: '2px 6px', borderRadius: 4, textTransform: 'uppercase',
                      }}
                    >
                      {entry.intent}
                    </span>
                    <span style={{ fontSize: 9.5, color: 'var(--color-faint)', fontFamily: 'var(--font-mono)' }}>
                      {entry.source_id}
                    </span>
                    <span className="flex items-center gap-1" title={entry.feedback}>
                      {FEEDBACK_ICONS[entry.feedback] ?? FEEDBACK_ICONS.neutral}
                    </span>
                    {entry.execution_success ? (
                      <span style={{ fontSize: 9, color: '#10b981', fontFamily: 'var(--font-mono)' }}>✓ OK</span>
                    ) : (
                      <span style={{ fontSize: 9, color: '#ef4444', fontFamily: 'var(--font-mono)' }}>✗ ERR</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(entry.question)}
                  disabled={deletingKey === entry.question}
                  className="btn-icon shrink-0 cursor-pointer hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/30 transition-all"
                  style={{ padding: 5, borderRadius: 6, color: 'var(--color-danger)' }}
                  title={language === 'tr' ? 'Sil' : 'Delete'}
                >
                  <Trash2 size={11} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default RAGMemoryPanel;
