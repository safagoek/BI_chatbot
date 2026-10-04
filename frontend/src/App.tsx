import React, { useEffect, useRef, useState, lazy, Suspense } from 'react';
import { useBIStore } from './context/store';
import Sidebar from './components/Sidebar';
import ChatConsole from './components/ChatConsole';
import ResultVisualizer from './components/ResultVisualizer';
import LoginPage from './components/LoginPage';

const SourceManager = lazy(() => import('./components/SourceManager'));
const Dashboard = lazy(() => import('./components/Dashboard'));
const RAGMemoryPanel = lazy(() => import('./components/RAGMemoryPanel'));
const CommandHelpModal = lazy(() => import('./components/CommandHelpModal'));
const SettingsPage = lazy(() => import('./components/SettingsPage'));

import { HardDrive, X, LayoutDashboard, Brain, MessageSquare, Settings, Sun, Moon } from 'lucide-react';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import {
  Dialog, DialogTitle, DialogContent, Box, Typography, IconButton, CircularProgress
} from '@mui/material';

type MainView = 'chat' | 'dashboard' | 'rag' | 'settings';

export const App: React.FC = () => {
  const user = useBIStore((s) => s.user);
  const authChecked = useBIStore((s) => s.authChecked);
  const fetchMe = useBIStore((s) => s.fetchMe);
  const logout = useBIStore((s) => s.logout);
  const fetchSources = useBIStore((s) => s.fetchSources);
  const fetchFiles = useBIStore((s) => s.fetchFiles);
  const language = useBIStore((s) => s.language);
  const visualizerDismissed = useBIStore((s) => s.visualizerDismissed);
  const studioMode = useBIStore((s) => s.studioMode);
  const setStudioMode = useBIStore((s) => s.setStudioMode);

  const [splitRatio, setSplitRatio] = useState(0.42);
  const splitContainerRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);

  // Active main view
  const [activeTab, setActiveTab] = useState<MainView>('chat');

  // Data sources overlay dialog (quick access — full yönetim Ayarlar sayfasında)
  const [showSources, setShowSources] = useState(false);
  const [showCommandHelp, setShowCommandHelp] = useState(false);

  // Oturum kontrolü + 401'de login ekranına dönüş
  useEffect(() => {
    fetchMe();
    const onUnauthorized = () => logout();
    window.addEventListener('deepbi:unauthorized', onUnauthorized);
    return () => window.removeEventListener('deepbi:unauthorized', onUnauthorized);
  }, [fetchMe, logout]);

  const toggleTheme = () => {
    const next = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
    document.documentElement.classList.toggle('dark', next === 'dark');
    document.documentElement.classList.toggle('light', next === 'light');
    localStorage.setItem('theme', next);
  };

  // Theme from storage (dark-first)
  const [theme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('theme') === 'dark' ? 'dark' : 'light';
    }
    return 'light';
  });

  useEffect(() => {
    const html = document.documentElement;
    html.classList.toggle('dark', theme === 'dark');
    html.classList.toggle('light', theme !== 'dark');
  }, [theme]);

  useEffect(() => {
    const handleMove = (event: PointerEvent) => {
      if (!isDraggingRef.current || !splitContainerRef.current) return;
      const rect = splitContainerRef.current.getBoundingClientRect();
      const nextRatio = (event.clientX - rect.left) / rect.width;
      const clampedRatio = Math.min(0.7, Math.max(0.3, nextRatio));
      setSplitRatio(clampedRatio);
    };

    const handleUp = () => {
      isDraggingRef.current = false;
    };

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);

    return () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
    };
  }, []);

  const handleSplitterDown = (event: React.PointerEvent<HTMLDivElement>) => {
    isDraggingRef.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const isDark = theme === 'dark';

  const muiTheme = React.useMemo(() => {
    return createTheme({
      palette: {
        mode: theme,
        primary: { main: '#c96442', light: '#e08a63', dark: '#a34628', contrastText: '#ffffff' },
        background: { default: isDark ? '#1b1917' : '#faf9f7', paper: isDark ? '#282521' : '#ffffff' },
        text: { primary: isDark ? '#faf9f7' : '#1f1e1c', secondary: isDark ? '#a8a29e' : '#78716c' },
        divider: isDark ? 'rgba(255,255,255,0.10)' : 'rgba(28,25,23,0.09)',
        error: { main: isDark ? '#ef4444' : '#dc2626' },
        success: { main: isDark ? '#34d399' : '#059669' },
        warning: { main: isDark ? '#fbbf24' : '#d97706' },
      },
      typography: {
        fontFamily: "'Inter', 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
        fontSize: 13,
        button: { textTransform: 'none', fontWeight: 600, letterSpacing: 0 },
      },
      shape: { borderRadius: 8 },
      components: {
        MuiDialog: {
          styleOverrides: {
            paper: {
              backgroundImage: 'none',
              backgroundColor: isDark ? '#16161a' : '#ffffff',
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.08)'}`,
              boxShadow: isDark ? '0 24px 48px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.02)' : '0 16px 32px rgba(0,0,0,0.12)',
              borderRadius: 12,
            }
          }
        },
        MuiCard: {
          styleOverrides: {
            root: {
              backgroundImage: 'none',
              backgroundColor: isDark ? '#16161a' : '#ffffff',
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.08)'}`,
              boxShadow: 'none',
              borderRadius: 10,
            }
          }
        },
      }
    });
  }, [theme, isDark]);

  // ─── Auth gate ──────────────────────────────────────────────────────────────
  if (!authChecked) {
    return (
      <div className="w-screen h-screen flex items-center justify-center bg-gh-bg">
        <CircularProgress size={28} sx={{ color: '#6366f1' }} />
      </div>
    );
  }

  if (!user) {
    return (
      <ThemeProvider theme={muiTheme}>
        <LoginPage />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={muiTheme}>
      <div className="w-screen h-screen flex bg-gh-bg text-gh-text overflow-hidden relative">

        {/* 1. Global Navigation Sidebar */}
        <Sidebar onOpenSources={() => setShowSources(true)} />

        {/* 2. Main Content Viewport */}
        <main className="flex-1 h-full flex flex-col overflow-hidden">
          {/* Top Bar — segmented view switcher */}
          <div
            className="flex items-center shrink-0 px-4 gap-3"
            style={{
              height: 48,
              borderBottom: '1px solid var(--color-border)',
              background: 'color-mix(in srgb, var(--color-canvas) 85%, transparent)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <div
              className="flex items-center gap-0.5"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 10,
                padding: 3,
              }}
            >
              {([
                { id: 'chat', label: language === 'tr' ? 'Sohbet' : 'Chat', icon: <MessageSquare size={13} /> },
                { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={13} /> },
                { id: 'rag', label: language === 'tr' ? 'RAG Belleği' : 'RAG Memory', icon: <Brain size={13} /> },
                { id: 'settings', label: language === 'tr' ? 'Ayarlar' : 'Settings', icon: <Settings size={13} /> },
              ] as const).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="flex items-center gap-1.5 transition-all duration-150"
                  style={{
                    height: 28,
                    padding: '0 12px',
                    fontSize: 11.5,
                    fontFamily: 'var(--font-sans)',
                    fontWeight: activeTab === tab.id ? 600 : 500,
                    color: activeTab === tab.id ? 'var(--color-text)' : 'var(--color-muted)',
                    background: activeTab === tab.id ? 'var(--color-surface2)' : 'transparent',
                    border: 'none',
                    borderRadius: 7,
                    cursor: 'pointer',
                    boxShadow: activeTab === tab.id ? '0 1px 3px rgba(0,0,0,0.3)' : 'none',
                  }}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="flex-1" />

            {/* Stüdyo toggle — yalnız Sohbet görünümünde */}
            {activeTab === 'chat' && (
              <button
                onClick={() => setStudioMode(!studioMode)}
                className="flex items-center gap-1.5 transition-all duration-150"
                style={{
                  height: 28,
                  padding: '0 12px',
                  fontSize: 11.5,
                  fontFamily: 'var(--font-sans)',
                  fontWeight: studioMode ? 600 : 500,
                  color: studioMode ? 'var(--color-accent-fg)' : 'var(--color-muted)',
                  background: studioMode ? 'var(--color-accent-subtle)' : 'transparent',
                  border: '1px solid ' + (studioMode ? 'rgba(201,100,66,0.3)' : 'var(--color-border)'),
                  borderRadius: 8,
                  cursor: 'pointer',
                }}
                title={language === 'tr'
                  ? (studioMode ? 'Stüdyoyu kapat — tek kolon sohbet' : 'Stüdyoyu aç — sonuç yan panelde')
                  : (studioMode ? 'Close studio' : 'Open studio panel')}
              >
                ◫ {language === 'tr' ? 'Stüdyo' : 'Studio'}
              </button>
            )}

            {/* Dil ve tema düğmeleri */}
            <button
              onClick={toggleTheme}
              className="flex items-center justify-center transition-all duration-150 hover:bg-[var(--color-surface2)] hover:text-[var(--color-text)]"
              style={{
                width: 28, height: 28, borderRadius: 8,
                background: 'transparent', border: '1px solid var(--color-border)',
                color: 'var(--color-muted)', cursor: 'pointer',
              }}
              title={isDark ? (language === 'tr' ? 'Aydınlık Mod' : 'Light Mode') : (language === 'tr' ? 'Karanlık Mod' : 'Dark Mode')}
            >
              {isDark ? <Sun size={13} /> : <Moon size={13} />}
            </button>
            <button
              onClick={() => {
                const next = language === 'tr' ? 'en' : 'tr';
                useBIStore.getState().setLanguage(next);
              }}
              className="transition-all duration-150 hover:bg-[var(--color-surface2)] hover:text-[var(--color-text)]"
              style={{
                height: 28, padding: '0 8px', borderRadius: 8,
                background: 'transparent', border: '1px solid var(--color-border)',
                color: 'var(--color-muted)', cursor: 'pointer',
                fontSize: 10, fontWeight: 600, fontFamily: 'var(--font-mono)',
              }}
              title={language === 'tr' ? 'Switch to English' : "Türkçe'ye Geç"}
            >
              {language.toUpperCase()}
            </button>

            <button
              onClick={() => setShowCommandHelp(true)}
              className="flex items-center gap-1.5 transition-all duration-150 hover:brightness-125"
              style={{
                height: 28, padding: '0 10px', fontSize: 10.5,
                fontFamily: 'var(--font-mono)', fontWeight: 600,
                background: 'var(--color-accent-subtle)',
                border: '1px solid rgba(99,102,241,0.25)',
                borderRadius: 8, color: 'var(--color-accent-fg)', cursor: 'pointer',
              }}
              title={language === 'tr' ? 'Komut listesini göster' : 'Show command list'}
            >
              ⌘ {language === 'tr' ? 'Komutlar' : 'Commands'}
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 flex overflow-hidden">
            {activeTab === 'chat' && (
              studioMode && !visualizerDismissed ? (
                <div ref={splitContainerRef} className="w-full h-full flex overflow-hidden">
                  <div
                    className="h-full flex flex-col min-w-[320px] transition-all duration-200 ease-in-out"
                    style={{ flexBasis: `${splitRatio * 100}%` }}
                  >
                    <ChatConsole />
                  </div>
                  <div
                    className="splitter"
                    role="separator"
                    aria-orientation="vertical"
                    onPointerDown={handleSplitterDown}
                  />
                  <div className="flex-grow h-full flex flex-col min-w-[360px]">
                    <ResultVisualizer />
                  </div>
                </div>
              ) : (
                <div className="w-full h-full flex flex-col overflow-hidden">
                  <ChatConsole />
                </div>
              )
            )}
            {activeTab === 'dashboard' && (
              <Suspense fallback={<Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%' }}><CircularProgress size={28} /></Box>}>
                <Dashboard />
              </Suspense>
            )}
            {activeTab === 'rag' && (
              <Suspense fallback={<Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%' }}><CircularProgress size={28} /></Box>}>
                <RAGMemoryPanel />
              </Suspense>
            )}
            {activeTab === 'settings' && (
              <Suspense fallback={<Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%' }}><CircularProgress size={28} /></Box>}>
                <SettingsPage />
              </Suspense>
            )}
          </div>
        </main>

        {/* Command Help Modal */}
        {showCommandHelp && (
          <Suspense fallback={null}>
            <CommandHelpModal open={showCommandHelp} onClose={() => setShowCommandHelp(false)} language={language} />
          </Suspense>
        )}

        {/* Quick-access Data Sources Modal */}
        <Dialog
          open={showSources}
          onClose={() => {
            setShowSources(false);
            fetchSources();
            fetchFiles();
          }}
          maxWidth="lg"
          fullWidth
          aria-labelledby="sources-dialog-title"
          scroll="paper"
        >
          <DialogTitle
            id="sources-dialog-title"
            sx={{
              p: 0, px: 2.5,
              borderBottom: '1px solid',
              borderColor: 'divider',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              minHeight: 52,
              bgcolor: 'transparent',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{
                width: 32, height: 32, borderRadius: '8px',
                bgcolor: 'var(--color-accent-subtle)',
                border: '1px solid rgba(99, 102, 241, 0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--color-accent-fg)'
              }}>
                <HardDrive size={16} />
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: 13, m: 0, letterSpacing: '-0.01em' }}>
                  {language === 'tr' ? 'Veri Kaynakları' : 'Data Sources'}
                </Typography>
                <Typography variant="caption" sx={{ fontSize: 10, color: 'text.secondary' }}>
                  {language === 'tr' ? 'DeepBI Birleşik Veri Merkezi' : 'DeepBI Unified Data Hub'}
                </Typography>
              </Box>
            </Box>
            <IconButton
              onClick={() => {
                setShowSources(false);
                fetchSources();
                fetchFiles();
              }}
              size="small"
              sx={{ color: 'text.secondary', borderRadius: '8px' }}
            >
              <X size={15} />
            </IconButton>
          </DialogTitle>

          <DialogContent sx={{ p: 0, bgcolor: isDark ? '#0f0f12' : '#fafafa', maxHeight: '80vh' }}>
            <Suspense fallback={<Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 8 }}><CircularProgress size={32} /></Box>}>
              <SourceManager />
            </Suspense>
          </DialogContent>
        </Dialog>

      </div>
    </ThemeProvider>
  );
};

export default App;
