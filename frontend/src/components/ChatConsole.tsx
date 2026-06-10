import React, { useState, useEffect, useRef } from 'react';
import { useBIStore, BACKEND_BASE, type JoinRelation } from '../context/store';
import { translations } from '../context/translations';
import {
  Send, ChevronDown, ChevronRight,
  Copy, Check, RotateCcw, Play, Edit3, X, Search, Plus,
  Database, FileText, Trash2, Layers, GitCommit, Download,
  Loader2, CheckCircle2, Circle, Sparkles, User, FileCode,
  ThumbsUp, ThumbsDown, Link, Zap, AlertTriangle
} from 'lucide-react';




// Autocomplete commands defined dynamically inside ChatConsole component

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
      '<span class="text-[#818cf8] font-semibold">$1</span>'
    ).replace(
      /\b(COUNT|SUM|AVG|MIN|MAX|ROUND|COALESCE|CAST|NOW|DATE|INTERVAL)\b/gi,
      '<span class="text-[#38bdf8]">$1</span>'
    ).replace(
      /\b(\d+)\b/g,
      '<span class="text-[#c084fc]">$1</span>'
    );
  } else if (lang === 'python') {
    tokenized = tokenized.replace(
      /\b(def|import|from|class|return|if|else|elif|for|while|try|except|as|in|is|not|and|or|print|lambda|with|assert|pass|break|continue)\b/g,
      '<span class="text-[#f472b6] font-semibold">$1</span>'
    ).replace(
      /\b(self|pd|np|plt|sns|go|px|sqlite3|conn|df|columns|rows|px|dict|list|str|int|float|set|tuple|len|range)\b/g,
      '<span class="text-[#fb923c]">$1</span>'
    ).replace(
      /\b(\d+)\b/g,
      '<span class="text-[#c084fc]">$1</span>'
    );
  }

  // Restore strings and comments
  const restored = tokenized.replace(/___STR_PLACEHOLDER_(\d+)___/g, (_, index) => {
    const rawMatch = stringsAndComments[parseInt(index, 10)];
    if (rawMatch.startsWith('#') || rawMatch.startsWith('--')) {
      return `<span class="text-zinc-500 italic">${rawMatch}</span>`;
    }
    return `<span class="text-[#34d399] font-medium">${rawMatch}</span>`;
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
      return <h4 key={i} className="text-[11px] font-bold text-indigo-400 uppercase tracking-widest mt-4 mb-2 font-mono flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>{line.replace('### ', '')}</h4>;
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

export const ChatConsole: React.FC = () => {
  const {
    chatHistory, isThinking, sendMessage, clearChat,
    activeSourceId, activeSessionId, updateMessageCode,
    sources, files, selectedSourceIds, setSelectedSourceIds, joinRelations, setJoinRelations,
    sessions,
    showSourcePicker, sourcePickerMode, setShowSourcePicker, createSession, setActiveSourceId,
    language, activeMessageId, setActiveMessageId
  } = useBIStore();


  const t = translations[language];

  const [input, setInput] = useState('');
  const [showSqlPreview, setShowSqlPreview] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [codeOpen] = useState<Record<string, boolean>>({});
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
      const response = await fetch(`${BACKEND_BASE}/api/sessions/${activeSessionId}/messages/${messageId}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ type: rating })
      });
      if (response.ok) {
        console.log("Feedback recorded successfully.");
      }
    } catch (err) {
      console.error("Feedback submission error", err);
    }
  };

  const commands = React.useMemo(() => [
    { cmd: '/graph', desc: language === 'tr' ? 'Plotly ile etkileşimli veri görselleştirme grafiği çizdirin' : 'Draw an interactive data visualization chart with Plotly', template: '/graph ' },
    { cmd: '/ask', desc: language === 'tr' ? 'Genel sorular sorabilirsiniz' : 'You can ask general questions', template: '/ask ' },
    { cmd: '/ml', desc: language === 'tr' ? 'Python ML sandbox ortamında tahminleme ve modelleme koşturun' : 'Run forecasting and modeling in the Python ML sandbox environment', template: '/ml' },
    { cmd: '/table', desc: language === 'tr' ? 'Sorguları tablo formatında temiz veri listesi halinde getirin' : 'Get queries in tabular format as a clean data list', template: '/table' },
    { cmd: '/sqlquery', desc: language === 'tr' ? 'DuckDB/Veritabanı üzerinde doğrudan SQL sorgusu çalıştırın' : 'Execute SQL queries directly on DuckDB/Database', template: '/sqlquery ' },
    { cmd: '/pythonscript', desc: language === 'tr' ? 'Sandbox üzerinde özel Python/Pandas veri işleme betiği çalıştırın' : 'Run custom Python/Pandas data processing scripts in sandbox', template: '/pythonscript' },
    { cmd: '/explain', desc: language === 'tr' ? 'Seçili veri kümesinin şemasını, özet istatistiklerini ve alan açıklamalarını analiz edip açıklayın' : 'Analyze and explain the active dataset\'s schema, summary statistics, and column descriptions', template: '/explain' },
    { cmd: '/forecast', desc: language === 'tr' ? 'Belirli bir sayısal kolon/metrik için zaman serisi tahmini ve trend projeksiyonu yapın' : 'Perform time-series forecasting and trend projection on a specific column/metric', template: '/forecast ' },
    { cmd: '/clean', desc: language === 'tr' ? 'Eksik verileri (NULL), anormal aykırı değerleri (outliers) analiz edin ve temizleme önerileri sunun' : 'Analyze missing values (NULL), anomalies/outliers, and provide automated cleaning suggestions', template: '/clean' },
    { cmd: '/pivot', desc: language === 'tr' ? 'Verileri gruplamak ve alt toplamlar oluşturmak için dinamik pivot analizi gerçekleştirin' : 'Perform dynamic pivot analysis to group data and generate sub-totals', template: '/pivot ' },
    { cmd: '/corr', desc: language === 'tr' ? 'Sayısal değişkenler arasındaki korelasyon ilişkilerini ve istatistiksel bağımlılıkları hesaplayın' : 'Calculate correlation values and statistical dependencies between numerical columns', template: '/corr' },
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
      const res = await fetch(`${BACKEND_BASE}/api/sessions/${activeSessionId}/messages/${msgId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: editedCodeText,
          code_language: lang,
          active_source_id: activeSourceId,
          source_ids: selectedSourceIds,
          relationships: joinRelations
        })
      });

      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          updateMessageCode(msgId, editedCodeText, data.data, data.visualization, data.final_response, undefined, data.auto_corrections);
          setEditingMessageId(null);
        } else {
          setExecutionError(data.error);
          updateMessageCode(msgId, editedCodeText, null, null, data.final_response, data.error, data.auto_corrections);
        }
      } else {
        const errText = await res.text();
        setExecutionError(errText || (language === 'tr' ? "Sunucu çalıştırma hatası." : "Server execution error."));
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

  const isEmpty = chatHistory.length <= 1;


  return (
    <div className="flex flex-col bg-gh-bg overflow-hidden" style={{ flex: 1, height: '100vh' }}>

      {/* ── Top bar ── */}
      <div
        className="flex items-center justify-between shrink-0 px-4 border-b border-gh-border"
        style={{ height: 48, background: 'var(--color-canvas)', borderBottom: '2px solid var(--color-border)' }}
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
                                auto: '#0078d4',
                                inner: '#10b981',
                                left: '#3b82f6',
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
                                      className="border border-gh-border/50 rounded-xl bg-gh-surface shadow-md overflow-hidden select-none hover:border-indigo-500/40 hover:shadow-lg transition-all duration-300 transform hover:-translate-y-[1px]"
                                      style={{ background: 'var(--color-bg)' }}
                                    >
                                      {/* Table Header */}
                                      <div className="px-3 py-2 border-b border-gh-border/50 flex items-center gap-2 shrink-0 select-none bg-zinc-900/10 dark:bg-white/[0.02]">
                                        {isDb ? <Database size={11} className="text-indigo-400" /> : <FileText size={11} className="text-emerald-400" />}
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
                                              ? 'bg-indigo-500/10 border-indigo-500 text-indigo-400 font-bold shadow-[0_0_8px_rgba(99,102,241,0.25)] animate-pulse'
                                              : isJoined
                                                ? 'bg-gh-canvas border-gh-border text-gh-text hover:border-zinc-500'
                                                : 'bg-transparent border-transparent text-gh-muted hover:bg-gh-surface hover:text-gh-text'
                                          );
                                          
                                          const indicatorClass = "w-2 h-2 rounded-full border transition-all " + (
                                            isSelected 
                                              ? 'bg-indigo-500 border-indigo-500 scale-110 shadow-[0_0_6px_#6366f1]'
                                              : isJoined
                                                ? 'bg-indigo-500/60 border-indigo-500/30'
                                                : 'bg-transparent border-gh-border'
                                          );

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
                                              <div className={indicatorClass} />
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

        {/* Empty state — Terminal Amber minimal */}
        {isEmpty && (
          <div className="flex flex-col justify-center h-full pb-20 animate-fade-in px-4" style={{ maxWidth: 560 }}>
            <div className="font-mono text-[10px] text-gh-faint uppercase tracking-widest mb-6">DeepBI / Analytics Studio — v1.2.1</div>
            <div className="border-l-2 border-gh-accent pl-4 mb-6">
              <div className="text-base font-bold text-gh-text font-mono tracking-tight">Analiz motoruna hoş geldiniz.</div>
              <div className="text-xs text-gh-muted font-mono mt-1 leading-relaxed">
                SQL sorguları, Python/Pandas analizi ve ML tahminleme için aşağıdan talep yazın.
              </div>
            </div>
            <div className="space-y-1.5">
              {[
                { cmd: '/graph', desc: 'Plotly ile etkileşimli grafik' },
                { cmd: '/ml', desc: 'Makine öğrenmesi & tahminleme' },
                { cmd: '/sqlquery', desc: 'Doğrudan SQL sorgusu çalıştır' },
                { cmd: '/ask', desc: 'Analitik soru sor' },
              ].map(({ cmd, desc }) => (
                <button
                  key={cmd}
                  onClick={() => { setInput(cmd + ' '); inputRef.current?.focus(); }}
                  className="flex items-center gap-3 w-full text-left px-3 py-2 border border-gh-border hover:border-gh-accent hover:bg-gh-accent-subtle transition-all group"
                  style={{ borderRadius: '8px' }}
                >
                  <span className="text-gh-accent font-mono text-xs font-bold group-hover:text-gh-accent">{cmd}</span>
                  <span className="text-gh-faint font-mono text-[10px]">{desc}</span>
                </button>
              ))}
            </div>
            <div className="mt-4 text-[9px] text-gh-faint font-mono">
              <span className="text-gh-accent">›</span> Veri kaynağı seçili: <span className="text-gh-muted">{srcLabel}</span>
            </div>
          </div>
        )}

        {chatHistory.map((msg, msgIdx) => {
          const isAgent = msg.role === 'agent';
          const hasLog = isAgent && msg.statusHistory.length > 0;
          const hasCode = isAgent && !!msg.code;
          const isLogOpen = logOpen[msg.id] !== false;
          const isCodeOpen = codeOpen[msg.id] !== false;

          const nextAgent = msg.role === 'user' ? chatHistory.slice(msgIdx + 1).find(m => m.role === 'agent') : null;
          const isUserActive = nextAgent ? nextAgent.id === resolvedActiveMessageId : false;
          const canActivateUser = !!(nextAgent && (nextAgent.data || nextAgent.visualization || nextAgent.error));

          const isAgentActive = msg.id === resolvedActiveMessageId;
          const canActivateAgent = !!(msg.data || msg.visualization || msg.error);

          return (
            <div key={msg.id} className="animate-fade-in w-full px-2 py-1">

              {/* ── USER QUERY ROW ── */}
              {!isAgent && (
                <div
                  onClick={() => canActivateUser && activateMessageForIndex(msgIdx)}
                  className={`msg-user transition-all duration-300 border-l-4 ${canActivateUser ? 'cursor-pointer hover:border-indigo-500/80 hover:shadow-[0_8px_24px_rgba(99,102,241,0.06)]' : ''} ${isUserActive ? 'border-indigo-500 bg-indigo-500/[0.04] shadow-[0_4px_20px_rgba(99,102,241,0.08)]' : ''}`}
                  style={{
                    borderRadius: '0 12px 12px 0',
                    borderLeftColor: isUserActive ? '#6366f1' : 'var(--color-accent)'
                  }}
                  title={canActivateUser ? (language === 'tr' ? "Panele yansıtmak için tıklayın" : "Click to display in panel") : undefined}
                >
                  <div className="flex gap-4 items-start">
                    {/* User Avatar */}
                    <div
                      className="flex-shrink-0 w-8 h-8 rounded-xl border border-gh-border bg-gh-surface flex items-center justify-center shadow-md"
                      style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
                    >
                      <User size={13} style={{ color: '#6366f1' }} />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span className="text-[9px] font-mono font-bold text-indigo-400 uppercase tracking-widest">›  SORGU</span>
                          <span className="text-[9px] font-mono text-gh-faint/60">{new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        {isUserActive && (
                          <span className="text-[8px] font-mono font-bold text-indigo-400 uppercase tracking-widest bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                            {language === 'tr' ? 'GÖSTERİLİYOR' : 'DISPLAYED'}
                          </span>
                        )}
                      </div>
                      <p className="font-mono text-xs text-gh-text select-text whitespace-pre-wrap leading-relaxed dark:text-zinc-200 text-zinc-800">{msg.text}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* ── AGENT RESPONSE SECTION ── */}
              {isAgent && (
                <div
                  onClick={() => canActivateAgent && activateMessageForIndex(msgIdx)}
                  className={`msg-agent transition-all duration-300 border-l-4 ${canActivateAgent ? 'cursor-pointer hover:border-indigo-500/80 hover:shadow-[0_8px_24px_rgba(99,102,241,0.06)]' : ''} ${isAgentActive ? 'animate-glow-border border-indigo-500' : 'border-gh-border'}`}
                  style={{
                    borderRadius: '12px',
                    borderLeftColor: isAgentActive ? '#6366f1' : 'var(--color-border)',
                    boxShadow: isAgentActive ? '0 12px 36px rgba(99, 102, 241, 0.15)' : 'none'
                  }}
                  title={canActivateAgent ? (language === 'tr' ? "Panele yansıtmak için tıklayın" : "Click to display in panel") : undefined}
                >
                  <div className="flex gap-4 items-start">
                    {/* Agent Avatar */}
                    <div
                      className="flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center shadow-lg mt-0.5"
                      style={{
                        background: 'linear-gradient(135deg, #6366f1 0%, #a78bfa 100%)',
                        boxShadow: '0 4px 14px rgba(99, 102, 241, 0.35)'
                      }}
                    >
                      <Sparkles size={13} style={{ color: '#ffffff' }} />
                    </div>

                    <div className="flex-1 min-w-0">
                      {/* Section header */}
                      <div className="flex items-center justify-between mb-4 pb-3" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                        <div className="flex items-center gap-3">
                          <span className="text-[9px] font-mono font-bold text-gh-muted uppercase tracking-widest flex items-center gap-1.5"><Sparkles size={11} className="text-indigo-400" /> {language === 'tr' ? 'ANALİZ RAPORU & ÇIKTILAR' : 'ANALYSIS REPORT & OUTPUTS'}</span>
                          {isThinking && msgIdx === chatHistory.length - 1 && (
                            <span className="dot-processing" />
                          )}
                        </div>
                        {isAgentActive && (
                          <span className="text-[8px] font-mono font-bold text-indigo-400 uppercase tracking-widest bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                            {language === 'tr' ? 'GÖSTERİLİYOR' : 'DISPLAYED'}
                          </span>
                        )}
                      </div>

                      {/* KPI Cards (Glassmorphism layout) */}
                      {(() => {
                        const kpis = extractKPIs(msg.text || '');
                        if (kpis.length > 0) {
                          return (
                            <div className="grid grid-cols-3 gap-3 mb-4 animate-slide-up select-none">
                              {kpis.map((kpi, kpiIdx) => {
                                const colors = ['#818cf8', '#34d399', '#f472b6'];
                                const activeColor = colors[kpiIdx % colors.length];
                                return (
                                  <div
                                    key={kpiIdx}
                                    className="premium-glass p-3 relative overflow-hidden transition-all duration-300 hover:scale-[1.03] hover:-translate-y-[2px]"
                                    style={{
                                      borderLeft: `3px solid ${activeColor}`,
                                      borderRadius: '10px'
                                    }}
                                  >
                                    <span className="text-[8px] uppercase font-bold tracking-wider block text-zinc-400 font-mono mb-1">{kpi.label}</span>
                                    <span className="text-sm font-bold tracking-tight block font-mono" style={{ color: activeColor }}>
                                      {kpi.value}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          );
                        }
                        return null;
                      })()}

                      {/* Auto-correction badge */}
                      {msg.auto_corrections && msg.auto_corrections.applied && (
                        <div className="mb-4 px-3.5 py-2.5 text-[11px] font-semibold border border-indigo-500/20 text-indigo-400 flex items-center justify-between font-mono rounded-lg" style={{ background: 'rgba(99, 102, 241, 0.06)', borderLeft: '3px solid #6366f1' }}>
                          <div className="flex items-center gap-2">
                            <Sparkles size={11} className="text-indigo-400 shrink-0" />
                            <span>Tablo çözümleme düzeltmesi uygulandı: </span>
                            <span className="font-mono bg-indigo-500/10 px-1.5 py-0.5 border border-indigo-500/20 text-indigo-300 rounded ml-1">
                              {Object.entries(msg.auto_corrections.applied).map(([k, v]) => `${k}→${v}`).join(', ')}
                            </span>
                          </div>
                          <button onClick={() => setLogOpen(p => ({ ...p, [`corr-${msg.id}`]: !(p[`corr-${msg.id}`]) }))} className="text-[10px] underline hover:text-indigo-300">Detay</button>
                          {logOpen[`corr-${msg.id}`] && (
                            <div className="mt-2.5 text-[10.5px] text-zinc-400 bg-zinc-950/40 p-2.5 border border-gh-border font-mono rounded-md w-full">
                              <div className="text-zinc-300 font-bold mb-1">Düzeltme Adımları:</div>
                              <ul className="list-disc list-inside space-y-1 font-mono">
                                {Object.entries(msg.auto_corrections.applied).map(([k, v]) => (
                                  <li key={`ac-${k}`}>{k} → {String(v)}</li>
                                ))}
                              </ul>
                              {msg.auto_corrections.ambiguous && (
                                <div className="mt-2 text-[10.5px] text-amber-400">Belirsiz şema referansları: {msg.auto_corrections.ambiguous.join(', ')}</div>
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
                              <span className="text-indigo-400 font-bold">$</span>
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
                                        <Loader2 className="animate-spin text-indigo-400" size={13} />
                                      ) : isCompleted ? (
                                        <CheckCircle2 size={13} style={{ color: '#10b981' }} />
                                      ) : (
                                        <Circle size={13} style={{ color: 'var(--color-faint)' }} />
                                      )}
                                    </div>

                                    {/* Description */}
                                    <div className="flex-1 pb-2">
                                      <span
                                        className={`font-mono text-[10.5px] leading-relaxed block ${live ? 'text-indigo-400 font-bold' : 'text-zinc-400'}`}
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
                          <div className="flex items-center justify-between px-3 py-2 bg-zinc-900 border-b border-gh-border shrink-0 select-none">
                            <div className="flex items-center gap-2">
                              <FileCode size={12} className="text-indigo-400" />
                              <span className="text-[10px] font-mono font-bold text-zinc-300 uppercase tracking-wider">{msg.codeLanguage ?? 'code'}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              {editingMessageId === msg.id ? (
                                <>
                                  <button
                                    onClick={() => handleRunEditedCode(msg.id, msg.codeLanguage as any)}
                                    disabled={isExecutingCode}
                                    className="p-1 rounded bg-indigo-500 hover:bg-indigo-600 disabled:bg-zinc-800 text-white cursor-pointer"
                                    title={language === 'tr' ? "Kodu Çalıştır" : "Run Code"}
                                  >
                                    {isExecutingCode ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                                  </button>
                                  <button
                                    onClick={cancelEditing}
                                    className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 cursor-pointer"
                                    title={language === 'tr' ? "İptal" : "Cancel"}
                                  >
                                    <X size={11} />
                                  </button>
                                </>
                              ) : (
                                <>
                                  <button
                                    onClick={() => startEditing(msg.id, msg.code ?? '')}
                                    className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 cursor-pointer"
                                    title={language === 'tr' ? "Düzenle" : "Edit"}
                                  >
                                    <Edit3 size={11} />
                                  </button>
                                  <button
                                    onClick={() => copyCode(msg.code ?? '', msg.id)}
                                    className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 cursor-pointer"
                                    title={language === 'tr' ? "Kopyala" : "Copy"}
                                  >
                                    {copied === msg.id ? <Check size={11} className="text-green-400" /> : <Copy size={11} />}
                                  </button>
                                  <button
                                    onClick={() => downloadCode(msg.code ?? '', msg.codeLanguage, msg.id)}
                                    className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 cursor-pointer"
                                    title={language === 'tr' ? "İndir" : "Download"}
                                  >
                                    <Download size={11} />
                                  </button>
                                </>
                              )}
                            </div>
                          </div>

                          {editingMessageId === msg.id ? (
                            <div className="flex flex-col bg-zinc-950/20 border-t border-gh-border w-full">
                              <div className="flex font-mono text-[11px] bg-zinc-900 w-full relative overflow-hidden" style={{ minHeight: 160 }}>
                                <div className="select-none text-right pr-2.5 pl-3 py-3 bg-zinc-950/40 border-r border-gh-border text-zinc-600 flex flex-col pointer-events-none" style={{ minWidth: 36, userSelect: 'none' }}>
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
                              <pre className="overflow-x-auto px-4.5 py-4 select-text" style={{ maxHeight: 240, fontSize: 11.5, lineHeight: 1.65, background: '#18181b', color: '#f4f4f5' }}>
                                <code dangerouslySetInnerHTML={{ __html: highlightCode(msg.code ?? '', msg.codeLanguage ?? '') }} />
                              </pre>
                            )
                          )}
                        </div>
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
      <div className="shrink-0 px-4 py-3 bg-gh-bg border-t border-gh-border relative" style={{ borderTop: '2px solid var(--color-border)' }}>

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
              borderLeft: '3px solid var(--color-accent)',
              borderRadius: '12px',
              maxHeight: '240px',
              overflowY: 'auto',
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)'
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
                    borderBottom: '1px solid var(--color-border)'
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

        <form onSubmit={send} className="flex gap-2">
          <div className="flex-1 relative flex items-center shadow-inner" style={{ borderLeft: '3px solid var(--color-accent)', background: 'var(--color-canvas)', borderRadius: '8px', overflow: 'hidden' }}>
            <span className="pl-3 pr-1 text-gh-accent font-mono text-xs font-bold shrink-0">›</span>
            <input
              ref={inputRef}
              type="text"
              value={input}
              disabled={isThinking}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isThinking ? t.calculating : t.queryPlaceholder}
              className="flex-1 bg-transparent text-gh-text font-mono text-xs py-3 pr-3 focus:outline-none border-none"
              style={{ fontSize: 12 }}
            />
          </div>
          <button
            type="submit"
            disabled={!input.trim() || isThinking}
            className="btn btn-primary px-4"
            style={{ gap: 6, borderRadius: '8px' }}
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

