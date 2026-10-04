import React, { useEffect, useState } from 'react';
import { useBIStore } from '../context/store';
import { apiFetch } from '../api/client';

interface AnalyticsSummary {
  total_sessions: number;
  total_queries: number;
  total_agent_responses: number;
  success_count: number;
  success_rate: number;
  daily_activity: { day: string; count: number }[];
  code_type_distribution: { language: string; count: number }[];
}

interface SourceStat {
  source_id: string;
  display_name: string;
  session_count: number;
}

const COLORS = ['#c96442', '#d97a56', '#e08a63', '#34d399', '#fbbf24', '#ef4444'];

const Dashboard: React.FC = () => {
  const language = useBIStore((s) => s.language);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [sources, setSources] = useState<SourceStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError('');
      try {
        const [sumData, srcData] = await Promise.all([
          apiFetch('/api/analytics/summary'),
          apiFetch('/api/analytics/sources'),
        ]);
        setSummary(sumData);
        setSources(srcData);
      } catch (err: any) {
        setError(language === 'tr' ? 'İstatistikler yüklenemedi.' : 'Failed to load statistics.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ color: 'var(--color-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 rounded-full border-2 border-[var(--color-accent)] border-t-transparent animate-spin" />
          <span>{language === 'tr' ? 'Analitik yükleniyor...' : 'Loading analytics...'}</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div style={{ color: 'var(--color-danger)', fontSize: 13 }}>{error}</div>
      </div>
    );
  }

  if (!summary) return null;

  const maxActivity = Math.max(...summary.daily_activity.map((d) => d.count), 1);
  const maxSource = Math.max(...sources.map((s) => s.session_count), 1);

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--color-bg)' }}>
      {/* Header */}
      <div className="mb-6">
        <h1 style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-text)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.02em' }}>
          {language === 'tr' ? 'Dashboard' : 'Dashboard'}
        </h1>
        <p style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 4 }}>
          {language === 'tr' ? 'Sistem kullanım istatistikleri ve analiz özeti' : 'System usage statistics and analysis overview'}
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 mb-6" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        {[
          {
            label: language === 'tr' ? 'Toplam Oturum' : 'Total Sessions',
            value: summary.total_sessions,
            color: '#c96442',
            accent: true,
          },
          {
            label: language === 'tr' ? 'Toplam Sorgu' : 'Total Queries',
            value: summary.total_queries,
            color: '',
            accent: false,
          },
          {
            label: language === 'tr' ? 'Başarılı Sorgu' : 'Successful',
            value: summary.success_count,
            color: '',
            accent: false,
          },
          {
            label: language === 'tr' ? 'Başarı Oranı' : 'Success Rate',
            value: `${summary.success_rate}%`,
            color: summary.success_rate >= 80 ? 'var(--color-success)' : summary.success_rate >= 60 ? 'var(--color-warning)' : 'var(--color-danger)',
            accent: false,
          },
        ].map((kpi, i) => (
          <div
            key={i}
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 12,
              padding: '16px 18px',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: 10.5, color: 'var(--color-muted)', fontFamily: 'var(--font-sans)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {kpi.label}
              </div>
              <div
                style={{
                  width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                  background: kpi.accent ? 'var(--color-accent)' : kpi.color || 'var(--color-disabled)',
                  boxShadow: kpi.accent ? '0 0 6px rgba(201,100,66,0.4)' : 'none',
                  opacity: kpi.accent || kpi.color ? 1 : 0.35,
                }}
              />
            </div>
            <div
              style={{
                fontSize: 28, fontWeight: 700,
                color: kpi.color || 'var(--color-text)',
                fontFamily: 'var(--font-sans)',
                letterSpacing: '-0.03em',
                marginTop: 8,
                lineHeight: 1.1,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: '1fr 1fr' }}>
        {/* Son 7 Gün Aktivite */}
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: '20px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-muted)', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.05em', fontFamily: 'var(--font-sans)' }}>
            {language === 'tr' ? 'Son 7 Gün Aktivite' : 'Last 7 Days Activity'}
          </div>
          {summary.daily_activity.length === 0 ? (
            <div style={{ fontSize: 11, color: 'var(--color-faint)', textAlign: 'center', padding: '20px 0' }}>
              {language === 'tr' ? 'Henüz veri yok' : 'No data yet'}
            </div>
          ) : (
            <div className="flex items-end gap-2" style={{ height: 100 }}>
              {summary.daily_activity.map((d, i) => (
                <div key={i} className="flex flex-col items-center gap-1.5 flex-1">
                  <div
                    style={{
                      width: '100%',
                      height: `${(d.count / maxActivity) * 80}px`,
                      minHeight: 4,
                      background: 'var(--color-accent)',
                      opacity: 0.55 + 0.45 * (d.count / maxActivity),
                      borderRadius: '3px 3px 0 0',
                      transition: 'height 0.3s ease',
                    }}
                    title={`${d.day}: ${d.count}`}
                  />
                  <div style={{ fontSize: 9, color: 'var(--color-faint)', fontFamily: 'var(--font-mono)' }}>
                    {d.day.slice(5)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Kod Tipi Dağılımı */}
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: '20px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-muted)', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.05em', fontFamily: 'var(--font-sans)' }}>
            {language === 'tr' ? 'Sorgu Tipi Dağılımı' : 'Query Type Distribution'}
          </div>
          <div className="flex flex-col gap-2.5">
            {summary.code_type_distribution.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--color-faint)', textAlign: 'center', padding: '20px 0' }}>
                {language === 'tr' ? 'Henüz veri yok' : 'No data yet'}
              </div>
            ) : (
              summary.code_type_distribution.map((item, i) => {
                const total = summary.code_type_distribution.reduce((a, b) => a + b.count, 0);
                const pct = total > 0 ? Math.round((item.count / total) * 100) : 0;
                return (
                  <div key={i}>
                    <div className="flex justify-between mb-1">
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--color-text-2)' }}>
                        {item.language.toUpperCase()}
                      </span>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--color-faint)' }}>
                        {pct}% ({item.count})
                      </span>
                    </div>
                    <div style={{ height: 5, background: 'var(--color-canvas)', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: COLORS[i % COLORS.length], borderRadius: 3, transition: 'width 0.4s ease' }} />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* En Aktif Kaynaklar */}
      <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: '20px' }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-muted)', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.05em', fontFamily: 'var(--font-sans)' }}>
          {language === 'tr' ? 'En Aktif Veri Kaynakları' : 'Most Active Data Sources'}
        </div>
        {sources.length === 0 ? (
          <div style={{ fontSize: 11, color: 'var(--color-faint)', textAlign: 'center', padding: '20px 0' }}>
            {language === 'tr' ? 'Henüz oturum yok' : 'No sessions yet'}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {sources.slice(0, 8).map((src, i) => (
              <div key={i} className="flex items-center gap-3">
                <div style={{ width: 22, height: 22, borderRadius: 6, background: 'var(--color-accent-subtle)', border: '1px solid var(--color-border2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: 'var(--color-accent-fg)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between mb-1">
                    <span style={{ fontSize: 11.5, fontFamily: 'var(--font-sans)', fontWeight: 500, color: 'var(--color-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '65%' }}>
                      {src.display_name}
                    </span>
                    <span style={{ fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--color-faint)' }}>
                      {src.session_count} {language === 'tr' ? 'oturum' : 'sessions'}
                    </span>
                  </div>
                  <div style={{ height: 4, background: 'var(--color-canvas)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(src.session_count / maxSource) * 100}%`, background: 'var(--color-accent)', opacity: 0.85, borderRadius: 2, transition: 'width 0.4s ease' }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
