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
    color: '#c96442',
    tr: 'Veri üzerinden grafik ve görselleştirme oluşturur',
    en: 'Creates charts and visualizations from data',
    example: '/graph satış trendi',
    type: 'PYTHON',
  },
  {
    cmd: '/sql',
    icon: '🗄️',
    color: '#c96442',
    tr: 'Doğrudan SQL sorgusu çalıştırır',
    en: 'Runs a direct SQL query',
    example: '/sql SELECT * FROM orders LIMIT 10',
    type: 'SQL',
  },
  {
    cmd: '/table',
    icon: '📋',
    color: '#c96442',
    tr: 'Tablosal veri listesi getirir',
    en: 'Fetches tabular data list',
    example: '/table tüm ürünleri listele',
    type: 'SQL',
  },
  {
    cmd: '/forecast',
    icon: '🔮',
    color: '#e08a63',
    tr: 'Zaman serisi tahmini (ML/Trend)',
    en: 'Time series forecasting (ML/Trend)',
    example: '/forecast gelecek 3 ay satış',
    type: 'ML',
  },
  {
    cmd: '/ml',
    icon: '🤖',
    color: '#e08a63',
    tr: 'Makine öğrenmesi analizi (sınıflandırma, kümeleme)',
    en: 'Machine learning analysis (classification, clustering)',
    example: '/ml müşteri segmentasyonu',
    type: 'ML',
  },
  {
    cmd: '/corr',
    icon: '🔗',
    color: '#e08a63',
    tr: 'Korelasyon analizi ve Heatmap oluşturur',
    en: 'Correlation analysis and Heatmap',
    example: '/corr tüm sütunlar',
    type: 'ML',
  },
  {
    cmd: '/pivot',
    icon: '🔄',
    color: '#fbbf24',
    tr: 'Dinamik pivot tablo analizi',
    en: 'Dynamic pivot table analysis',
    example: '/pivot bölge × ürün × satış',
    type: 'PYTHON',
  },
  {
    cmd: '/clean',
    icon: '🧹',
    color: '#34d399',
    tr: 'Veri temizleme ve EDA (Keşifsel Veri Analizi)',
    en: 'Data cleaning and EDA',
    example: '/clean eksik değerleri analiz et',
    type: 'PYTHON',
  },
  {
    cmd: '/explain',
    icon: '🔬',
    color: '#34d399',
    tr: 'Veri açıklama ve istatistiksel özet',
    en: 'Data explanation and statistical summary',
    example: '/explain satış sütununu açıkla',
    type: 'PYTHON',
  },
  {
    cmd: '/ask',
    icon: '💡',
    color: '#fbbf24',
    tr: 'Kavramsal/teorik soru sorma modu',
    en: 'Conceptual/theoretical question mode',
    example: '/ask makine öğrenmesi nedir?',
    type: 'INFO',
  },
  {
    cmd: '/rapor',
    icon: '📄',
    color: '#c96442',
    tr: 'Detaylı analiz raporu oluşturur',
    en: 'Generates a detailed analysis report',
    example: '/rapor satış analizi',
    type: 'REPORT',
  },
  {
    cmd: '/bilgi',
    icon: '📚',
    color: '#fbbf24',
    tr: 'Bilgi sorgulama (Türkçe alias)',
    en: 'Knowledge query (Turkish alias)',
    example: '/bilgi korelasyon nedir',
    type: 'INFO',
  },
  {
    cmd: '/help',
    icon: '❓',
    color: '#a1a1aa',
    tr: 'Kullanım rehberi ve yardım',
    en: 'Usage guide and help',
    example: '/help',
    type: 'INFO',
  },
];

const TYPE_COLORS: Record<string, string> = {
  SQL: 'var(--color-accent-subtle)',
  PYTHON: 'var(--color-accent-subtle)',
  ML: 'var(--color-warning-subtle)',
  INFO: 'var(--color-warning-subtle)',
  REPORT: 'var(--color-accent-subtle)',
};

const TYPE_TEXT: Record<string, string> = {
  SQL: 'var(--color-accent-fg)',
  PYTHON: 'var(--color-accent-fg)',
  ML: 'var(--color-warning)',
  INFO: 'var(--color-warning)',
  REPORT: 'var(--color-accent-fg)',
};

const CommandHelpModal: React.FC<CommandHelpModalProps> = ({ open, onClose, language }) => {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(28,25,23,0.35)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        className="relative flex flex-col"
        style={{
          background: 'var(--color-canvas)',
          border: '1px solid var(--color-border)',
          borderRadius: 12,
          width: '92%',
          maxWidth: 720,
          maxHeight: '85vh',
          boxShadow: '0 12px 32px rgba(28,25,23,0.10)',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 shrink-0"
          style={{ height: 56, borderBottom: '1px solid var(--color-border)' }}
        >
          <div className="flex items-center gap-3">
            <div
              className="flex items-center justify-center shadow-[0_0_12px_rgba(201,100,66,0.25)]"
              style={{
                width: 30, height: 30, borderRadius: 8,
                background: 'linear-gradient(135deg, #c96442, #b8532f)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13,
              }}
            >
              ⌨️
            </div>
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--color-text)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.01em' }}>
                {language === 'tr' ? 'Komut Paleti' : 'Command Palette'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--color-faint)', fontFamily: 'var(--font-mono)' }}>
                {COMMANDS.length} {language === 'tr' ? 'komut mevcut' : 'commands available'}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="btn-icon cursor-pointer hover:bg-[var(--color-surface2)] hover:text-[var(--color-text)] transition-colors"
            style={{ padding: 6, borderRadius: 8, color: 'var(--color-muted)', display: 'flex', alignItems: 'center' }}
          >
            <X size={15} />
          </button>
        </div>

        {/* Info banner */}
        <div
          className="px-5 py-3 shrink-0"
          style={{ background: 'var(--color-accent-subtle)', borderBottom: '1px solid var(--color-border)' }}
        >
          <div style={{ fontSize: 11, color: 'var(--color-text-2)', fontFamily: 'var(--font-sans)', lineHeight: 1.5 }}>
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
                  borderRadius: 8,
                  padding: '12px 14px',
                  transition: 'border-color 0.15s, background 0.15s',
                }}
                className="hover:bg-[var(--color-surface2)] hover:border-[var(--color-border)] transition-all"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span style={{ fontSize: 15 }}>{cmd.icon}</span>
                  <code
                    style={{
                      fontSize: 11.5, fontWeight: 700, color: 'var(--color-accent-fg)',
                      fontFamily: 'var(--font-mono)',
                      background: 'var(--color-canvas)',
                      border: '1px solid var(--color-border)',
                      padding: '2px 8px', borderRadius: 5,
                    }}
                  >
                    {cmd.cmd}
                  </code>
                  <span
                    style={{
                      fontSize: 8.5, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      background: TYPE_COLORS[cmd.type],
                      color: TYPE_TEXT[cmd.type],
                      border: '1px solid var(--color-border2)',
                      padding: '2px 6px', borderRadius: 4, textTransform: 'uppercase', letterSpacing: '0.05em',
                    }}
                  >
                    {cmd.type}
                  </span>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--color-text-2)', fontFamily: 'var(--font-sans)', lineHeight: 1.45, marginBottom: 8 }}>
                  {language === 'tr' ? cmd.tr : cmd.en}
                </div>
                <div
                  style={{
                    fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-muted)',
                    background: 'var(--color-canvas)', padding: '4px 8px', borderRadius: 5,
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
