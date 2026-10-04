import React, { useState, useEffect, useRef } from 'react';
import { useBIStore, type JoinRelation, type Message } from '../context/store';
import { apiFetch } from '../api/client';
import { translations } from '../context/translations';
import {
  Send, ChevronDown, ChevronRight,
  Copy, Check, RotateCcw, Play, Edit3, X, Search, Plus,
  Database, FileText, Trash2, Layers, GitCommit, Download,
  Loader2, CheckCircle2, Circle, Sparkles, User, FileCode,
  ThumbsUp, ThumbsDown, Link, Zap, AlertTriangle, Pin,
  BarChart2, Table as TableIcon, Maximize2
} from 'lucide-react';
import { useCompareStore } from './compareStore';




// Autocomplete commands defined dynamically inside ChatConsole component

/* ── Kayıtlı analiz (saved analysis) satırı ── */
interface SaveRow {
  id: string;
  title: string;
  question: string;
  source_ids: string[];
  relationships: any[];
  created_at: string;
}

/* ── Extract KPI metrics from markdown text ── */
const extractKPIs = (text: string) => {
  const kpis: { label: string; value: string }[] = [];
  const re = /(?:toplam|ortalama|en yüksek|tahmin edilen|beklenen)?\s*\**([a-zA-Z0-9_ğüşöçİĞÜŞÖÇ\s\-]{3,30})\**\s*(?:değeri)?:\s*\*\*(.*?)\*\*/gi;
  let m;
  const tempText = text;
  while ((m = re.exec(tempText)) !== null) {
    if (m[1] && m[2]) {
      const label = m[1].trim();
      const value = m[2].trim();
      if (/[\d\%\$\€\£\.\,]+/.test(value) && label.length < 35 && value.length < 25) {
        kpis.push({ label, value });
      }
    }
  }
  return kpis.slice(0, 3);
};

/* ── Simple Python & SQL Syntax Highlighter with Premium Nord theme ── */
const highlightCode = (code: string, lang: 'python' | 'sql' | string) => {
  if (!code) return '';
  const escaped = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Extract strings & comments first
  const stringsAndComments: string[] = [];
  let tokenized = escaped.replace(/('.*?'|".*?"|#.*|--.*)/g, (match) => {
    stringsAndComments.push(match);
    return `___STR_PLACEHOLDER_${stringsAndComments.length - 1}___`;
  });

  if (lang === 'sql') {
    tokenized = tokenized.replace(
      /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|ON|GROUP BY|ORDER BY|LIMIT|AND|OR|AS|CREATE TABLE|INSERT INTO|DELETE|UPDATE|SET|PRAGMA|NULL|DESCRIBE|UNION|ALL|HAVING)\b/gi,
      '<span class="font-semibold" style="color:var(--color-accent)">$1</span>'
    ).replace(
      /\b(COUNT|SUM|AVG|MIN|MAX|ROUND|COALESCE|CAST|NOW|DATE|INTERVAL)\b/gi,
      '<span style="color:var(--color-warning)">$1</span>'
    ).replace(
      /\b(\d+)\b/g,
      '<span style="color:var(--color-done)">$1</span>'
    );
  } else if (lang === 'python') {
    tokenized = tokenized.replace(
      /\b(def|import|from|class|return|if|else|elif|for|while|try|except|as|in|is|not|and|or|print|lambda|with|assert|pass|break|continue)\b/g,
      '<span class="font-semibold" style="color:var(--color-accent)">$1</span>'
    ).replace(
      /\b(self|pd|np|plt|sns|go|px|sqlite3|conn|df|columns|rows|px|dict|list|str|int|float|set|tuple|len|range)\b/g,
      '<span style="color:var(--color-warning)">$1</span>'
    ).replace(
      /\b(\d+)\b/g,
      '<span style="color:var(--color-done)">$1</span>'
    );
  }

  // Restore strings and comments
  const restored = tokenized.replace(/___STR_PLACEHOLDER_(\d+)___/g, (_, index) => {
    const rawMatch = stringsAndComments[parseInt(index, 10)];
    if (rawMatch.startsWith('#') || rawMatch.startsWith('--')) {
      return `<span class="text-zinc-500 italic">${rawMatch}</span>`;
    }
    return `<span class="font-medium" style="color:var(--color-success)">${rawMatch}</span>`;
  });

  return restored;
};


/* ── Minimal markdown renderer ── */
const renderText = (text: string = '') =>
  text.split('\n').map((line, i) => {
    const boldAndItalic = (s: string) => {
      const parts: React.ReactNode[] = [];
      let last = 0;
      // Bold Regex
      const re = /\*\*(.*?)\*\*/g;
      let m;
      while ((m = re.exec(s)) !== null) {
        if (m.index > last) parts.push(s.slice(last, m.index));
        parts.push(<strong key={`b${i}-${m.index}`} className="text-gh-text font-bold dark:text-zinc-100 text-zinc-800">{m[1]}</strong>);
        last = re.lastIndex;
      }
      if (last < s.length) parts.push(s.slice(last));
      return parts.length ? parts : s;
    };

    if (line.startsWith('### ')) {
      return <h4 key={i} className="text-[11px] font-bold text-gh-accent-fg uppercase tracking-widest mt-4 mb-2 font-mono flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-gh-accent"></span>{line.replace('### ', '')}</h4>;
    }
    if (line.startsWith('## ')) {
      return <h3 key={i} className="text-xs font-bold text-zinc-200 mt-5 mb-2 font-mono uppercase tracking-wider border-b border-zinc-800/40 pb-1.5">{line.replace('## ', '')}</h3>;
    }
    if (line.startsWith('- ')) {
      return <li key={i} className="text-xs text-zinc-400 dark:text-zinc-300 ml-4 list-disc mt-1.5 leading-relaxed font-mono">{boldAndItalic(line.replace('- ', ''))}</li>;
    }
    if (line.trim() === '') {
      return <div key={i} className="h-2" />;
    }
    return <p key={i} className="text-xs text-zinc-400 dark:text-zinc-300 leading-relaxed mt-1 font-mono">{boldAndItalic(line)}</p>;
  });

/* ── Inline result: chart + table rendered inside the agent bubble ── */
const InlineResult: React.FC<{
  msg: Message;
  studioMode: boolean;
  onOpenStudio: () => void;
  language: string;
  onPin?: () => void;
  pinnedNow?: boolean;
}> = ({ msg, studioMode, onOpenStudio, language, onPin, pinnedNow }) => {
  const [tableOpen, setTableOpen] = useState(false);
  const [isDark, setIsDark] = useState(() =>
    typeof document !== 'undefined' ? document.documentElement.classList.contains('dark') : false
  );
  const plotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const obs = new MutationObserver(() =>
      setIsDark(document.documentElement.classList.contains('dark'))
    );
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => obs.disconnect();
  }, []);

  const hasViz = !!msg.visualization && Array.isArray(msg.visualization.data) && msg.visualization.data.length > 0;
  const msgData = msg.data;
  const hasData = !!msgData && Array.isArray(msgData.columns) && msgData.columns.length > 0;
  const columns: string[] = hasData ? msgData.columns : [];
  const previewRows: any[][] = hasData ? (msgData.rows || []).slice(0, 10) : [];
  const totalRows = hasData ? (msgData.row_count ?? (msgData.rows || []).length) : 0;

  /* Plotly render (theme-adaptive layout from msg.visualization) */
  useEffect(() => {
    if (!hasViz || studioMode || !plotRef.current || !window.Plotly) return;
    try {
      const baseLayout = msg.visualization?.layout || {};
      const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(28,25,23,0.08)';
      const lineColor = isDark ? 'rgba(255,255,255,0.14)' : 'rgba(28,25,23,0.15)';
      const textColor = isDark ? '#a1a1aa' : '#57534e';
      const layout = {
        ...baseLayout,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        template: isDark ? 'plotly_dark' : 'plotly_white',
        font: { ...(baseLayout.font || {}), color: textColor, family: 'Inter, sans-serif', size: 11 },
        xaxis: {
          ...(baseLayout.xaxis || {}),
          gridcolor: gridColor,
          linecolor: lineColor,
          tickfont: { ...(baseLayout.xaxis?.tickfont || {}), size: 10 }
        },
        yaxis: {
          ...(baseLayout.yaxis || {}),
          gridcolor: gridColor,
          linecolor: lineColor,
          tickfont: { ...(baseLayout.yaxis?.tickfont || {}), size: 10 }
        },
        margin: { ...(baseLayout.margin || {}), t: 28, r: 16, l: 52, b: 42 },
        autosize: true
      };
      window.Plotly.react(plotRef.current, msg.visualization.data, layout, { responsive: true, displayModeBar: false });
    } catch (err) {
      console.error('Inline Plotly render error', err);
    }
  }, [hasViz, studioMode, isDark, msg.id, msg.visualization]);

  /* Resize with window */
  useEffect(() => {
    if (!hasViz || studioMode) return;
    const onResize = () => {
      if (plotRef.current && window.Plotly) {
        try { window.Plotly.Plots.resize(plotRef.current); } catch { /* noop */ }
      }
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [hasViz, studioMode]);

  /* Studio mode: compact preview + open button instead of full inline result */
  if (studioMode) {
    return (
      <div
        className="flex items-center justify-between gap-3 mb-4 px-3.5 py-2.5"
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 10
        }}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className="flex-shrink-0 w-7 h-7 flex items-center justify-center"
            style={{ background: 'var(--color-accent-subtle)', borderRadius: 8 }}
          >
            {hasViz ? <BarChart2 size={13} style={{ color: 'var(--color-accent-fg)' }} /> : <TableIcon size={13} style={{ color: 'var(--color-accent-fg)' }} />}
          </div>
          <div className="min-w-0">
            <div className="text-[11px] font-semibold font-mono truncate" style={{ color: 'var(--color-text)' }}>
              {hasViz ? (language === 'tr' ? 'Grafik hazır' : 'Chart ready') : (language === 'tr' ? 'Tablo hazır' : 'Table ready')}
            </div>
            <div className="text-[10px] font-mono" style={{ color: 'var(--color-faint)' }}>
              {totalRows > 0 ? `${totalRows} ${language === 'tr' ? 'satır' : 'rows'}` : (language === 'tr' ? 'Sonuç stüdyoda görüntüleniyor' : 'Result shown in Studio')}
            </div>
          </div>
        </div>
        <div className="flex-shrink-0 flex items-center gap-1.5">
          {onPin && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onPin(); }}
              className="flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-bold font-mono cursor-pointer transition-all"
              style={{
                background: pinnedNow ? 'var(--color-accent-subtle2)' : 'var(--color-surface)',
                color: pinnedNow ? 'var(--color-accent-fg)' : 'var(--color-muted)',
                border: '1px solid var(--color-border)',
                borderRadius: 8
              }}
              title={language === 'tr' ? 'Karşılaştırma için sabitle' : 'Pin for comparison'}
            >
              <Pin size={11} />
              {pinnedNow
                ? (language === 'tr' ? 'Sabitlendi' : 'Pinned')
                : (language === 'tr' ? '◫ Sabitle' : '◫ Pin')}
            </button>
          )}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onOpenStudio(); }}
            className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-bold font-mono cursor-pointer transition-all"
            style={{
              background: 'var(--color-accent-subtle)',
              color: 'var(--color-accent-fg)',
              border: '1px solid var(--color-border)',
              borderRadius: 8
            }}
          >
            <Maximize2 size={11} />
            {language === 'tr' ? '◫ Stüdyoda aç' : '◫ Open in Studio'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-4 select-text">
      <style>{`
        .inline-result-tbl tbody tr { transition: background-color 0.12s; }
        .inline-result-tbl tbody tr:hover { background: var(--color-surface); }
      `}</style>

      {/* Chart */}
      {hasViz && (
        <div
          className="mb-3"
          style={{
            background: 'var(--color-canvas)',
            border: '1px solid var(--color-border)',
            borderRadius: 10,
            padding: '8px 4px',
            boxShadow: '0 2px 6px rgba(28,25,23,0.06)'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div ref={plotRef} style={{ width: '100%', height: 360 }} />
        </div>
      )}

      {/* Table (first 10 rows, collapsible) */}
      {hasData && (
        <div
          style={{
            border: '1px solid var(--color-border)',
            borderRadius: 10,
            overflow: 'hidden'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            onClick={() => setTableOpen(o => !o)}
            className="w-full flex items-center justify-between px-3.5 py-2 cursor-pointer transition-colors hover:opacity-90"
            style={{ background: 'var(--color-surface)', border: 'none' }}
          >
            <span className="flex items-center gap-2 text-[10px] font-bold font-mono uppercase tracking-wider" style={{ color: 'var(--color-muted)' }}>
              📋 {language === 'tr' ? 'Tablo' : 'Table'}
              <span style={{ color: 'var(--color-faint)', fontWeight: 500 }}>{totalRows} {language === 'tr' ? 'satır' : 'rows'}</span>
            </span>
            {tableOpen ? <ChevronDown size={12} style={{ color: 'var(--color-faint)' }} /> : <ChevronRight size={12} style={{ color: 'var(--color-faint)' }} />}
          </button>
          {tableOpen && (
            <div style={{ overflowX: 'auto', maxHeight: 320, overflowY: 'auto' }}>
              <table className="inline-result-tbl" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr>
                    {columns.map(col => (
                      <th
                        key={col}
                        style={{
                          textAlign: 'left',
                          padding: '6px 10px',
                          background: 'var(--color-surface2)',
                          borderBottom: '1px solid var(--color-border)',
                          color: 'var(--color-muted)',
                          fontWeight: 600,
                          fontFamily: 'var(--font-mono)',
                          fontSize: 10,
                          whiteSpace: 'nowrap',
                          position: 'sticky',
                          top: 0
                        }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, rIdx) => (
                    <tr key={rIdx} style={{ borderBottom: '1px solid var(--color-border2)' }}>
                      {row.map((cell, cIdx) => (
                        <td
                          key={cIdx}
                          title={String(cell)}
                          style={{
                            padding: '5px 10px',
                            color: 'var(--color-text-2)',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 10.5,
                            whiteSpace: 'nowrap',
                            maxWidth: 220,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }}
                        >
                          {cell === null || cell === undefined ? <span style={{ fontStyle: 'italic', color: 'var(--color-faint)' }}>null</span> : String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {previewRows.length === 0 && (
                    <tr>
                      <td colSpan={columns.length} style={{ padding: 16, textAlign: 'center', color: 'var(--color-faint)', fontStyle: 'italic' }}>
                        {language === 'tr' ? 'Veri yok' : 'No data'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const ChatConsole: React.FC = () => {
  const chatHistory = useBIStore((s) => s.chatHistory);
  const isThinking = useBIStore((s) => s.isThinking);
  const sendMessage = useBIStore((s) => s.sendMessage);
  const clearChat = useBIStore((s) => s.clearChat);
  const activeSourceId = useBIStore((s) => s.activeSourceId);
  const activeSessionId = useBIStore((s) => s.activeSessionId);
  const updateMessageCode = useBIStore((s) => s.updateMessageCode);
  const sources = useBIStore((s) => s.sources);
  const files = useBIStore((s) => s.files);
  const selectedSourceIds = useBIStore((s) => s.selectedSourceIds);
  const setSelectedSourceIds = useBIStore((s) => s.setSelectedSourceIds);
  const joinRelations = useBIStore((s) => s.joinRelations);
  const setJoinRelations = useBIStore((s) => s.setJoinRelations);
  const sessions = useBIStore((s) => s.sessions);
  const showSourcePicker = useBIStore((s) => s.showSourcePicker);
  const sourcePickerMode = useBIStore((s) => s.sourcePickerMode);
  const setShowSourcePicker = useBIStore((s) => s.setShowSourcePicker);
  const createSession = useBIStore((s) => s.createSession);
  const setActiveSourceId = useBIStore((s) => s.setActiveSourceId);
  const language = useBIStore((s) => s.language);
  const activeMessageId = useBIStore((s) => s.activeMessageId);
  const setActiveMessageId = useBIStore((s) => s.setActiveMessageId);
  const studioMode = useBIStore((s) => s.studioMode);
  const setStudioMode = useBIStore((s) => s.setStudioMode);
  const pinnedResult = useCompareStore((s) => s.pinned);
  const pinResult = useCompareStore((s) => s.pinResult);


  const t = translations[language];

  const [input, setInput] = useState('');
  const [showSqlPreview, setShowSqlPreview] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [codeOpen, setCodeOpen] = useState<Record<string, boolean>>({});
  const [logOpen, setLogOpen] = useState<Record<string, boolean>>({});
  const [sourceSearch, setSourceSearch] = useState('');

  // Interactive Editor States
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editedCodeText, setEditedCodeText] = useState<string>('');
  const [isExecutingCode, setIsExecutingCode] = useState<boolean>(false);
  const [executionError, setExecutionError] = useState<string | null>(null);

  // Command Palette States
  const [selectedCmdIndex, setSelectedCmdIndex] = useState(0);

  // Thumbs Feedback & Interactive Schema Selection States (Suggestion 2 & 6)
  const [messageRatings, setMessageRatings] = useState<Record<string, 'positive' | 'negative'>>({});
  const [selectedCol, setSelectedCol] = useState<{ sourceId: string; tableName?: string; columnName: string } | null>(null);
  const [_redrawTrigger, setRedrawTrigger] = useState(0);

  // Saved analyses states (Görev 1)
  const [saves, setSaves] = useState<SaveRow[]>([]);
  const [saveFormFor, setSaveFormFor] = useState<string | null>(null);
  const [saveTitle, setSaveTitle] = useState('');
  const [saveQuestion, setSaveQuestion] = useState('');
  const [savingInProgress, setSavingInProgress] = useState(false);
  const [saveDoneId, setSaveDoneId] = useState<string | null>(null);

  useEffect(() => {
    if (showSourcePicker) {
      // Force several redraw ticks to ensure DOM is fully settled
      const timer1 = setTimeout(() => setRedrawTrigger(t => t + 1), 50);
      const timer2 = setTimeout(() => setRedrawTrigger(t => t + 1), 150);
      const timer3 = setTimeout(() => setRedrawTrigger(t => t + 1), 350);
      const timer4 = setTimeout(() => setRedrawTrigger(t => t + 1), 600);
      
      const handleResize = () => setRedrawTrigger(t => t + 1);
      window.addEventListener('resize', handleResize);
      
      return () => {
        clearTimeout(timer1);
        clearTimeout(timer2);
        clearTimeout(timer3);
        clearTimeout(timer4);
        window.removeEventListener('resize', handleResize);
      };
    }
  }, [showSourcePicker, joinRelations, selectedCol, selectedSourceIds]);

  const handleFeedback = async (messageId: string, rating: 'positive' | 'negative') => {
    try {
      setMessageRatings(p => ({ ...p, [messageId]: rating }));
      await apiFetch(`/api/sessions/${activeSessionId}/messages/${messageId}/feedback`, {
        method: 'POST',
        body: JSON.stringify({ type: rating })
      });
      console.log("Feedback recorded successfully.");
    } catch (err) {
      console.error("Feedback submission error", err);
    }
  };

  /* ── Kayıtlı analizler (saved analyses) ── */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await apiFetch<SaveRow[]>('/api/saves');
        if (!cancelled) setSaves(Array.isArray(rows) ? rows : []);
      } catch (err) {
        console.error('Saved analyses load error', err);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const openSaveForm = (messageId: string, question: string) => {
    setSaveFormFor(messageId);
    setSaveQuestion(question.trim());
    setSaveTitle(question.trim().slice(0, 40));
  };

  const cancelSaveForm = () => {
    setSaveFormFor(null);
    setSaveTitle('');
    setSaveQuestion('');
  };

  const submitSave = async (messageId: string) => {
    const title = saveTitle.trim();
    if (!title || savingInProgress) return;
    setSavingInProgress(true);
    try {
      const row = await apiFetch<SaveRow>('/api/saves', {
        method: 'POST',
        body: JSON.stringify({
          title,
          question: saveQuestion || title,
          source_ids: selectedSourceIds,
          relationships: joinRelations
        })
      });
      if (row && row.id) {
        setSaves(prev => [...prev, row]);
      }
      setSaveFormFor(null);
      setSaveTitle('');
      setSaveQuestion('');
      setSaveDoneId(messageId);
      setTimeout(() => setSaveDoneId(cur => (cur === messageId ? null : cur)), 2500);
    } catch (err) {
      console.error('Save analysis error', err);
    } finally {
      setSavingInProgress(false);
    }
  };

  const deleteSave = async (id: string) => {
    try {
      await apiFetch(`/api/saves/${id}`, { method: 'DELETE' });
      setSaves(prev => prev.filter(s => s.id !== id));
    } catch (err) {
      console.error('Saved analysis delete error', err);
    }
  };

  const runSavedAnalysis = (save: SaveRow) => {
    if (isThinking) return;
    if (Array.isArray(save.source_ids) && save.source_ids.length > 0) {
      setSelectedSourceIds(save.source_ids);
    }
    if (Array.isArray(save.relationships) && save.relationships.length > 0) {
      setJoinRelations(save.relationships as JoinRelation[]);
    }
    sendMessage(save.question);
  };

  const pinMessageResult = (msg: Message, question: string) => {
    pinResult({
      messageId: msg.id,
      title: (question.trim() || msg.text?.trim() || '').slice(0, 60) || (language === 'tr' ? 'Analiz' : 'Analysis'),
      data: msg.data,
      visualization: msg.visualization
    });
  };

  const commands = React.useMemo(() => [
    { cmd: '/graph', desc: language === 'tr' ? 'Plotly ile etkileşimli veri görselleştirme grafiği çizdirin' : 'Draw an interactive data visualization chart with Plotly', template: '/graph ' },
    { cmd: '/ask', desc: language === 'tr' ? 'Genel sorular sorabilirsiniz' : 'You can ask general questions', template: '/ask ' },
    { cmd: '/ml', desc: language === 'tr' ? 'Python ML sandbox ortamında tahminleme ve modelleme koşturun' : 'Run forecasting and modeling in the Python ML sandbox environment', template: '/ml ' },
    { cmd: '/table', desc: language === 'tr' ? 'Sorguları tablo formatında temiz veri listesi halinde getirin' : 'Get queries in tabular format as a clean data list', template: '/table ' },
    { cmd: '/sqlquery', desc: language === 'tr' ? 'DuckDB/Veritabanı üzerinde doğrudan SQL sorgusu çalıştırın' : 'Execute SQL queries directly on DuckDB/Database', template: '/sqlquery ' },
    { cmd: '/pythonscript', desc: language === 'tr' ? 'Sandbox üzerinde özel Python/Pandas veri işleme betiği çalıştırın' : 'Run custom Python/Pandas data processing scripts in sandbox', template: '/pythonscript ' },
    { cmd: '/explain', desc: language === 'tr' ? 'Seçili veri kümesinin şemasını, özet istatistiklerini ve alan açıklamalarını analiz edip açıklayın' : 'Analyze and explain the active dataset\'s schema, summary statistics, and column descriptions', template: '/explain' },
    { cmd: '/forecast', desc: language === 'tr' ? 'Belirli bir sayısal kolon/metrik için zaman serisi tahmini ve trend projeksiyonu yapın' : 'Perform time-series forecasting and trend projection on a specific column/metric', template: '/forecast ' },
    { cmd: '/clean', desc: language === 'tr' ? 'Eksik verileri (NULL), anormal aykırı değerleri (outliers) analiz edin ve temizleme önerileri sunun' : 'Analyze missing values (NULL), anomalies/outliers, and provide automated cleaning suggestions', template: '/clean ' },
    { cmd: '/pivot', desc: language === 'tr' ? 'Verileri gruplamak ve alt toplamlar oluşturmak için dinamik pivot analizi gerçekleştirin' : 'Perform dynamic pivot analysis to group data and generate sub-totals', template: '/pivot ' },
    { cmd: '/corr', desc: language === 'tr' ? 'Sayısal değişkenler arasındaki korelasyon ilişkilerini ve istatistiksel bağımlılıkları hesaplayın' : 'Calculate correlation values and statistical dependencies between numerical columns', template: '/corr ' },
    { cmd: '/help', desc: language === 'tr' ? 'Analytics Studio analiz motoru kullanım rehberi ve gelişmiş prompt ipuçlarını görüntüleyin' : 'Display Analytics Studio analytics engine usage guide and advanced prompt engineering tips', template: '/help' }
  ], [language]);

  const filteredCommands = React.useMemo(() => {
    if (!input.startsWith('/')) return [];
    const query = input.toLowerCase();
    return commands.filter(c => c.cmd.startsWith(query));
  }, [input, commands]);

  const showAutocomplete = input.startsWith('/') && !input.includes(' ') && filteredCommands.length > 0;

  const selectCommand = (template: string) => {
    const resolvedTemplate = template.replace(/{dataset}/g, srcLabel);
    setInput(resolvedTemplate);
    setSelectedCmdIndex(0);
    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (showAutocomplete) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedCmdIndex(prev => (prev + 1) % filteredCommands.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedCmdIndex(prev => (prev - 1 + filteredCommands.length) % filteredCommands.length);
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        if (filteredCommands[selectedCmdIndex]) {
          selectCommand(filteredCommands[selectedCmdIndex].template);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setInput('');
      }
    }
  };

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const cmdPaletteRef = useRef<HTMLDivElement>(null);

  // Auto-scroll selected command item into view inside the palette container
  useEffect(() => {
    if (showAutocomplete && cmdPaletteRef.current) {
      const container = cmdPaletteRef.current;
      const selectedElement = container.children[selectedCmdIndex + 1] as HTMLElement;
      if (selectedElement) {
        const containerHeight = container.clientHeight;
        const elemTop = selectedElement.offsetTop;
        const elemHeight = selectedElement.clientHeight;
        
        // Auto scroll viewport adjustments with header buffer consideration
        if (elemTop < container.scrollTop + 32) {
          container.scrollTop = Math.max(0, elemTop - 32);
        } else if (elemTop + elemHeight > container.scrollTop + containerHeight) {
          container.scrollTop = elemTop + elemHeight - containerHeight;
        }
      }
    }
  }, [selectedCmdIndex, showAutocomplete]);

  const allSources = React.useMemo(() => {
    const dbSources = sources.map(s => ({
      id: s.id,
      label: s.display_name,
      type: 'database' as const,
      schema: s.schema
    }));
    const fileSources = files.map(f => ({
      id: f.id,
      label: f.alias,
      type: 'file' as const,
      schema: f.schema
    }));
    return [...dbSources, ...fileSources];
  }, [sources, files]);

  const visibleSources = allSources.filter(s =>
    s.label.toLowerCase().includes(sourceSearch.trim().toLowerCase())
  );

  // Auto-initialize selectedSourceIds to have at least the first source selected
  useEffect(() => {
    if (selectedSourceIds.length === 0 && allSources.length > 0) {
      setSelectedSourceIds([allSources[0].id]);
    }
  }, [allSources, selectedSourceIds, setSelectedSourceIds]);

  const effectiveSourceIds = selectedSourceIds.length > 0
    ? selectedSourceIds
    : (allSources.length > 0 ? [allSources[0].id] : []);

  const activeSession = React.useMemo(() => {
    return sessions.find(s => s.id === activeSessionId);
  }, [sessions, activeSessionId]);

  const sessionTitle = activeSession ? activeSession.title : t.queryTitle;

  const srcLabel = React.useMemo(() => {
    const active = allSources.find(s => s.id === activeSourceId);
    return active ? active.label : (language === 'tr' ? 'Veri Kaynağı' : 'Data Source');
  }, [allSources, activeSourceId, language]);



  useEffect(() => {
    if (joinRelations.length === 0) return;
    const activeSet = new Set(effectiveSourceIds);
    const next = joinRelations.filter(r => activeSet.has(r.leftSourceId) && activeSet.has(r.rightSourceId));
    if (next.length !== joinRelations.length) {
      setJoinRelations(next);
    }
  }, [effectiveSourceIds.join('|'), joinRelations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isThinking]);

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    const t = input.trim();
    if (!t || isThinking) return;
    // If it looks like SQL, run local analysis to offer preview/corrections
    const looksLikeSql = /\bselect\b|\bfrom\b|\bjoin\b/i.test(t);
    if (looksLikeSql) {
      const analysis = analyzeSqlForPreview(t);
      if (analysis.unknowns.length > 0) {
        setPreviewData(analysis);
        setShowSqlPreview(true);
        return;
      }
    }
    sendMessage(t);
    setInput('');
  };

  const analyzeSqlForPreview = (sql: string) => {
    const refs: string[] = [];
    const re = /\bfrom\s+([\w\"\'\.]+)|\bjoin\s+([\w\"\'\.]+)/gi;
    let m;
    while ((m = re.exec(sql)) !== null) {
      const t = m[1] || m[2];
      if (!t) continue;
      let t_clean = t.trim().replace(/^['\"]|['\"]$/g, '');
      if (t_clean.includes('.')) t_clean = t_clean.split('.').pop() || t_clean;
      refs.push(t_clean.toLowerCase());
    }

    const allowed: string[] = [];
    allSources.forEach(s => {
      if (s.type === 'file') allowed.push(s.id.toLowerCase());
      else {
        if (s.schema) {
          Object.keys(s.schema).forEach(t => allowed.push(`${s.id}__${t}`.toLowerCase()));
        }
      }
    });

    const unknowns = refs.filter(r => r && !allowed.includes(r));

    // Simple candidate matching: allowed entries that contain unknown substring or vice versa
    const candidates: Record<string, string[]> = {};
    unknowns.forEach(u => {
      candidates[u] = allowed.filter(a => a.includes(u) || u.includes(a));
    });

    return { sql, refs, unknowns, allowed, candidates };
  };

  const confirmPreviewSend = (finalSql?: string) => {
    const toSend = finalSql ?? previewData.sql;
    sendMessage(toSend);
    setInput('');
    setShowSqlPreview(false);
    setPreviewData(null);
  };

  const cancelPreview = () => {
    setShowSqlPreview(false);
    setPreviewData(null);
  };

  const copyCode = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const downloadCode = (code: string, lang: string | null | undefined, msgId: string) => {
    const ext = lang === 'python' ? '.py' : lang === 'sql' ? '.sql' : '.txt';
    const filename = `${language === 'tr' ? 'analiz_kodu' : 'analysis_code'}_${msgId.slice(0, 8)}${ext}`;
    const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Interactive Re-Execution Logic
  const startEditing = (msgId: string, initialCode: string) => {
    setEditingMessageId(msgId);
    setEditedCodeText(initialCode);
    setExecutionError(null);
  };

  const cancelEditing = () => {
    setEditingMessageId(null);
    setEditedCodeText('');
    setExecutionError(null);
  };

  const handleRunEditedCode = async (msgId: string, lang: 'python' | 'sql') => {
    setIsExecutingCode(true);
    setExecutionError(null);

    try {
      const data = await apiFetch(`/api/sessions/${activeSessionId}/messages/${msgId}/execute`, {
        method: 'POST',
        body: JSON.stringify({
          code: editedCodeText,
          code_language: lang,
          active_source_id: activeSourceId,
          source_ids: selectedSourceIds,
          relationships: joinRelations
        })
      });

      if (data.success) {
        updateMessageCode(msgId, editedCodeText, data.data, data.visualization, data.final_response, undefined, data.auto_corrections);
        setEditingMessageId(null);
      } else {
        setExecutionError(data.error);
        updateMessageCode(msgId, editedCodeText, null, null, data.final_response, data.error, data.auto_corrections);
      }
    } catch (e: any) {
      setExecutionError(e.message || (language === 'tr' ? "Bilinmeyen bir hata oluştu." : "An unknown error occurred."));
    } finally {
      setIsExecutingCode(false);
    }
  };

  const resolvedActiveMessageId = React.useMemo(() => {
    if (activeMessageId) return activeMessageId;
    const messagesWithData = chatHistory.filter(m => m.data || m.visualization || m.error);
    return messagesWithData.length > 0 ? messagesWithData[messagesWithData.length - 1].id : null;
  }, [chatHistory, activeMessageId]);

  // Last successful agent message (data or visualization, no error) — "💾 Kaydet" target
  const lastSuccessAgentIdx = React.useMemo(() => {
    for (let i = chatHistory.length - 1; i >= 0; i--) {
      const m = chatHistory[i];
      if (m.role === 'agent' && !m.error && (m.data || m.visualization)) return i;
    }
    return -1;
  }, [chatHistory]);

  const activateMessageForIndex = (idx: number) => {
    const clickedMsg = chatHistory[idx];
    if (!clickedMsg) return;
    if (clickedMsg.role === 'user') {
      const nextAgentMsg = chatHistory.slice(idx + 1).find(m => m.role === 'agent' && (m.data || m.visualization || m.error));
      if (nextAgentMsg) {
        setActiveMessageId(nextAgentMsg.id);
      }
    } else if (clickedMsg.role === 'agent' && (clickedMsg.data || clickedMsg.visualization || clickedMsg.error)) {
      setActiveMessageId(clickedMsg.id);
    }
  };

  const isEmpty = chatHistory.length === 0 && !isThinking;

  // Composer source chip
  const chipSource = allSources.find(s => s.id === activeSourceId)
    || allSources.find(s => s.id === effectiveSourceIds[0])
    || null;
  const chipExtraCount = Math.max(0, selectedSourceIds.length - 1);


  return (
    <div className="flex flex-col bg-gh-bg overflow-hidden" style={{ flex: 1, height: '100vh' }}>

      {/* ── Top bar ── */}
      <div
        className="flex items-center justify-between shrink-0 px-4 border-b border-gh-border"
        style={{ height: 48, background: 'var(--color-canvas)', borderBottom: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center gap-2.5">
          <span className="text-gh-accent font-mono font-bold" style={{ fontSize: 9 }}>›</span>
          <span className="text-xs font-mono font-bold text-gh-text tracking-tight truncate max-w-[340px]">
            {sessionTitle}
          </span>
          <div className="ml-2 flex gap-1 items-center">
            {selectedSourceIds.slice(0, 3).map(sid => {
              const src = allSources.find(a => a.id === sid);
              if (!src) return null;
              return (
                <div key={`chip-${sid}`} className="font-mono" style={{ fontSize: 9, padding: '1px 7px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-muted)', borderRadius: '6px' }}>{src.label}</div>
              );
            })}
            {selectedSourceIds.length > 3 && (
              <div className="font-mono" style={{ fontSize: 9, padding: '1px 7px', background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-faint)', borderRadius: '6px' }}>+{selectedSourceIds.length - 3}</div>
            )}
          </div>
        </div>

        <button
          onClick={clearChat}
          className="btn-icon cursor-pointer"
          style={{ padding: 5 }}
          title={t.clearChatTooltip}
        >
          <RotateCcw size={13} />
        </button>
      </div>

      {/* ── Çoklu Kaynak Seçim Çubuğu ── */}
      <div className="border-b border-gh-border px-4 py-2" style={{ background: 'var(--color-surface)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-gh-accent font-mono font-bold" style={{ fontSize: 9 }}>$</span>
            <div className="flex flex-col">
              <span className="font-mono font-bold text-gh-text" style={{ fontSize: 10 }}>{t.multisourceTitle}</span>
              <span className="font-mono" style={{ fontSize: 9, color: 'var(--color-muted)' }}>
                {selectedSourceIds.length > 0 ? t.multisourceSelected.replace('{count}', String(selectedSourceIds.length)) : t.multisourceDefaultActive}
              </span>
            </div>
          </div>
          <button
            onClick={() => setShowSourcePicker(true)}
            className="btn btn-accent"
            style={{ fontSize: 10, padding: '4px 10px', gap: 5 }}
          >
            <Layers size={11} />
            {t.editBtn}
          </button>
        </div>
      </div>

      {showSourcePicker && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 backdrop-blur-md p-4 md:p-6"
          onClick={() => setShowSourcePicker(false)}
        >
          <div
            className="w-full max-w-4xl max-h-[90vh] flex flex-col bg-gh-canvas border border-gh-border rounded-xl shadow-2xl overflow-hidden animate-slide-up"
            onClick={(e) => e.stopPropagation()}
            style={{ animationDuration: '0.25s' }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gh-border bg-gh-surface">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-gh-accent-subtle border border-gh-accent/30">
                  <Layers className="w-5 h-5 text-gh-accent" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-gh-text">{t.relationEditorTitle}</h3>
                  <p className="text-[11px] text-gh-muted mt-0.5">{t.relationEditorSubtitle}</p>
                </div>
              </div>
              <button
                onClick={() => setShowSourcePicker(false)}
                className="p-1.5 rounded-lg text-gh-muted hover:bg-gh-surface hover:text-gh-text transition-all cursor-pointer border border-transparent"
              >
                <X className="w-4.5 h-4.5" />
              </button>
            </div>

            {/* Scrollable Body */}
            <div className="flex-1 overflow-y-auto p-6">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                
                {/* Left Column: Source Selection + Relationship Form list */}
                <div className="lg:col-span-7 space-y-6">

                  {/* Section 1: Source Cards selection */}
                  <div className="space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-gh-border pb-2">
                      <span className="text-xs font-semibold text-gh-muted uppercase tracking-wider">{t.sourcesToAnalyze}</span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setSelectedSourceIds(allSources.map(s => s.id))}
                          className="text-[10px] text-gh-accent hover:underline bg-transparent border-none cursor-pointer"
                        >
                          {t.selectAll}
                        </button>
                        <span className="text-gh-border text-xs">|</span>
                        <button
                          onClick={() => setSelectedSourceIds([])}
                          className="text-[10px] text-gh-muted hover:underline bg-transparent border-none cursor-pointer"
                        >
                          {t.clearSelection}
                        </button>
                      </div>
                    </div>

                    <div className="relative mb-3">
                      <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-gh-faint" />
                      <input
                        value={sourceSearch}
                        onChange={(e) => setSourceSearch(e.target.value)}
                        placeholder={t.searchSourcesPlaceholder}
                        className="input pl-9 text-xs"
                        style={{ paddingTop: 8, paddingBottom: 8 }}
                      />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[160px] overflow-y-auto pr-1">
                      {visibleSources.map((src) => {
                        const checked = selectedSourceIds.includes(src.id);
                        return (
                          <div
                            key={src.id}
                            onClick={() => {
                              const next = checked
                                ? selectedSourceIds.filter(id => id !== src.id)
                                : [...selectedSourceIds, src.id];
                              setSelectedSourceIds(next);
                            }}
                            className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-all ${checked
                                ? 'bg-gh-accent-subtle border-gh-accent shadow-[0_0_8px_var(--color-accent-subtle)]'
                                : 'bg-gh-canvas border-gh-border hover:bg-gh-surface hover:border-gh-muted'
                              }`}
                          >
                            <div className={`p-1.5 rounded ${checked ? 'bg-gh-accent-subtle text-gh-accent' : 'bg-gh-surface text-gh-muted'}`}>
                              {src.type === 'file' ? <FileText size={14} /> : <Database size={14} />}
                            </div>

                            <div className="flex-1 min-w-0">
                              <div className="text-xs font-semibold text-gh-text truncate">{src.label}</div>
                              <div className="text-[10px] text-gh-muted mt-0.5">
                                {src.type === 'file' ? t.csvExcelFileLabel : `${src.type.toUpperCase()} ${t.databaseLabelSuffix}`}
                              </div>
                            </div>

                            <div className={`w-4 h-4 rounded-full border flex items-center justify-center transition-all ${checked ? 'border-gh-accent bg-gh-accent' : 'border-gh-border'
                              }`}>
                              {checked && <Check size={10} className="text-white stroke-[3px]" />}
                            </div>
                          </div>
                        );
                      })}
                      {visibleSources.length === 0 && (
                        <div className="col-span-2 text-center py-6 text-xs text-gh-muted">
                          {t.noSourceFoundMatching}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Section 2: Relationship Builder */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between border-b border-gh-border pb-2">
                      <span className="text-xs font-semibold text-gh-muted uppercase tracking-wider">{t.relationsLabel}</span>
                      <button
                        onClick={() => {
                          if (effectiveSourceIds.length < 1) return;
                          const defaultSrcId = effectiveSourceIds[0];

                          const defaultSrc = allSources.find(s => s.id === defaultSrcId);
                          let defaultCol = '';
                          if (defaultSrc) {
                            if (defaultSrc.type === 'file') {
                              const cols = defaultSrc.schema ? Object.keys(defaultSrc.schema) : [];
                              defaultCol = cols.length > 0 ? cols[0] : '';
                            } else {
                              const tables = defaultSrc.schema ? Object.keys(defaultSrc.schema) : [];
                              if (tables.length > 0) {
                                const firstTable = tables[0];
                                const cols = defaultSrc.schema[firstTable] as string[] || [];
                                const firstCol = cols.length > 0 ? cols[0] : '';
                                defaultCol = `${firstTable}.${firstCol}`;
                              }
                            }
                          }

                          setJoinRelations([
                            ...joinRelations,
                            {
                              leftSourceId: defaultSrcId,
                              leftColumn: defaultCol,
                              rightSourceId: defaultSrcId,
                              rightColumn: defaultCol,
                              joinType: 'auto'
                            }
                          ]);
                        }}
                        disabled={effectiveSourceIds.length === 0}
                        className="btn btn-primary text-[10px] py-1 px-3 flex items-center gap-1"
                      >
                        <Plus size={11} />
                        {t.addRelationBtn}
                      </button>
                    </div>

                    <div className="space-y-3">
                      {joinRelations.map((rel, idx) => {
                        const leftSource = allSources.find(s => s.id === rel.leftSourceId);
                        const rightSource = allSources.find(s => s.id === rel.rightSourceId);

                        const isLeftDb = leftSource?.type === 'database';
                        const isRightDb = rightSource?.type === 'database';

                        const leftTables = isLeftDb && leftSource?.schema ? Object.keys(leftSource.schema) : [];
                        const leftSelectedTable = isLeftDb && rel.leftColumn && rel.leftColumn.includes('.')
                          ? rel.leftColumn.split('.')[0]
                          : (leftTables.length > 0 ? leftTables[0] : '');

                        const leftSelectedColName = isLeftDb && rel.leftColumn && rel.leftColumn.includes('.')
                          ? rel.leftColumn.split('.')[1]
                          : (isLeftDb ? '' : rel.leftColumn);

                        const leftTableColumns = isLeftDb && leftSource?.schema && leftSelectedTable
                          ? (leftSource.schema[leftSelectedTable] as string[] || [])
                          : [];

                        const leftFileColumns = !isLeftDb && leftSource?.schema ? Object.keys(leftSource.schema) : [];

                        const rightTables = isRightDb && rightSource?.schema ? Object.keys(rightSource.schema) : [];
                        const rightSelectedTable = isRightDb && rel.rightColumn && rel.rightColumn.includes('.')
                          ? rel.rightColumn.split('.')[0]
                          : (rightTables.length > 0 ? rightTables[0] : '');

                        const rightSelectedColName = isRightDb && rel.rightColumn && rel.rightColumn.includes('.')
                          ? rel.rightColumn.split('.')[1]
                          : (isRightDb ? '' : rel.rightColumn);

                        const rightTableColumns = isRightDb && rightSource?.schema && rightSelectedTable
                          ? (rightSource.schema[rightSelectedTable] as string[] || [])
                          : [];

                        const rightFileColumns = !isRightDb && rightSource?.schema ? Object.keys(rightSource.schema) : [];

                        return (
                          <div
                            key={idx}
                            className="bg-gh-surface border border-gh-border rounded-xl p-4 shadow-inner relative group/row hover:border-gh-muted transition-all"
                          >
                            <div className="flex items-center justify-between mb-3 border-b border-gh-border/40 pb-1.5">
                              <span className="text-[10px] font-semibold text-gh-accent uppercase tracking-wider flex items-center gap-1.5">
                                <GitCommit size={12} className="rotate-90" />
                                {t.relationIndexLabel.replace('{number}', String(idx + 1))}
                              </span>
                              <button
                                onClick={() => {
                                  const next = [...joinRelations];
                                  next.splice(idx, 1);
                                  setJoinRelations(next);
                                }}
                                className="p-1.5 rounded-lg text-gh-danger hover:bg-gh-danger/10 transition-colors cursor-pointer border border-transparent"
                                title={t.removeRelationTooltip}
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-9 gap-3 items-center">
                              <div className="md:col-span-3 space-y-2">
                                <label className="block text-[10px] font-semibold text-gh-muted">{t.leftSourceLabel}</label>
                                <select
                                  className="input text-xs py-1.5 bg-gh-bg border-gh-border rounded-md text-gh-text"
                                  value={rel.leftSourceId}
                                  onChange={(e) => {
                                    const newSrcId = e.target.value;
                                    const newSrc = allSources.find(s => s.id === newSrcId);
                                    let newCol = '';
                                    if (newSrc) {
                                      if (newSrc.type === 'file') {
                                        const cols = newSrc.schema ? Object.keys(newSrc.schema) : [];
                                        newCol = cols.length > 0 ? cols[0] : '';
                                      } else {
                                        const tables = newSrc.schema ? Object.keys(newSrc.schema) : [];
                                        if (tables.length > 0) {
                                          const firstTable = tables[0];
                                          const cols = newSrc.schema[firstTable] as string[] || [];
                                          const firstCol = cols.length > 0 ? cols[0] : '';
                                          newCol = `${firstTable}.${firstCol}`;
                                        }
                                      }
                                    }
                                    const next = [...joinRelations];
                                    next[idx] = { ...rel, leftSourceId: newSrcId, leftColumn: newCol };
                                    setJoinRelations(next);
                                  }}
                                >
                                  {effectiveSourceIds.map(id => {
                                    const s = allSources.find(a => a.id === id);
                                    return <option key={id} value={id}>{s?.label || id}</option>;
                                  })}
                                </select>

                                {isLeftDb ? (
                                  <div className="grid grid-cols-2 gap-2 mt-1.5">
                                    <select
                                      className="input text-xs py-1.5 bg-gh-bg border-gh-border rounded-md text-gh-text"
                                      value={leftSelectedTable}
                                      onChange={(e) => {
                                        const newTable = e.target.value;
                                        const cols = leftSource && leftSource.schema && newTable
                                          ? (leftSource.schema[newTable] as string[] || [])
                                          : [];
                                        const firstCol = cols.length > 0 ? cols[0] : '';
                                        const next = [...joinRelations];
                                        next[idx] = { ...rel, leftColumn: `${newTable}.${firstCol}` };
                                        setJoinRelations(next);
                                      }}
                                    >
                                      {leftTables.map(tbl => <option key={tbl} value={tbl}>{tbl}</option>)}
                                    </select>
                                    <select
                                      disabled={!leftSelectedTable}
                                      className="input text-xs py-1.5 bg-gh-bg border-gh-border rounded-md text-gh-text"
                                      value={leftSelectedColName}
                                      onChange={(e) => {
                                        const newColName = e.target.value;
                                        const next = [...joinRelations];
                                        next[idx] = { ...rel, leftColumn: `${leftSelectedTable}.${newColName}` };
                                        setJoinRelations(next);
                                      }}
                                    >
                                      <option value="">{t.columnDefault}</option>
                                      {leftTableColumns.map(col => <option key={col} value={col}>{col}</option>)}
                                    </select>
                                  </div>
                                ) : (
                                  <select
                                    className="input text-xs py-1.5 bg-gh-bg border-gh-border rounded-md text-gh-text mt-1.5"
                                    value={rel.leftColumn}
                                    onChange={(e) => {
                                      const next = [...joinRelations];
                                      next[idx] = { ...rel, leftColumn: e.target.value };
                                      setJoinRelations(next);
                                    }}
                                  >
                                    <option value="">{t.columnSelectDefault}</option>
                                    {leftFileColumns.map(col => <option key={col} value={col}>{col}</option>)}
                                  </select>
                                )}
                              </div>

                              <div className="md:col-span-3 text-center flex flex-col items-center justify-center space-y-2">
                                <span className="text-[10px] font-semibold text-gh-muted">{t.relationTypeLabel}</span>
                                <div className="w-full flex items-center justify-center gap-1.5">
                                  <div className="h-[1px] bg-gh-border flex-1"></div>
                                  <select
                                    className="input text-xs text-center py-1.5 max-w-[120px] font-semibold bg-gh-canvas border-gh-border text-gh-accent hover:border-gh-muted"
                                    value={rel.joinType}
                                    onChange={(e) => {
                                      const next = [...joinRelations];
                                      next[idx] = { ...rel, joinType: e.target.value as any };
                                      setJoinRelations(next);
                                    }}
                                  >
                                    <option value="auto">Auto JOIN</option>
                                    <option value="inner">Inner JOIN</option>
                                    <option value="left">Left JOIN</option>
                                    <option value="right">Right JOIN</option>
                                    <option value="full">Full JOIN</option>
                                  </select>
                                  <div className="h-[1px] bg-gh-border flex-1"></div>
                                </div>
                              </div>

                              <div className="md:col-span-3 space-y-2">
                                <label className="block text-[10px] font-semibold text-gh-muted">{t.rightSourceLabel}</label>
                                <select
                                  className="input text-xs py-1.5 bg-gh-bg border-gh-border rounded-md text-gh-text"
                                  value={rel.rightSourceId}
                                  onChange={(e) => {
                                    const newSrcId = e.target.value;
                                    const newSrc = allSources.find(s => s.id === newSrcId);
                                    let newCol = '';
                                    if (newSrc) {
                                      if (newSrc.type === 'file') {
                                        const cols = newSrc.schema ? Object.keys(newSrc.schema) : [];
                                        newCol = cols.length > 0 ? cols[0] : '';
                                      } else {
                                        const tables = newSrc.schema ? Object.keys(newSrc.schema) : [];
                                        if (tables.length > 0) {
                                          const firstTable = tables[0];
                                          const cols = newSrc.schema[firstTable] as string[] || [];
                                          const firstCol = cols.length > 0 ? cols[0] : '';
                                          newCol = `${firstTable}.${firstCol}`;
                                        }
                                      }
                                    }
                                    const next = [...joinRelations];
                                    next[idx] = { ...rel, rightSourceId: newSrcId, rightColumn: newCol };
                                    setJoinRelations(next);
                                  }}
                                >
                                  {effectiveSourceIds.map(id => {
                                    const s = allSources.find(a => a.id === id);
                                    return <option key={id} value={id}>{s?.label || id}</option>;
                                  })}
                                </select>

                                {isRightDb ? (
                                  <div className="grid grid-cols-2 gap-2 mt-1.5">
                                    <select
                                      className="input text-xs py-1.5 bg-gh-bg border-gh-border rounded-md text-gh-text"
                                      value={rightSelectedTable}
                                      onChange={(e) => {
                                        const newTable = e.target.value;
                                        const cols = rightSource && rightSource.schema && newTable
                                          ? (rightSource.schema[newTable] as string[] || [])
                                          : [];
                                        const firstCol = cols.length > 0 ? cols[0] : '';
                                        const next = [...joinRelations];
                                        next[idx] = { ...rel, rightColumn: `${newTable}.${firstCol}` };
                                        setJoinRelations(next);
                                      }}
                                    >
                                      {rightTables.map(tbl => <option key={tbl} value={tbl}>{tbl}</option>)}
                                    </select>
                                    <select
                                      disabled={!rightSelectedTable}
                                      className="input text-xs py-1.5 bg-gh-bg border-gh-border rounded-md text-gh-text"
                                      value={rightSelectedColName}
                                      onChange={(e) => {
                                        const newColName = e.target.value;
                                        const next = [...joinRelations];
                                        next[idx] = { ...rel, rightColumn: `${rightSelectedTable}.${newColName}` };
                                        setJoinRelations(next);
                                      }}
                                    >
                                      <option value="">{t.columnDefault}</option>
                                      {rightTableColumns.map(col => <option key={col} value={col}>{col}</option>)}
                                    </select>
                                  </div>
                                ) : (
                                  <select
                                    className="input text-xs py-1.5 bg-gh-bg border-gh-border rounded-md text-gh-text mt-1.5"
                                    value={rel.rightColumn}
                                    onChange={(e) => {
                                      const next = [...joinRelations];
                                      next[idx] = { ...rel, rightColumn: e.target.value };
                                      setJoinRelations(next);
                                    }}
                                  >
                                    <option value="">{t.columnSelectDefault}</option>
                                    {rightFileColumns.map(col => <option key={col} value={col}>{col}</option>)}
                                  </select>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}

                      {joinRelations.length === 0 && (
                        <div className="text-center py-8 rounded-xl border border-dashed border-gh-border bg-gh-surface/35">
                          <GitCommit size={24} className="mx-auto text-gh-faint mb-2" />
                          <p className="text-xs text-gh-muted font-medium">{t.noRelationDefined}</p>
                          <p className="text-[10px] text-gh-faint mt-1">{t.noRelationDesc}</p>
                        </div>
                      )}
                    </div>
                  </div>

                </div>

                {/* Right Column: Visual Schema Map (Suggestion 6) */}
                <div className="lg:col-span-5 space-y-3 flex flex-col min-h-[480px]">
                  <div className="flex items-center justify-between border-b border-gh-border pb-2 shrink-0">
                    <span className="text-xs font-semibold text-gh-muted uppercase tracking-wider flex items-center gap-1.5">
                      <Layers className="w-4 h-4 text-gh-accent" />
                      3. {t.schemaDesignerTitle}
                    </span>
                    {selectedCol && (
                      <span className="text-[9px] text-gh-accent font-bold font-mono animate-pulse bg-gh-accent-subtle px-2 py-0.5 rounded border border-gh-accent/20 flex items-center gap-1">
                        <Link size={10} className="text-gh-accent shrink-0" /> {t.columnSelectedBadge}: {selectedCol.columnName}
                      </span>
                    )}
                  </div>
                  
                  <div 
                    className="border border-gh-border rounded-xl p-4 flex flex-col justify-between flex-1 relative overflow-hidden" 
                    style={{ background: 'var(--color-surface)', minHeight: 460 }}
                  >
                    {/* SVG Connector overlay Layer */}
                    <div className="absolute inset-0 pointer-events-none z-10">
                      <svg className="w-full h-full absolute inset-0">
                        <defs>
                          <filter id="glow-effect" x="-20%" y="-20%" width="140%" height="140%">
                            <feGaussianBlur stdDeviation="3.5" result="blur" />
                            <feComposite in="SourceGraphic" in2="blur" operator="over" />
                          </filter>
                        </defs>
                        <style>{`
                          @keyframes flow-dash {
                            to {
                              stroke-dashoffset: -12;
                            }
                          }
                        `}</style>
                        {(() => {
                          const svgLines: React.ReactNode[] = [];
                          
                          joinRelations.forEach((rel, rIdx) => {
                            const leftId = `col-node-${rel.leftSourceId}-${rel.leftColumn.replace('.', '-')}`;
                            const rightId = `col-node-${rel.rightSourceId}-${rel.rightColumn.replace('.', '-')}`;
                            
                            const leftEl = document.getElementById(leftId);
                            const rightEl = document.getElementById(rightId);
                            const containerEl = leftEl?.closest('.relative');
                            
                            if (leftEl && rightEl && containerEl) {
                              const cRect = containerEl.getBoundingClientRect();
                              const lRect = leftEl.getBoundingClientRect();
                              const rRect = rightEl.getBoundingClientRect();
                              
                              const x1 = lRect.right - cRect.left;
                              const y1 = (lRect.top + lRect.bottom) / 2 - cRect.top;
                              const x2 = rRect.left - cRect.left;
                              const y2 = (rRect.top + rRect.bottom) / 2 - cRect.top;
                              
                              const cx = (x1 + x2) / 2;
                              const cy = (y1 + y2) / 2;
                              
                              const joinColors: Record<string, string> = {
                                auto: '#c96442',
                                inner: '#10b981',
                                left: '#b45309',
                                right: '#f59e0b',
                                full: '#8b5cf6'
                              };
                              
                              const activeColor = joinColors[rel.joinType] || joinColors.auto;
                              
                              svgLines.push(
                                <g key={`line-group-${rIdx}`} className="pointer-events-auto group">
                                  {/* Curved Connection Path */}
                                  <path
                                    d={`M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`}
                                    fill="none"
                                    stroke={activeColor}
                                    strokeWidth="3.5"
                                    className="opacity-70 group-hover:stroke-gh-accent group-hover:stroke-[4.5px] transition-all"
                                    style={{ filter: 'url(#glow-effect)' }}
                                  />
                                  {/* Animated flow path */}
                                  <path
                                    d={`M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`}
                                    fill="none"
                                    stroke="#ffffff"
                                    strokeWidth="1.2"
                                    strokeDasharray="4,8"
                                    className="opacity-80 pointer-events-none"
                                    style={{ animation: 'flow-dash 1.5s linear infinite' }}
                                  />
                                  {/* Hover Helper wide line for easy click */}
                                  <path
                                    d={`M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`}
                                    fill="none"
                                    stroke="transparent"
                                    strokeWidth="12"
                                    className="cursor-pointer"
                                  />
                                  {/* Visual circle nodes at terminals */}
                                  <circle cx={x1} cy={y1} r="4" fill={activeColor} />
                                  <circle cx={x2} cy={y2} r="4" fill={activeColor} />
                                  
                                  {/* Center Join Type selector pill inside SVG foreignObject */}
                                  <foreignObject
                                    x={cx - 36}
                                    y={cy - 12}
                                    width="72"
                                    height="24"
                                    className="overflow-visible"
                                  >
                                    <div className="flex items-center gap-1 bg-gh-canvas border border-gh-border rounded-md px-1.5 py-0.5 shadow-md justify-between h-full select-none" style={{ background: 'var(--color-surface)', borderColor: activeColor }}>
                                      <select
                                        value={rel.joinType}
                                        onChange={(e) => {
                                          const next = [...joinRelations];
                                          next[rIdx] = { ...rel, joinType: e.target.value as any };
                                          setJoinRelations(next);
                                        }}
                                        className="bg-transparent font-mono font-bold text-[8px] focus:outline-none border-none text-gh-text select-none cursor-pointer uppercase py-0 px-0.5"
                                        style={{ fontSize: 7.5 }}
                                      >
                                        <option value="auto">Auto</option>
                                        <option value="inner">Inner</option>
                                        <option value="left">Left</option>
                                        <option value="right">Right</option>
                                        <option value="full">Full</option>
                                      </select>
                                      <button
                                        onClick={() => {
                                          const next = [...joinRelations];
                                          next.splice(rIdx, 1);
                                          setJoinRelations(next);
                                        }}
                                        className="w-3.5 h-3.5 rounded bg-gh-danger-subtle hover:bg-gh-danger text-gh-danger hover:text-white flex items-center justify-center text-[9px] border-none outline-none cursor-pointer transition-all"
                                      >
                                        ×
                                      </button>
                                    </div>
                                  </foreignObject>
                                </g>
                              );
                            }
                          });
                          
                          return svgLines;
                        })()}
                      </svg>
                    </div>

                    {/* Canvas Inner Content */}
                    <div onScroll={() => setRedrawTrigger(t => t + 1)} className="space-y-4 flex-1 overflow-y-auto max-h-[380px] z-0 pr-1 relative">
                      {effectiveSourceIds.length === 0 ? (
                        <div className="h-[300px] flex flex-col items-center justify-center text-center p-4">
                          <div className="w-12 h-12 rounded-full border border-dashed border-gh-border flex items-center justify-center mb-3 animate-pulse">
                            <Layers className="w-5 h-5 text-gh-faint" />
                          </div>
                          <p className="text-xs text-gh-muted font-medium">{t.visualSchemaEmptyTitle}</p>
                          <p className="text-[10px] text-gh-faint mt-1 max-w-[200px] leading-relaxed">{t.visualSchemaEmptyDesc}</p>
                        </div>
                      ) : (
                        <div className="grid grid-cols-2 gap-4 select-none relative">
                          {effectiveSourceIds.map((sid) => {
                            const src = allSources.find(a => a.id === sid);
                            if (!src) return null;
                            const isDb = src.type === 'database';
                            const srcLabel = src.label.replace('db_', '').replace('file_', '');
                            
                            // Render individual table boxes dynamically
                            const tablesList = isDb && src.schema ? Object.keys(src.schema) : [srcLabel];
                            
                            return (
                              <React.Fragment key={`canvas-src-${sid}`}>
                                {tablesList.map((tbl) => {
                                  const tableKey = isDb ? tbl : srcLabel;
                                  const cols = isDb && src.schema && src.schema[tbl]
                                    ? (src.schema[tbl] as string[] || [])
                                    : (src.schema ? Object.keys(src.schema) : []);
                                    
                                  return (
                                    <div 
                                      key={`canvas-tbl-${sid}-${tbl}`}
                                      className="border border-gh-border/50 rounded-xl bg-gh-surface shadow-md overflow-hidden select-none hover:border-gh-accent hover:shadow-lg transition-all duration-300 transform hover:-translate-y-[1px]"
                                      style={{ background: 'var(--color-bg)' }}
                                    >
                                      {/* Table Header */}
                                      <div className="px-3 py-2 border-b border-gh-border/50 flex items-center gap-2 shrink-0 select-none bg-zinc-900/10 dark:bg-white/[0.02]">
                                        {isDb ? <Database size={11} className="text-gh-accent-fg" /> : <FileText size={11} className="text-emerald-400" />}
                                        <span className="font-mono font-bold text-[9.5px] text-gh-text truncate dark:text-zinc-200 text-zinc-800" title={tableKey}>{tableKey}</span>
                                      </div>
                                      
                                      {/* Column list nodes */}
                                      <div className="p-2 space-y-1.5 select-none">
                                        {cols.map((col) => {
                                          const colPath = isDb ? `${tbl}.${col}` : col;
                                          const nodeDomId = `col-node-${sid}-${colPath.replace('.', '-')}`;
                                          
                                          // Check if active or part of selection
                                          const isSelected = selectedCol?.sourceId === sid && selectedCol?.columnName === colPath;
                                          const isJoined = joinRelations.some(r => 
                                            (r.leftSourceId === sid && r.leftColumn === colPath) ||
                                            (r.rightSourceId === sid && r.rightColumn === colPath)
                                          );
                                          
                                          const colClass = "flex items-center justify-between px-2.5 py-1.5 rounded-lg text-[10px] font-mono select-none cursor-pointer transition-all border " + (
                                            isSelected
                                              ? 'bg-gh-accent-subtle border-gh-accent text-gh-accent-fg font-bold'
                                              : isJoined
                                                ? 'bg-gh-canvas border-gh-border text-gh-text hover:border-zinc-500'
                                                : 'bg-transparent border-transparent text-gh-muted hover:bg-gh-surface hover:text-gh-text'
                                          );
                                          
                                          const indicatorStyle: React.CSSProperties = isSelected
                                            ? {
                                                background: 'var(--color-accent)',
                                                borderColor: 'var(--color-accent)',
                                                transform: 'scale(1.1)',
                                                boxShadow: '0 0 6px rgba(201,100,66,0.45)'
                                              }
                                            : isJoined
                                              ? {
                                                  background: 'var(--color-accent-subtle2)',
                                                  borderColor: 'var(--color-accent)'
                                                }
                                              : {
                                                  background: 'transparent',
                                                  borderColor: 'var(--color-border)'
                                                };

                                          return (
                                            <div
                                              key={`node-col-${sid}-${tbl}-${col}`}
                                              id={nodeDomId}
                                              onClick={() => {
                                                if (!selectedCol) {
                                                  setSelectedCol({ sourceId: sid, tableName: isDb ? tbl : undefined, columnName: colPath });
                                                } else {
                                                  if (selectedCol.sourceId === sid && selectedCol.columnName === colPath) {
                                                    setSelectedCol(null); // click again to cancel
                                                  } else {
                                                    // Create new relation between the selected and the clicked column
                                                    const newRel: JoinRelation = {
                                                      leftSourceId: selectedCol.sourceId,
                                                      leftColumn: selectedCol.columnName,
                                                      rightSourceId: sid,
                                                      rightColumn: colPath,
                                                      joinType: 'auto'
                                                    };
                                                    setJoinRelations([...joinRelations, newRel]);
                                                    setSelectedCol(null);
                                                  }
                                                }
                                              }}
                                              className={colClass}
                                            >
                                              <span className="truncate select-none pointer-events-none" title={col}>{col}</span>
                                              <div className="w-2 h-2 rounded-full border transition-all" style={indicatorStyle} />
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  );
                                })}
                              </React.Fragment>
                            );
                          })}
                        </div>
                      )}
                    </div>
                    
                    {/* Live indicator Footer */}
                    <div className="border-t border-gh-border/50 pt-2.5 mt-2.5 flex items-center justify-between text-[9px] text-gh-faint font-mono shrink-0 select-none">
                      <span className="flex items-center gap-1.5"><Zap size={10} className="text-gh-accent shrink-0" /> {t.clickToLinkPrompt}</span>
                      <span>{joinRelations.length} {t.totalRelationsBadge}</span>
                    </div>
                  </div>
                </div>

              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 bg-gh-canvas border-t border-gh-border flex justify-end">
              {sourcePickerMode === 'create' ? (
                <button
                  onClick={async () => {
                    if (selectedSourceIds.length > 0) {
                      await setActiveSourceId(selectedSourceIds[0]);
                    }
                    await createSession();
                    setShowSourcePicker(false);
                  }}
                  className="btn btn-primary px-6 py-2 shadow font-semibold"
                >
                  {t.startChatBtn}
                </button>
              ) : (
                <button
                  onClick={() => setShowSourcePicker(false)}
                  className="btn btn-accent px-6 py-2 shadow font-semibold"
                >
                  {language === 'tr' ? 'Kaydet ve Kapat' : 'Save and Close'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {showSqlPreview && previewData && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/55 p-4">
          <div className="w-full max-w-2xl bg-gh-canvas border border-gh-border rounded-lg p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-gh-text">Sorgu Önizlemesi ve Düzeltme Önerileri</h3>
                <p className="text-[11px] text-gh-muted mt-1">Sorgunuzda seçili olmayan tablolar tespit edildi. Aşağıdan düzeltmeyi onaylayabilirsiniz.</p>
              </div>
              <button onClick={cancelPreview} className="p-1.5 rounded hover:bg-gh-surface"><X className="w-4 h-4 text-gh-muted" /></button>
            </div>

            <div className="panel-inset p-3 mb-4">
              <div className="text-[12px] text-gh-muted mb-2">Orijinal Sorgu</div>
              <pre className="bg-gh-bg p-3 rounded text-[13px] overflow-auto">{previewData.sql}</pre>
            </div>

            <div className="mb-4">
              <div className="text-[12px] text-gh-muted mb-2">Tespit Edilen Bilinmeyen Tablolar</div>
              <ul className="list-disc list-inside text-gh-text">
                {previewData.unknowns.map((u: string) => (
                  <li key={`u-${u}`} className="mb-2">
                    <div className="font-semibold">{u}</div>
                    <div className="text-[12px] text-gh-muted mt-1">Önerilen eşleşmeler: {previewData.candidates[u].length ? previewData.candidates[u].join(', ') : '(Öneri yok)'}</div>
                    {previewData.candidates[u].length > 0 && (
                      <div className="mt-2 flex gap-2">
                        {previewData.candidates[u].map((c: string) => (
                          <button key={`c-${c}`} className="btn btn-sm" onClick={() => {
                            // apply replacement for this unknown
                            const re = new RegExp(`\\b${u}\\b`, 'gi');
                            const replaced = previewData.sql.replace(re, c);
                            setPreviewData({ ...previewData, sql: replaced });
                          }}>{c}</button>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex items-center justify-end gap-2">
              <button className="btn" onClick={cancelPreview}>Vazgeç</button>
              <button className="btn btn-primary" onClick={() => confirmPreviewSend(previewData.sql)}>Düzelt ve Gönder</button>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto space-y-0" style={{ background: 'var(--color-bg)', padding: '16px 16px' }}>

        {/* Empty state — centered hero with 3-step flow guide */}
        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full animate-fade-in px-4 text-center">
            {/* Logo mark with subtle coral glow */}
            <div className="relative mb-6" style={{ width: 72, height: 64 }}>
              <div
                className="absolute inset-0"
                style={{
                  background: 'radial-gradient(circle, rgba(201,100,66,0.28) 0%, rgba(201,100,66,0.07) 55%, transparent 75%)',
                  filter: 'blur(8px)'
                }}
              />
              <div
                className="relative w-12 h-12 mx-auto flex items-center justify-center"
                style={{
                  background: 'linear-gradient(135deg, var(--color-surface2) 0%, var(--color-surface) 100%)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 12,
                  boxShadow: '0 2px 6px rgba(28,25,23,0.06)'
                }}
              >
                <Sparkles size={18} style={{ color: 'var(--color-accent-fg)' }} />
              </div>
            </div>

            <div className="text-lg font-semibold text-gh-text tracking-tight">
              {language === 'tr' ? 'Ne analiz etmek istersiniz?' : 'What would you like to analyze?'}
            </div>
            <div className="text-xs text-gh-muted mt-2 max-w-[380px] leading-relaxed">
              {language === 'tr'
                ? 'Analiz etmek istediğiniz veri kaynaklarını seçin ve aşağıya sorunuzu yazın.'
                : 'Select the data sources you want to analyze and type your question below.'}
            </div>

            {/* 3-step flow guide */}
            <div className="flex flex-wrap items-center justify-center gap-1.5 mt-6">
              <button
                type="button"
                onClick={() => setShowSourcePicker(true)}
                className="flex items-center gap-2 px-3 py-1.5 cursor-pointer transition-all hover:brightness-[0.98]"
                style={{
                  background: 'var(--color-canvas)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 999,
                  boxShadow: '0 2px 6px rgba(28,25,23,0.06)'
                }}
                title={language === 'tr' ? 'Kaynak seçiciyi aç' : 'Open source picker'}
              >
                <span className="text-[11px] font-bold font-mono" style={{ color: 'var(--color-accent-fg)' }}>1</span>
                <span className="text-[11px] font-medium" style={{ color: 'var(--color-text-2)' }}>
                  {language === 'tr' ? 'Kaynak seç' : 'Pick a source'}
                </span>
                <Plus size={11} style={{ color: 'var(--color-accent-fg)' }} />
              </button>
              <span className="text-[11px] font-mono" style={{ color: 'var(--color-faint)' }}>→</span>
              <button
                type="button"
                onClick={() => inputRef.current?.focus()}
                className="flex items-center gap-2 px-3 py-1.5 cursor-pointer transition-all hover:brightness-[0.98]"
                style={{
                  background: 'var(--color-canvas)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 999,
                  boxShadow: '0 2px 6px rgba(28,25,23,0.06)'
                }}
              >
                <span className="text-[11px] font-bold font-mono" style={{ color: 'var(--color-accent-fg)' }}>2</span>
                <span className="text-[11px] font-medium" style={{ color: 'var(--color-text-2)' }}>
                  {language === 'tr' ? 'Sorunu yaz' : 'Write your question'}
                </span>
              </button>
              <span className="text-[11px] font-mono" style={{ color: 'var(--color-faint)' }}>→</span>
              <div
                className="flex items-center gap-2 px-3 py-1.5"
                style={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 999
                }}
              >
                <span className="text-[11px] font-bold font-mono" style={{ color: 'var(--color-accent-fg)' }}>3</span>
                <span className="text-[11px] font-medium" style={{ color: 'var(--color-muted)' }}>
                  {language === 'tr' ? 'Sonucu keşfet' : 'Explore the result'}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-2 mt-7 max-w-[500px]">
              {([
                { cmd: '/graph', prompt: '/graph en çok satan ilk 10 ürünü göster', desc: language === 'tr' ? 'Grafik çizdir' : 'Draw a chart' },
                { cmd: '/explain', prompt: '/explain', desc: language === 'tr' ? 'Veri kümesini açıkla' : 'Explain the dataset' },
                { cmd: '/table', prompt: '/table özet istatistikleri listele', desc: language === 'tr' ? 'Tablo olarak listele' : 'List as a table' },
                { cmd: '/ask', prompt: '/ask bu veri kümesinde neler var?', desc: language === 'tr' ? 'Soru sor' : 'Ask a question' },
              ] as const).map(ex => (
                <button
                  key={ex.cmd}
                  onClick={() => sendMessage(ex.prompt)}
                  className="group flex items-center gap-2 px-3 py-1.5 text-left cursor-pointer transition-all hover:bg-gh-surface2 hover:border-gh-muted"
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 8
                  }}
                  title={ex.prompt}
                >
                  <span className="font-mono text-[10px] font-semibold text-gh-accent-fg">{ex.cmd}</span>
                  <span className="text-[10px] text-gh-faint group-hover:text-gh-muted">{ex.desc}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {chatHistory.map((msg, msgIdx) => {
          const isAgent = msg.role === 'agent';
          const hasLog = isAgent && msg.statusHistory.length > 0;
          const hasCode = isAgent && !!msg.code;
          const isLogOpen = logOpen[msg.id] !== false;
          const isCodeOpen = codeOpen[msg.id] === true;

          const nextAgent = msg.role === 'user' ? chatHistory.slice(msgIdx + 1).find(m => m.role === 'agent') : null;
          const isUserActive = nextAgent ? nextAgent.id === resolvedActiveMessageId : false;
          const canActivateUser = !!(nextAgent && (nextAgent.data || nextAgent.visualization || nextAgent.error));

          const isAgentActive = msg.id === resolvedActiveMessageId;
          const canActivateAgent = !!(msg.data || msg.visualization || msg.error);

          // Preceding user question (for save default title / pin title)
          const prevUserText = (() => {
            for (let i = msgIdx - 1; i >= 0; i--) {
              if (chatHistory[i].role === 'user') return chatHistory[i].text || '';
            }
            return '';
          })();
          const canSave = !isThinking && msgIdx === lastSuccessAgentIdx;

          return (
            <div key={msg.id} className="animate-fade-in w-full px-2 py-1">

              {/* ── USER QUERY ROW ── */}
              {!isAgent && (
                <div
                  onClick={() => canActivateUser && activateMessageForIndex(msgIdx)}
                  className={`transition-all duration-200 ${canActivateUser ? 'cursor-pointer hover:brightness-110' : ''}`}
                  style={{
                    maxWidth: '82%',
                    marginLeft: 'auto',
                    marginTop: 8,
                    marginBottom: 8,
                    padding: '10px 14px',
                    background: 'var(--color-accent-subtle)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '12px',
                    boxShadow: isUserActive ? '0 0 0 1px var(--color-accent-subtle2)' : '0 2px 6px rgba(28,25,23,0.06)'
                  }}
                  title={canActivateUser ? (language === 'tr' ? "Panele yansıtmak için tıklayın" : "Click to display in panel") : undefined}
                >
                  <div className="flex gap-3 items-start">
                    {/* User Avatar */}
                    <div
                      className="flex-shrink-0 w-7 h-7 rounded-lg border flex items-center justify-center"
                      style={{ background: 'var(--color-surface2)', borderColor: 'var(--color-border)' }}
                    >
                      <User size={12} style={{ color: 'var(--color-accent-fg)' }} />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] font-mono font-bold text-gh-accent-fg uppercase tracking-widest">SORGU</span>
                          <span className="text-[9px] font-mono text-gh-faint/60">{new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        {isUserActive && (
                          <span className="text-[8px] font-mono font-bold text-gh-accent-fg uppercase tracking-widest px-2 py-0.5 rounded-full" style={{ background: 'var(--color-accent-subtle2)' }}>
                            {language === 'tr' ? 'GÖSTERİLİYOR' : 'DISPLAYED'}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gh-text select-text whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* ── AGENT RESPONSE SECTION ── */}
              {isAgent && (
                <div
                  onClick={() => canActivateAgent && activateMessageForIndex(msgIdx)}
                  className={`msg-agent transition-all duration-200 ${canActivateAgent ? 'cursor-pointer' : ''}`}
                  style={{
                    borderRadius: '12px',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-canvas)',
                    padding: '14px 16px',
                    boxShadow: isAgentActive ? '0 0 0 1px var(--color-accent-subtle2)' : '0 2px 6px rgba(28,25,23,0.06)'
                  }}
                  title={canActivateAgent ? (language === 'tr' ? "Panele yansıtmak için tıklayın" : "Click to display in panel") : undefined}
                >
                  <div className="flex gap-3 items-start">
                    {/* Agent Avatar */}
                    <div
                      className="flex-shrink-0 w-7 h-7 rounded-lg border flex items-center justify-center mt-0.5"
                      style={{
                        background: 'var(--color-accent-subtle)',
                        borderColor: 'var(--color-border)'
                      }}
                    >
                      <Sparkles size={13} style={{ color: 'var(--color-accent-fg)' }} />
                    </div>

                    <div className="flex-1 min-w-0">
                      {/* Section header */}
                      <div className="flex items-center justify-between mb-3 pb-2" style={{ borderBottom: '1px solid var(--color-border2)' }}>
                        <div className="flex items-center gap-3">
                          <span className="text-[9px] font-mono font-bold text-gh-faint uppercase tracking-widest flex items-center gap-1.5"><Sparkles size={11} className="text-gh-accent-fg" /> {language === 'tr' ? 'ANALİZ RAPORU & ÇIKTILAR' : 'ANALYSIS REPORT & OUTPUTS'}</span>
                          {isThinking && msgIdx === chatHistory.length - 1 && (
                            <span className="dot-processing" />
                          )}
                        </div>
                        {isAgentActive && (
                          <span className="text-[8px] font-mono font-bold text-gh-accent-fg uppercase tracking-widest px-2 py-0.5 rounded-full" style={{ background: 'var(--color-accent-subtle2)' }}>
                            {language === 'tr' ? 'GÖSTERİLİYOR' : 'DISPLAYED'}
                          </span>
                        )}
                      </div>

                      {/* KPI Cards (simplified) */}
                      {(() => {
                        const kpis = extractKPIs(msg.text || '');
                        if (kpis.length > 0) {
                          return (
                            <div className="grid grid-cols-3 gap-3 mb-4 animate-slide-up select-none">
                              {kpis.map((kpi, kpiIdx) => (
                                <div
                                  key={kpiIdx}
                                  className="p-3 relative overflow-hidden transition-all duration-200"
                                  style={{
                                    background: 'var(--color-surface)',
                                    border: '1px solid var(--color-border)',
                                    borderLeft: '2px solid var(--color-accent)',
                                    borderRadius: '8px'
                                  }}
                                >
                                  <span className="text-[8px] uppercase font-semibold tracking-wider block text-gh-faint font-mono mb-1">{kpi.label}</span>
                                  <span className="text-sm font-bold tracking-tight block font-mono" style={{ color: 'var(--color-accent-fg)' }}>
                                    {kpi.value}
                                  </span>
                                </div>
                              ))}
                            </div>
                          );
                        }
                        return null;
                      })()}

                      {/* Auto-correction badge */}
                      {msg.auto_corrections && msg.auto_corrections.applied && (
                        <div className="mb-4 px-3.5 py-2.5 text-[11px] font-semibold font-mono flex items-center justify-between rounded-lg" style={{ background: 'var(--color-accent-subtle)', border: '1px solid var(--color-border)', borderLeft: '3px solid var(--color-accent)', color: 'var(--color-accent-fg)' }}>
                          <div className="flex items-center gap-2">
                            <Sparkles size={11} className="shrink-0" />
                            <span>Tablo çözümleme düzeltmesi uygulandı: </span>
                            <span className="px-1.5 py-0.5 rounded ml-1" style={{ background: 'var(--color-accent-subtle2)', border: '1px solid var(--color-border)' }}>
                              {Object.entries(msg.auto_corrections.applied).map(([k, v]) => `${k}→${v}`).join(', ')}
                            </span>
                          </div>
                          <button onClick={() => setLogOpen(p => ({ ...p, [`corr-${msg.id}`]: !(p[`corr-${msg.id}`]) }))} className="text-[10px] underline hover:opacity-80">Detay</button>
                          {logOpen[`corr-${msg.id}`] && (
                            <div className="mt-2.5 text-[10.5px] p-2.5 font-mono rounded-md w-full" style={{ color: 'var(--color-muted)', background: 'var(--color-canvas)', border: '1px solid var(--color-border)' }}>
                              <div className="font-bold mb-1" style={{ color: 'var(--color-text-2)' }}>Düzeltme Adımları:</div>
                              <ul className="list-disc list-inside space-y-1 font-mono">
                                {Object.entries(msg.auto_corrections.applied).map(([k, v]) => (
                                  <li key={`ac-${k}`}>{k} → {String(v)}</li>
                                ))}
                              </ul>
                              {msg.auto_corrections.ambiguous && (
                                <div className="mt-2 text-[10.5px]" style={{ color: 'var(--color-warning)' }}>Belirsiz şema referansları: {msg.auto_corrections.ambiguous.join(', ')}</div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Processing log (Timeline Pipeline layout) */}
                      {hasLog && (
                        <div className="log-panel mb-4" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => setLogOpen(p => ({ ...p, [msg.id]: !p[msg.id] }))}
                            className="log-header w-full flex items-center justify-between px-3 py-2 border border-gh-border bg-gh-surface2/45 rounded-lg hover:bg-gh-surface transition-colors cursor-pointer"
                          >
                            <div className="flex items-center gap-2 text-[10px] font-bold font-mono text-zinc-400 uppercase tracking-wider">
                              <span className="text-gh-accent-fg font-bold">$</span>
                              <span>{t.executionLogTitle.replace('{count}', String(msg.statusHistory.length))}</span>
                            </div>
                            {isLogOpen
                              ? <ChevronDown size={12} className="text-zinc-500" />
                              : <ChevronRight size={12} className="text-zinc-500" />}
                          </button>
                          {isLogOpen && (
                            <div className="px-4 py-3.5 space-y-0.5 overflow-y-auto rounded-b-lg border-x border-b border-gh-border" style={{ maxHeight: 160, background: 'rgba(0,0,0,0.15)' }}>
                              {msg.statusHistory.map((s, sIdx) => {
                                const isLast = sIdx === msg.statusHistory.length - 1;
                                const live = isLast && isThinking && msgIdx === chatHistory.length - 1;
                                const isCompleted = !live;
                                return (
                                  <div key={sIdx} className="agent-step-node flex gap-3.5 relative min-h-[30px]">
                                    {/* Timeline line overrides */}
                                    {!isLast && (
                                      <div
                                        className="absolute left-[9px] top-[15px] bottom-[-15px] w-[1px]"
                                        style={{ background: isCompleted ? '#10b981' : 'var(--color-border)' }}
                                      />
                                    )}

                                    {/* Icon node */}
                                    <div className="flex-shrink-0 z-10" style={{ padding: '2px 0' }}>
                                      {live ? (
                                        <Loader2 className="animate-spin text-gh-accent-fg" size={13} />
                                      ) : isCompleted ? (
                                        <CheckCircle2 size={13} style={{ color: '#10b981' }} />
                                      ) : (
                                        <Circle size={13} style={{ color: 'var(--color-faint)' }} />
                                      )}
                                    </div>

                                    {/* Description */}
                                    <div className="flex-1 pb-2">
                                      <span
                                        className={`font-mono text-[10.5px] leading-relaxed block ${live ? 'text-gh-accent-fg font-bold' : 'text-zinc-400'}`}
                                      >
                                        {s}
                                      </span>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Code visualizer block (VS Code Monaco style) */}
                      {hasCode && (
                        <div
                          className="border border-gh-border rounded-lg overflow-hidden mb-4 shadow-sm w-full select-none"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div className="flex items-center justify-between px-3 py-2 border-b shrink-0 select-none" style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => setCodeOpen(p => ({ ...p, [msg.id]: !isCodeOpen }))}
                                className="flex items-center gap-2 bg-transparent border-none cursor-pointer p-0"
                                title={isCodeOpen ? (language === 'tr' ? 'Kodu kapat' : 'Collapse code') : (language === 'tr' ? 'Kodu göster' : 'Expand code')}
                              >
                                {isCodeOpen ? <ChevronDown size={12} className="text-gh-faint" /> : <ChevronRight size={12} className="text-gh-faint" />}
                                <FileCode size={12} className="text-gh-accent-fg" />
                              </button>
                              <span className="text-[10px] font-mono font-semibold text-gh-text-2 uppercase tracking-wider px-1.5 py-0.5 rounded" style={{ background: 'var(--color-surface2)' }}>{msg.codeLanguage ?? 'code'}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              {editingMessageId === msg.id ? (
                                <>
                                  <button
                                    onClick={() => handleRunEditedCode(msg.id, msg.codeLanguage as any)}
                                    disabled={isExecutingCode}
                                    className="p-1 rounded text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                                    style={{ background: 'var(--color-accent)' }}
                                    title={language === 'tr' ? "Kodu Çalıştır" : "Run Code"}
                                  >
                                    {isExecutingCode ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                                  </button>
                                  <button
                                    onClick={cancelEditing}
                                    className="p-1 rounded bg-gh-surface2 hover:bg-gh-border text-gh-faint hover:text-gh-text cursor-pointer"
                                    title={language === 'tr' ? "İptal" : "Cancel"}
                                  >
                                    <X size={11} />
                                  </button>
                                </>
                              ) : (
                                <>
                                  <button
                                    onClick={() => startEditing(msg.id, msg.code ?? '')}
                                    className="p-1 rounded bg-gh-surface2 hover:bg-gh-border text-gh-faint hover:text-gh-text cursor-pointer"
                                    title={language === 'tr' ? "Düzenle" : "Edit"}
                                  >
                                    <Edit3 size={11} />
                                  </button>
                                  <button
                                    onClick={() => copyCode(msg.code ?? '', msg.id)}
                                    className="p-1 rounded bg-gh-surface2 hover:bg-gh-border text-gh-faint hover:text-gh-text cursor-pointer"
                                    title={language === 'tr' ? "Kopyala" : "Copy"}
                                  >
                                    {copied === msg.id ? <Check size={11} className="text-green-400" /> : <Copy size={11} />}
                                  </button>
                                  <button
                                    onClick={() => downloadCode(msg.code ?? '', msg.codeLanguage, msg.id)}
                                    className="p-1 rounded bg-gh-surface2 hover:bg-gh-border text-gh-faint hover:text-gh-text cursor-pointer"
                                    title={language === 'tr' ? "İndir" : "Download"}
                                  >
                                    <Download size={11} />
                                  </button>
                                </>
                              )}
                            </div>
                          </div>

                          {editingMessageId === msg.id ? (
                            <div className="flex flex-col border-t border-gh-border w-full" style={{ background: 'var(--color-code-bg)' }}>
                              <div className="flex font-mono text-[11px] w-full relative overflow-hidden" style={{ minHeight: 160, background: 'var(--color-code-bg)' }}>
                                <div className="select-none text-right pr-2.5 pl-3 py-3 border-r border-gh-border text-gh-faint flex flex-col pointer-events-none" style={{ minWidth: 36, userSelect: 'none', background: 'rgba(255,255,255,0.02)' }}>
                                  {Array.from({ length: Math.max(editedCodeText.split('\n').length, 1) }).map((_, idx) => (
                                    <div key={idx} style={{ height: 19, lineHeight: '19px' }}>{idx + 1}</div>
                                  ))}
                                </div>
                                <textarea
                                  value={editedCodeText}
                                  disabled={isExecutingCode}
                                  onChange={(e) => setEditedCodeText(e.target.value)}
                                  className="font-mono text-[11.5px] p-3 select-text bg-transparent text-[#e4e4e7] focus:outline-none border-none w-full flex-1"
                                  style={{ minHeight: 160, lineHeight: '19px', fontFamily: 'var(--font-mono)', resize: 'vertical', whiteSpace: 'pre', overflowX: 'auto' }}
                                />
                              </div>
                              {executionError && (
                                <div className="px-3.5 py-2.5 bg-red-950/40 border-t border-red-900/30 text-red-400 text-xs font-mono whitespace-pre-wrap select-text max-h-36 overflow-y-auto">
                                  {executionError}
                                </div>
                              )}
                            </div>
                          ) : (
                            isCodeOpen && (
                              <pre className="overflow-x-auto px-4.5 py-4 select-text" style={{ maxHeight: 240, fontSize: 11.5, lineHeight: 1.65, background: 'var(--color-code-bg)', color: 'var(--color-code-fg)' }}>
                                <code dangerouslySetInnerHTML={{ __html: highlightCode(msg.code ?? '', msg.codeLanguage ?? '') }} />
                              </pre>
                            )
                          )}
                        </div>
                      )}

                      {/* Inline result (chart / table) inside the bubble */}
                      {(msg.data || msg.visualization) && !msg.error && (
                        <InlineResult
                          msg={msg}
                          studioMode={studioMode}
                          onOpenStudio={() => setStudioMode(true)}
                          language={language}
                          onPin={() => pinMessageResult(msg, prevUserText)}
                          pinnedNow={pinnedResult?.messageId === msg.id}
                        />
                      )}

                      {/* Response text */}
                      {msg.text && <div className="text-xs font-mono leading-relaxed" style={{ color: 'var(--color-muted)' }}>{renderText(msg.text)}</div>}

                      {/* Thumbs Feedback */}
                      {!isThinking && (
                        <div className="flex items-center gap-2 mt-4 select-none">
                          <button
                            onClick={() => handleFeedback(msg.id, 'positive')}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold font-mono transition-all border cursor-pointer ${
                              messageRatings[msg.id] === 'positive'
                                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                                : 'bg-gh-surface border-gh-border text-gh-muted hover:border-gh-muted hover:text-gh-text'
                            }`}
                            title={t.feedbackTooltipPositive}
                          >
                            <ThumbsUp size={11} />
                            {language === 'tr' ? 'Faydalı' : 'Helpful'}
                          </button>
                          <button
                            onClick={() => handleFeedback(msg.id, 'negative')}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold font-mono transition-all border cursor-pointer ${
                              messageRatings[msg.id] === 'negative'
                                ? 'bg-red-500/15 border-red-500/30 text-red-400'
                                : 'bg-gh-surface border-gh-border text-gh-muted hover:border-gh-muted hover:text-gh-text'
                            }`}
                            title={t.feedbackTooltipNegative}
                          >
                            <ThumbsDown size={11} />
                            {language === 'tr' ? 'Hatalı' : 'Incorrect'}
                          </button>
                          {messageRatings[msg.id] && (
                            <span className="text-[9px] text-emerald-400 font-mono animate-pulse ml-1 inline-flex items-center gap-1">
                              <Sparkles size={9} className="text-emerald-400 shrink-0" /> {t.feedbackSuccess}
                            </span>
                          )}

                          {/* Save analysis (last successful agent message only) */}
                          {canSave && (
                            saveDoneId === msg.id ? (
                              <span
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold font-mono border ml-1"
                                style={{ background: 'rgba(63,157,111,0.12)', borderColor: 'rgba(63,157,111,0.3)', color: '#3f9d6f' }}
                              >
                                <Check size={11} /> {language === 'tr' ? 'Kaydedildi' : 'Saved'}
                              </span>
                            ) : (
                              <button
                                onClick={(e) => { e.stopPropagation(); openSaveForm(msg.id, prevUserText || msg.text || ''); }}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold font-mono transition-all border cursor-pointer bg-gh-surface border-gh-border text-gh-muted hover:border-gh-muted hover:text-gh-text ml-1"
                                title={language === 'tr' ? 'Bu analizi kaydet' : 'Save this analysis'}
                              >
                                💾 {language === 'tr' ? 'Kaydet' : 'Save'}
                              </button>
                            )
                          )}
                        </div>
                      )}

                      {/* Save mini-form */}
                      {canSave && saveFormFor === msg.id && (
                        <div
                          onClick={(e) => e.stopPropagation()}
                          className="mt-2 flex items-center gap-2 px-3 py-2 rounded-lg animate-slide-up"
                          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
                        >
                          <input
                            autoFocus
                            value={saveTitle}
                            onChange={(e) => setSaveTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                submitSave(msg.id);
                              } else if (e.key === 'Escape') {
                                cancelSaveForm();
                              }
                            }}
                            placeholder={language === 'tr' ? 'Analiz başlığı' : 'Analysis title'}
                            maxLength={80}
                            className="input flex-1 text-[11px] font-mono"
                            style={{ padding: '5px 10px', color: 'var(--color-text)' }}
                          />
                          <button
                            onClick={() => submitSave(msg.id)}
                            disabled={savingInProgress || !saveTitle.trim()}
                            className="btn btn-primary"
                            style={{ fontSize: 10, padding: '4px 12px', gap: 4 }}
                          >
                            {savingInProgress ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                            {language === 'tr' ? 'Kaydet' : 'Save'}
                          </button>
                          <button onClick={cancelSaveForm} className="btn btn-sm" style={{ fontSize: 10 }}>
                            {language === 'tr' ? 'İptal' : 'Cancel'}
                          </button>
                        </div>
                      )}

                      {/* Error display */}
                      {msg.error && !msg.text && (
                        <div className="text-xs font-mono text-red-400 border border-red-500/20 px-3.5 py-2.5 mt-3 rounded-lg" style={{ background: 'rgba(239, 68, 68, 0.05)' }}>
                          <span className="flex items-center gap-1.5"><AlertTriangle size={12} className="text-red-400 shrink-0" /> {msg.error}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}




        {/* Processing indicator */}
        {isThinking && (
          <div className="animate-fade-in px-0 py-3 border-l-2 border-gh-accent" style={{ borderRadius: '8px' }}>
            <div className="pl-4">
              <div className="text-[9px] text-gh-accent mb-1.5 font-bold uppercase tracking-widest font-mono">$ {t.engineRunning}</div>
              <div className="thinking-bar" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input Panel ── */}
      <div className="shrink-0 px-4 py-3 bg-gh-bg border-t border-gh-border relative" style={{ borderTop: '1px solid var(--color-border)' }}>

        {/* Command Palette Autocomplete */}
        {showAutocomplete && (
          <div
            ref={cmdPaletteRef}
            className="absolute left-4 right-4 z-50 overflow-hidden animate-slide-up"
            style={{
              bottom: '100%',
              marginBottom: '6px',
              background: 'var(--color-canvas)',
              border: '1px solid var(--color-border)',
              borderRadius: '12px',
              maxHeight: '240px',
              overflowY: 'auto',
              boxShadow: '0 4px 12px rgba(28,25,23,0.10)'
            }}
          >
            <div className="px-3 py-1.5 text-[9px] font-bold text-gh-accent uppercase tracking-widest font-mono" style={{ background: 'var(--color-surface)', borderBottom: '1px solid var(--color-border)' }}>
              › {t.commandPaletteTitle}
            </div>
            {filteredCommands.map((item, idx) => {
              const isSelected = idx === selectedCmdIndex;
              return (
                <div
                  key={item.cmd}
                  onClick={() => selectCommand(item.template)}
                  className="flex items-center justify-between px-4 py-2.5 cursor-pointer transition-all"
                  style={{
                    background: isSelected ? 'var(--color-accent-subtle)' : 'transparent',
                    borderBottom: idx < filteredCommands.length - 1 ? '1px solid var(--color-border2)' : 'none'
                  }}
                >
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs font-mono font-bold tracking-tight" style={{ color: isSelected ? 'var(--color-accent)' : 'var(--color-text)' }}>
                      {item.cmd}
                    </span>
                    <span className="text-[10px] font-mono mt-0.5 truncate" style={{ color: 'var(--color-muted)' }}>{item.desc}</span>
                  </div>
                  <span className="text-[9px] font-mono px-1.5 py-0.5 border border-gh-border text-gh-faint" style={{ borderRadius: '4px' }}>enter</span>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Kayıtlı analizler çip şeridi ── */}
        {saves.length > 0 && (
          <div
            className="flex items-center gap-1.5 mb-2 overflow-x-auto pb-0.5"
            style={{ scrollbarWidth: 'thin' }}
          >
            <span
              className="flex-shrink-0 text-[9px] font-mono font-bold uppercase tracking-widest"
              style={{ color: 'var(--color-faint)' }}
            >
              {language === 'tr' ? 'Kayıtlı analizler' : 'Saved analyses'}
            </span>
            {saves.map(save => (
              <div
                key={save.id}
                onClick={() => runSavedAnalysis(save)}
                className="group flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1 cursor-pointer transition-all hover:opacity-90"
                style={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 999,
                  maxWidth: 220
                }}
                title={save.question || save.title}
              >
                <Sparkles size={9} style={{ color: 'var(--color-accent-fg)', flexShrink: 0 }} />
                <span
                  className="text-[10px] font-medium truncate"
                  style={{ color: 'var(--color-text-2)' }}
                >
                  {save.title}
                </span>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); deleteSave(save.id); }}
                  className="flex-shrink-0 flex items-center justify-center w-3.5 h-3.5 rounded-full cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ background: 'var(--color-accent-subtle)', color: 'var(--color-accent-fg)', border: 'none' }}
                  title={language === 'tr' ? 'Kaydı sil' : 'Delete saved analysis'}
                >
                  <X size={8} />
                </button>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={send} className="flex gap-2 items-center">
          {/* Active source chip (flow guide: source → question → result) */}
          <button
            type="button"
            onClick={(e) => { e.preventDefault(); setShowSourcePicker(true); }}
            className="flex-shrink-0 flex items-center gap-2 px-3 py-2.5 cursor-pointer transition-all hover:opacity-90"
            style={{
              maxWidth: 220,
              background: chipSource ? 'var(--color-surface)' : 'var(--color-accent-subtle)',
              border: '1px solid var(--color-border)',
              borderRadius: '12px'
            }}
            title={chipSource
              ? (language === 'tr' ? 'Kaynakları düzenle' : 'Edit sources')
              : (language === 'tr' ? 'Analiz için kaynak seçin' : 'Select a source to analyze')}
          >
            {chipSource
              ? (chipSource.type === 'file' ? <FileText size={13} style={{ color: 'var(--color-accent-fg)' }} /> : <Database size={13} style={{ color: 'var(--color-accent-fg)' }} />)
              : <Plus size={13} style={{ color: 'var(--color-accent-fg)' }} />}
            <span
              className="text-[11px] font-medium truncate"
              style={{ color: chipSource ? 'var(--color-text-2)' : 'var(--color-accent-fg)', fontWeight: chipSource ? 500 : 600 }}
            >
              {chipSource
                ? chipSource.label
                : (language === 'tr' ? 'Kaynak seç' : 'Select source')}
            </span>
            {chipSource && chipExtraCount > 0 && (
              <span
                className="flex-shrink-0 font-mono px-1.5 py-0.5"
                style={{ fontSize: 9, background: 'var(--color-accent-subtle)', color: 'var(--color-accent-fg)', borderRadius: 6 }}
              >
                +{chipExtraCount}
              </span>
            )}
          </button>
          <div
            className="flex-1 relative flex items-center transition-all focus-within:border-[var(--color-border-focus)] focus-within:shadow-[0_0_0_3px_var(--color-accent-subtle)]"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '12px',
              overflow: 'hidden'
            }}
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              disabled={isThinking}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isThinking ? t.calculating : t.queryPlaceholder}
              className="flex-1 bg-transparent text-gh-text text-[13px] py-2.5 px-3.5 focus:outline-none border-none"
              style={{ fontFamily: 'var(--font-sans)' }}
            />
          </div>
          <button
            type="submit"
            disabled={!input.trim() || isThinking}
            className="btn btn-primary px-4"
            style={{ gap: 6, borderRadius: '10px' }}
          >
            <Send size={12} />
            {t.runCodeBtn}
          </button>
        </form>

        <div className="mt-2 flex items-center gap-1.5 select-none">
          <span className="text-[9px] text-gh-faint font-mono">
            {t.commandPaletteHint}
          </span>
        </div>
      </div>

    </div>
  );
};

export default ChatConsole;

