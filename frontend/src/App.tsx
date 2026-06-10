import React, { useEffect, useRef, useState } from 'react';
import { useBIStore } from './context/store';
import { translations } from './context/translations';
import Sidebar from './components/Sidebar';
import ChatConsole from './components/ChatConsole';
import ResultVisualizer from './components/ResultVisualizer';
import SourceManager from './components/SourceManager';
import Dashboard from './components/Dashboard';
import RAGMemoryPanel from './components/RAGMemoryPanel';
import CommandHelpModal from './components/CommandHelpModal';
import { Settings, Key, HardDrive, X, Eye, EyeOff, LayoutDashboard, Brain, MessageSquare } from 'lucide-react';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import {
  Dialog, DialogTitle, DialogContent, Alert, TextField, Button, Box,
  Card, CardActionArea, Typography, IconButton, InputAdornment, CircularProgress
} from '@mui/material';

export const App: React.FC = () => {
  const { apiConfig, setApiConfig, fetchSources, fetchFiles, language, visualizerDismissed } = useBIStore();
  const t = translations[language];

  const [splitRatio, setSplitRatio] = useState(0.42);
  const splitContainerRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);

  // Active main view tab
  const [activeTab, setActiveTab] = useState<'chat' | 'dashboard' | 'rag'>('chat');

  // Dedicated overlay dialogs
  const [showSettings, setShowSettings] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [showCommandHelp, setShowCommandHelp] = useState(false);

  // Settings form states
  const [apiKey, setApiKey] = useState(apiConfig.apiKey);
  const [baseUrl, setBaseUrl] = useState(apiConfig.baseUrl);
  const [model, setModel] = useState(apiConfig.model);
  const [saveOk, setSaveOk] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Parent-level theme management
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('theme');
      if (saved === 'dark') return 'dark';
      return 'light'; // Default to premium light theme (Nordic Minimalist)
    }
    return 'light';
  });

  useEffect(() => {
    setApiKey(apiConfig.apiKey);
    setBaseUrl(apiConfig.baseUrl);
    setModel(apiConfig.model);
  }, [apiConfig]);

  useEffect(() => {
    const html = document.documentElement;
    if (theme === 'dark') {
      html.classList.add('dark');
      html.classList.remove('light');
    } else {
      html.classList.add('light');
      html.classList.remove('dark');
    }
  }, [theme]);

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('theme', next);
  };

  const presets = [
    {
      id: 'openai',
      label: language === 'tr' ? 'OpenAI Resmi API' : 'Official OpenAI API',
      value: 'https://api.openai.com/v1',
      defaultModel: 'gpt-4o',
      desc: language === 'tr' ? 'Kurumsal bulut altyapısı ve stabil model servisi' : 'Enterprise cloud infrastructure and stable model service',
      icon: '◼'
    },
    {
      id: 'openrouter',
      label: 'OpenRouter Gateway',
      value: 'https://openrouter.ai/api/v1',
      defaultModel: 'google/gemini-2.5-flash',
      desc: language === 'tr' ? 'Çoklu model geçidi ve pratik rotalama' : 'Multi-model gateway and convenient routing',
      icon: '◼'
    },
    {
      id: 'lmstudio',
      label: 'LM Studio (Local)',
      value: 'http://localhost:1234/v1',
      defaultModel: 'local-model',
      desc: language === 'tr' ? 'Çevrimdışı çalışır, veri çıkışı olmaz' : 'Runs offline, no data leaves your machine',
      icon: '◻'
    },
    {
      id: 'ollama',
      label: 'Ollama (Local)',
      value: 'http://localhost:11434/v1',
      defaultModel: 'llama3',
      desc: language === 'tr' ? 'Local model orkestrasyonu ve hızlı deneme modu' : 'Local model orchestration and fast prototyping mode',
      icon: '◻'
    },
    {
      id: 'custom',
      label: language === 'tr' ? 'Özel Base URL' : 'Custom Base URL',
      value: 'custom',
      defaultModel: 'gpt-4o',
      desc: language === 'tr' ? 'Manuel URL girişi (ör: https://openrouter.ai/api/v1)' : 'Manual URL input (e.g. https://openrouter.ai/api/v1)',
      icon: '◻'
    }
  ];

  const [selectedPreset, setSelectedPreset] = useState(() => {
    const matched = presets.find(p => p.value === apiConfig.baseUrl);
    return matched ? matched.value : 'custom';
  });

  const [customUrl, setCustomUrl] = useState(() => {
    const matched = presets.find(p => p.value === apiConfig.baseUrl);
    return matched ? '' : apiConfig.baseUrl;
  });

  const handlePresetChange = (val: string) => {
    setSelectedPreset(val);
    if (val === 'custom') {
      setBaseUrl(customUrl || 'https://');
      return;
    }
    setBaseUrl(val);
    const matched = presets.find(p => p.value === val);
    if (matched) {
      setModel(matched.defaultModel);
    }
  };

  const handleBaseUrlChange = (val: string) => {
    setCustomUrl(val);
    setBaseUrl(val);
    setSelectedPreset('custom');
  };

  const isLocalPreset = baseUrl.startsWith('http://localhost');

  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [testMessage, setTestMessage] = useState('');

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestStatus('idle');
    setTestMessage('');
    try {
      const cleanBase = baseUrl.replace(/\/+$/, '');
      const testUrl = `${cleanBase}/models`;
      const headers: Record<string, string> = {};
      if (apiKey && !isLocalPreset) {
        headers.Authorization = `Bearer ${apiKey}`;
      }

      const res = await fetch(testUrl, { method: 'GET', headers });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setTestStatus('ok');
      setTestMessage(t.testSuccess);
    } catch (err: any) {
      const msg = err?.message || t.testFailed;
      setTestStatus('error');
      setTestMessage(msg.includes('Failed to fetch') ? (language === 'tr' ? 'Bağlantı başarısız (CORS veya URL hatası).' : 'Connection failed (CORS or URL error).') : msg);
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveSettings = () => {
    setApiConfig({ apiKey, baseUrl, model });
    setSaveOk(true);
    setTimeout(() => {
      setSaveOk(false);
      setShowSettings(false);
    }, 1200);
  };

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

  // Build the Material UI custom theme synchronized with Fluent Design 2 tokens
  const muiTheme = React.useMemo(() => {
    const isDark = theme === 'dark';
    return createTheme({
      palette: {
        mode: theme,
        primary: {
          main: '#0078d4',          // Fluent Communication Blue
          light: '#60cdff',
          dark: '#005a9e',
          contrastText: '#ffffff',
        },
        background: {
          default: isDark ? '#141414' : '#f3f2f1',  // Fluent Ground
          paper:   isDark ? '#1c1c1c' : '#ffffff',  // Fluent Layer
        },
        text: {
          primary:   isDark ? '#ffffff' : '#201f1e',
          secondary: isDark ? 'rgba(255,255,255,0.7844)' : 'rgba(32,31,30,0.7827)',
        },
        divider: isDark ? 'rgba(255,255,255,0.0837)' : 'rgba(0,0,0,0.0824)',
        error:   { main: isDark ? '#d13438' : '#a4262c' },
        success: { main: isDark ? '#54b054' : '#107c10' },
        warning: { main: isDark ? '#ffb900' : '#986f0b' },
      },
      typography: {
        fontFamily: "'Plus Jakarta Sans', 'Outfit', 'Inter', system-ui, -apple-system, sans-serif",
        fontSize: 13,
        button: {
          textTransform: 'none',    // Fluent: Sentence case
          fontWeight: 600,
          letterSpacing: 0,
        },
      },
      shape: {
        borderRadius: 4,            // Fluent: Small radius (4px base)
      },
      components: {
        MuiDialog: {
          styleOverrides: {
            paper: {
              backgroundImage: 'none',
              backgroundColor: isDark ? '#1c1c1c' : '#ffffff',
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.0837)' : 'rgba(0,0,0,0.0824)'}`,
              boxShadow: isDark
                ? '0 28px 56px rgba(0,0,0,0.58), 0 0px 4px rgba(0,0,0,0.14)'
                : '0 16px 32px rgba(0,0,0,0.14), 0 0px 2px rgba(0,0,0,0.06)',
              borderRadius: 8,
            }
          }
        },
        MuiCard: {
          styleOverrides: {
            root: {
              backgroundImage: 'none',
              backgroundColor: isDark ? '#242424' : '#ffffff',
              border: `1px solid ${isDark ? 'rgba(255,255,255,0.0837)' : 'rgba(0,0,0,0.0824)'}`,
              boxShadow: '0 2px 4px rgba(0,0,0,0.14)',
              borderRadius: 8,
            }
          }
        },
        MuiTextField: {
          defaultProps: { size: 'small' },
          styleOverrides: {
            root: {
              '& .MuiOutlinedInput-root': {
                borderRadius: 4,
                backgroundColor: isDark ? '#242424' : '#f5f5f5',
                '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#0078d4',
                  borderWidth: '1px',
                },
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: isDark ? 'rgba(255,255,255,0.0837)' : 'rgba(0,0,0,0.0824)',
                }
              }
            }
          }
        },
        MuiButton: {
          styleOverrides: {
            root: {
              borderRadius: 4,
              padding: '6px 16px',
              boxShadow: 'none',
              '&:hover': { boxShadow: 'none' },
            },
            contained: {
              '&:hover': {
                backgroundColor: '#106ebe',
              }
            }
          }
        },
        MuiAlert: {
          styleOverrides: {
            root: { borderRadius: 4 }
          }
        }
      }
    });
  }, [theme]);

  return (
    <ThemeProvider theme={muiTheme}>
      <div className="w-screen h-screen flex bg-gh-bg text-gh-text overflow-hidden relative">
        
        {/* 1. Global Navigation Sidebar */}
        <Sidebar 
          onOpenSettings={() => setShowSettings(true)} 
          onOpenSources={() => setShowSources(true)} 
          theme={theme}
          onToggleTheme={toggleTheme}
        />

        {/* 2. Main Content Viewport */}
        <main className="flex-1 h-full flex flex-col overflow-hidden">
          {/* Tab Bar */}
          <div
            className="flex items-center shrink-0 px-4 gap-1"
            style={{ height: 44, borderBottom: '1px solid var(--color-border)', background: 'var(--color-canvas)' }}
          >
            {([
              { id: 'chat', label: language === 'tr' ? 'Sohbet' : 'Chat', icon: <MessageSquare size={13} /> },
              { id: 'dashboard', label: language === 'tr' ? 'Dashboard' : 'Dashboard', icon: <LayoutDashboard size={13} /> },
              { id: 'rag', label: language === 'tr' ? 'RAG Belleği' : 'RAG Memory', icon: <Brain size={13} /> },
            ] as const).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="flex items-center gap-1.5 cursor-pointer transition-all duration-150"
                style={{
                  height: 44,
                  padding: '0 14px',
                  fontSize: 11.5,
                  fontFamily: 'var(--font-sans)',
                  fontWeight: activeTab === tab.id ? 700 : 500,
                  color: activeTab === tab.id ? 'var(--color-text)' : 'var(--color-muted)',
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === tab.id ? '2px solid #6366f1' : '2px solid transparent',
                  cursor: 'pointer',
                }}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
            <div className="flex-1" />
            <button
              onClick={() => setShowCommandHelp(true)}
              className="flex items-center gap-1.5 cursor-pointer transition-all duration-150 hover:text-indigo-400"
              style={{
                height: 28, padding: '0 10px', fontSize: 10.5,
                fontFamily: 'var(--font-mono)', fontWeight: 600,
                background: 'rgba(99,102,241,0.08)',
                border: '1px solid rgba(99,102,241,0.2)',
                borderRadius: 6, color: '#818cf8', cursor: 'pointer',
              }}
              title={language === 'tr' ? 'Komut listesini göster' : 'Show command list'}
            >
              ⌨️ {language === 'tr' ? 'Komutlar' : 'Commands'}
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 flex overflow-hidden">
            {activeTab === 'chat' && (
              <div ref={splitContainerRef} className="w-full h-full flex overflow-hidden">
                <div
                  className="h-full flex flex-col min-w-[320px] transition-all duration-200 ease-in-out"
                  style={{ flexBasis: visualizerDismissed ? '100%' : `${splitRatio * 100}%` }}
                >
                  <ChatConsole />
                </div>
                {!visualizerDismissed && (
                  <>
                    <div
                      className="splitter"
                      role="separator"
                      aria-orientation="vertical"
                      onPointerDown={handleSplitterDown}
                    />
                    <div className="flex-grow h-full flex flex-col min-w-[360px]">
                      <ResultVisualizer />
                    </div>
                  </>
                )}
              </div>
            )}
            {activeTab === 'dashboard' && <Dashboard />}
            {activeTab === 'rag' && <RAGMemoryPanel />}
          </div>
        </main>

        {/* Command Help Modal */}
        <CommandHelpModal open={showCommandHelp} onClose={() => setShowCommandHelp(false)} language={language} />

        {/* ── 3. Dedicated LLM Settings Modal (Google Material UI Redesigned) ── */}
        <Dialog
          open={showSettings}
          onClose={() => setShowSettings(false)}
          maxWidth="md"
          fullWidth
          aria-labelledby="settings-dialog-title"
        >
          {/* Fluent Command Bar Header */}
          <DialogTitle
            id="settings-dialog-title"
            sx={{
              p: 0,
              borderBottom: '1px solid',
              borderColor: 'divider',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              minHeight: 48,
              px: 2.5,
              bgcolor: theme === 'dark' ? '#1c1c1c' : '#ffffff',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{
                width: 32, height: 32, borderRadius: '4px',
                bgcolor: 'rgba(0, 120, 212, 0.1)',
                border: '1px solid rgba(0, 120, 212, 0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#0078d4'
              }}>
                <Settings size={16} />
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: 13, m: 0, letterSpacing: '-0.01em' }}>
                  {t.llmSettingsTitle}
                </Typography>
                <Typography variant="caption" sx={{ fontSize: 10, color: 'text.secondary', letterSpacing: 0 }}>
                  {t.llmSettingsSubtitle}
                </Typography>
              </Box>
            </Box>
            <IconButton onClick={() => setShowSettings(false)} size="small" sx={{ color: 'text.secondary', borderRadius: '4px' }}>
              <X size={15} />
            </IconButton>
          </DialogTitle>

          <DialogContent sx={{ p: 0, display: 'flex', minHeight: 480, height: 480, overflow: 'hidden' }}>
            {/* Left Pane - Fluent Provider Selection */}
            <Box sx={{ width: '40%', borderRight: '1px solid', borderColor: 'divider', bgcolor: theme === 'dark' ? '#141414' : '#f3f2f1', p: 2.5, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em' }}>
                {t.engineSelection}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {presets.map((p) => {
                  const isActivePreset = selectedPreset === p.value;
                  return (
                    <Card
                      key={p.id}
                      onClick={() => handlePresetChange(p.value)}
                      sx={{
                        cursor: 'pointer',
                        borderColor: isActivePreset ? '#0078d4' : 'divider',
                        bgcolor: isActivePreset
                          ? 'rgba(0, 120, 212, 0.1)'
                          : (theme === 'dark' ? '#242424' : '#ffffff'),
                        boxShadow: isActivePreset ? '0 2px 4px rgba(0,0,0,0.18)' : 'none',
                        transition: 'all 0.1s cubic-bezier(0.1, 0.9, 0.2, 1)',
                        borderRadius: '4px',
                        borderWidth: isActivePreset ? '1.5px' : '1px',
                        '&:hover': {
                          bgcolor: isActivePreset
                            ? 'rgba(0, 120, 212, 0.14)'
                            : (theme === 'dark' ? '#2c2c2c' : '#f5f5f5'),
                          borderColor: isActivePreset ? '#0078d4' : 'rgba(0,120,212,0.2)',
                        }
                      }}
                    >
                      <CardActionArea sx={{ p: 1.5, display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                        <Typography sx={{ fontSize: 12, color: '#0078d4', mt: 0.2, userSelect: 'none' }}>{p.icon}</Typography>
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', userSelect: 'none' }}>
                            <Typography variant="body2" sx={{ fontWeight: 600, fontSize: 11.5, letterSpacing: 0 }}>
                              {p.label}
                            </Typography>
                            {isActivePreset && (
                              <Box sx={{ width: 7, height: 7, borderRadius: '2px', bgcolor: '#0078d4' }} />
                            )}
                          </Box>
                          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: 9.5, mt: 0.3, display: 'block', lineHeight: 1.4 }}>
                            {p.desc}
                          </Typography>
                        </Box>
                      </CardActionArea>
                    </Card>
                  );
                })}
              </Box>
            </Box>

            {/* Right Pane - Endpoint Details Form */}
            <Box sx={{ flex: 1, p: 4, overflowY: 'auto' }}>
              <Box component="form" onSubmit={(e) => { e.preventDefault(); handleSaveSettings(); }} sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, maxWidth: 440 }}>
                <Box>
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold', fontSize: 12, textTransform: 'uppercase', tracking: '0.05em', color: 'text.primary', mb: 0.5 }}>
                    {t.presetsTitle}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: 10.5 }}>
                    {t.presetsSubtitle}
                  </Typography>
                </Box>

                <Box sx={{ height: '1px', bgcolor: 'divider' }} />

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                    {t.baseUrlLabel}
                  </Typography>
                  <TextField
                    fullWidth
                    variant="outlined"
                    value={baseUrl}
                    onChange={e => handleBaseUrlChange(e.target.value)}
                    placeholder="https://openrouter.ai/api/v1"
                    slotProps={{
                      htmlInput: {
                        style: { fontFamily: 'monospace', fontSize: 12 }
                      }
                    }}
                    sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                  />
                  <Typography variant="caption" sx={{ fontSize: 9, color: 'text.secondary', mt: 0.5 }}>
                    {t.baseUrlDesc}
                  </Typography>
                </Box>

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', mb: 0.5, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Key size={11} style={{ color: '#0078d4' }} />
                    {t.apiKeyLabel}
                  </Typography>
                  <TextField
                    fullWidth
                    variant="outlined"
                    type={showPassword ? 'text' : 'password'}
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder={isLocalPreset ? t.apiKeyDescLocal : 'sk-...'}
                    disabled={isLocalPreset}
                    slotProps={{
                      htmlInput: {
                        style: { fontFamily: 'monospace', fontSize: 12 }
                      },
                      input: {
                        endAdornment: (
                           <InputAdornment position="end">
                            <IconButton onClick={() => setShowPassword(!showPassword)} size="small" disabled={isLocalPreset}>
                              {showPassword ? <EyeOff size={13} /> : <Eye size={13} />}
                            </IconButton>
                          </InputAdornment>
                        )
                      }
                    }}
                    sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                  />
                  <Typography variant="caption" sx={{ fontSize: 9, color: 'text.secondary', mt: 0.5 }}>
                    {isLocalPreset ? t.apiKeyDescLocal : t.apiKeyDescCloud}
                  </Typography>
                </Box>

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                    {t.modelLabel}
                  </Typography>
                  <TextField
                    fullWidth
                    variant="outlined"
                    required
                    value={model}
                    onChange={e => setModel(e.target.value)}
                    placeholder="deepseek-coder veya gpt-4o"
                    slotProps={{
                      htmlInput: {
                        style: { fontFamily: 'monospace', fontSize: 12 }
                      }
                    }}
                    sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                  />
                  <Typography variant="caption" sx={{ fontSize: 9, color: 'text.secondary', mt: 0.5 }}>
                    {t.modelDesc}
                  </Typography>
                </Box>

                <Box sx={{ pt: 2, display: 'flex', gap: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                  <Button
                    onClick={handleTestConnection}
                    disabled={isTesting || !baseUrl}
                    variant="outlined"
                    sx={{ flex: 1, fontSize: 11, borderRadius: '4px', py: 0.8, borderColor: 'divider', color: 'text.primary' }}
                  >
                    {isTesting ? <CircularProgress size={13} color="inherit" /> : t.testBtn}
                  </Button>
                  <Button
                    onClick={() => setShowSettings(false)}
                    variant="outlined"
                    sx={{ flex: 1, fontSize: 11, borderRadius: '4px', py: 0.8, borderColor: 'divider', color: 'text.primary' }}
                  >
                    {t.closeBtn}
                  </Button>
                  <Button
                    type="submit"
                    variant="contained"
                    sx={{
                      flex: 2, fontSize: 11,
                      bgcolor: '#0078d4',
                      '&:hover': { bgcolor: '#106ebe' },
                      '&:active': { bgcolor: '#005a9e' },
                      fontWeight: 600, color: '#ffffff',
                      borderRadius: '4px', py: 0.8
                    }}
                  >
                    {saveOk ? t.savedBtn : t.applyBtn}
                  </Button>
                </Box>

                {testStatus !== 'idle' && (
                  <Alert severity={testStatus === 'ok' ? 'success' : 'error'} sx={{ fontSize: 10.5, borderRadius: '8px', py: 0.5 }}>
                    {testMessage}
                  </Alert>
                )}
              </Box>
            </Box>
          </DialogContent>
        </Dialog>

        {/* ── 4. Fullscreen Data Sources Modal (Google Material UI Redesigned) ── */}
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
          {/* Fluent Command Bar Header */}
          <DialogTitle
            id="sources-dialog-title"
            sx={{
              p: 0, px: 2.5,
              borderBottom: '1px solid',
              borderColor: 'divider',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              minHeight: 48,
              bgcolor: theme === 'dark' ? '#1c1c1c' : '#ffffff',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{
                width: 32, height: 32, borderRadius: '4px',
                bgcolor: 'rgba(0, 120, 212, 0.1)',
                border: '1px solid rgba(0, 120, 212, 0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#0078d4'
              }}>
                <HardDrive size={16} />
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: 13, m: 0, letterSpacing: '-0.01em' }}>
                  {language === 'tr' ? 'Veri Kaynakları' : 'Data Sources'}
                </Typography>
                <Typography variant="caption" sx={{ fontSize: 10, color: 'text.secondary', letterSpacing: 0 }}>
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
              sx={{ color: 'text.secondary', borderRadius: '4px' }}
            >
              <X size={15} />
            </IconButton>
          </DialogTitle>

          <DialogContent sx={{ p: 0, bgcolor: theme === 'dark' ? '#141414' : '#f3f2f1', maxH: '80vh' }}>
            <SourceManager />
          </DialogContent>
        </Dialog>

      </div>
    </ThemeProvider>
  );
};

export default App;
