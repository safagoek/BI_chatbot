import React from 'react';
import { X } from 'lucide-react';

interface CommandHelpModalProps {
  open: boolean;
  onClose: () => void;
  language: 'tr' | 'en';
}

const COMMANDS = [
  {
    cmd: '/graph',
    icon: '📈',
    color: '#6366f1',
    tr: 'Veri üzerinden grafik ve görselleştirme oluşturur',
    en: 'Creates charts and visualizations from data',
    example: '/graph satış trendi',
    type: 'PYTHON',
  },
  {
    cmd: '/sql',
    icon: '🗄️',
    color: '#06b6d4',
    tr: 'Doğrudan SQL sorgusu çalıştırır',
    en: 'Runs a direct SQL query',
    example: '/sql SELECT * FROM orders LIMIT 10',
    type: 'SQL',
  },
  {
    cmd: '/table',
    icon: '📋',
    color: '#06b6d4',
    tr: 'Tablosal veri listesi getirir',
    en: 'Fetches tabular data list',
    example: '/table tüm ürünleri listele',
    type: 'SQL',
  },
  {
    cmd: '/forecast',
    icon: '🔮',
    color: '#a855f7',
    tr: 'Zaman serisi tahmini (ML/Trend)',
    en: 'Time series forecasting (ML/Trend)',
    example: '/forecast gelecek 3 ay satış',
    type: 'ML',
  },
  {
    cmd: '/ml',
    icon: '🤖',
    color: '#a855f7',
    tr: 'Makine öğrenmesi analizi (sınıflandırma, kümeleme)',
    en: 'Machine learning analysis (classification, clustering)',
    example: '/ml müşteri segmentasyonu',
    type: 'ML',
  },
  {
    cmd: '/corr',
    icon: '🔗',
    color: '#a855f7',
    tr: 'Korelasyon analizi ve Heatmap oluşturur',
    en: 'Correlation analysis and Heatmap',
    example: '/corr tüm sütunlar',
    type: 'ML',
  },
  {
    cmd: '/pivot',
    icon: '🔄',
    color: '#f59e0b',
    tr: 'Dinamik pivot tablo analizi',
    en: 'Dynamic pivot table analysis',
    example: '/pivot bölge × ürün × satış',
    type: 'PYTHON',
  },
  {
    cmd: '/clean',
    icon: '🧹',
    color: '#10b981',
    tr: 'Veri temizleme ve EDA (Keşifsel Veri Analizi)',
    en: 'Data cleaning and EDA',
    example: '/clean eksik değerleri analiz et',
    type: 'PYTHON',
  },
  {
    cmd: '/explain',
    icon: '🔬',
    color: '#10b981',
    tr: 'Veri açıklama ve istatistiksel özet',
    en: 'Data explanation and statistical summary',
    example: '/explain satış sütununu açıkla',
    type: 'PYTHON',
  },
  {
    cmd: '/ask',
    icon: '💡',
    color: '#f59e0b',
    tr: 'Kavramsal/teorik soru sorma modu',
    en: 'Conceptual/theoretical question mode',
    example: '/ask makine öğrenmesi nedir?',
    type: 'INFO',
  },
  {
    cmd: '/rapor',
    icon: '📄',
    color: '#6366f1',
    tr: 'Detaylı analiz raporu oluşturur',
    en: 'Generates a detailed analysis report',
    example: '/rapor satış analizi',
    type: 'REPORT',
  },
  {
    cmd: '/bilgi',
    icon: '📚',
    color: '#f59e0b',
    tr: 'Bilgi sorgulama (Türkçe alias)',
    en: 'Knowledge query (Turkish alias)',
    example: '/bilgi korelasyon nedir',
    type: 'INFO',
  },
  {
    cmd: '/help',
    icon: '❓',
    color: '#6b7280',
    tr: 'Kullanım rehberi ve yardım',
    en: 'Usage guide and help',
    example: '/help',
    type: 'INFO',
  },
];

const TYPE_COLORS: Record<string, string> = {
  SQL: 'rgba(6,182,212,0.15)',
  PYTHON: 'rgba(99,102,241,0.15)',
  ML: 'rgba(168,85,247,0.15)',
  INFO: 'rgba(245,158,11,0.15)',
  REPORT: 'rgba(99,102,241,0.15)',
};

const TYPE_TEXT: Record<string, string> = {
  SQL: '#06b6d4',
  PYTHON: '#818cf8',
  ML: '#c084fc',
  INFO: '#f59e0b',
  REPORT: '#818cf8',
};

const CommandHelpModal: React.FC<CommandHelpModalProps> = ({ open, onClose, language }) => {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        className="relative flex flex-col"
        style={{
          background: 'var(--color-canvas)',
          border: '1px solid var(--color-border)',
          borderRadius: 16,
          width: '92%',
          maxWidth: 720,
          maxHeight: '85vh',
          boxShadow: '0 32px 64px rgba(0,0,0,0.4)',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 shrink-0"
          style={{ height: 56, borderBottom: '1px solid var(--color-border)', background: 'var(--color-bg)' }}
        >
          <div className="flex items-center gap-3">
            <div
              style={{
                width: 32, height: 32, borderRadius: 8,
                background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 14,
              }}
            >
              ⌨️
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.015em' }}>
                {language === 'tr' ? 'Komut Paleti' : 'Command Palette'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'var(--font-mono)' }}>
                {COMMANDS.length} {language === 'tr' ? 'komut mevcut' : 'commands available'}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="btn-icon cursor-pointer hover:text-rose-400 hover:border-rose-500/30 transition-all"
            style={{ padding: 6, borderRadius: 8 }}
          >
            <X size={15} />
          </button>
        </div>

        {/* Info banner */}
        <div
          className="px-6 py-3 shrink-0"
          style={{ background: 'rgba(99,102,241,0.06)', borderBottom: '1px solid var(--color-border)' }}
        >
          <div style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'var(--font-sans)' }}>
            {language === 'tr'
              ? '💡 Sohbet kutusuna / ile başlayarak doğrudan komut moduna geçebilirsiniz. Komut yazmadan da doğal dil sorgusu yapabilirsiniz — sistem otomatik yönlendirir.'
              : '💡 Type / in the chat box to activate command mode directly. You can also ask in natural language without commands — the system auto-routes.'}
          </div>
        </div>

        {/* Command Grid */}
        <div className="overflow-y-auto flex-1 p-5" style={{ scrollbarWidth: 'thin' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
            {COMMANDS.map((cmd) => (
              <div
                key={cmd.cmd}
                style={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 10,
                  padding: '12px 14px',
                  transition: 'border-color 0.15s, background 0.15s',
                }}
                className="hover:border-indigo-500/30 hover:bg-indigo-500/5 transition-all"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span style={{ fontSize: 16 }}>{cmd.icon}</span>
                  <code
                    style={{
                      fontSize: 12, fontWeight: 700, color: cmd.color,
                      fontFamily: 'var(--font-mono)',
                      background: `${cmd.color}18`,
                      padding: '2px 7px', borderRadius: 5,
                    }}
                  >
                    {cmd.cmd}
                  </code>
                  <span
                    style={{
                      fontSize: 8.5, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      background: TYPE_COLORS[cmd.type],
                      color: TYPE_TEXT[cmd.type],
                      padding: '2px 5px', borderRadius: 4, textTransform: 'uppercase', letterSpacing: '0.04em',
                    }}
                  >
                    {cmd.type}
                  </span>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--color-text-2)', fontFamily: 'var(--font-sans)', lineHeight: 1.4, marginBottom: 8 }}>
                  {language === 'tr' ? cmd.tr : cmd.en}
                </div>
                <div
                  style={{
                    fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-faint)',
                    background: 'var(--color-bg)', padding: '4px 8px', borderRadius: 5,
                    border: '1px solid var(--color-border)', wordBreak: 'break-all',
                  }}
                >
                  {cmd.example}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CommandHelpModal;
