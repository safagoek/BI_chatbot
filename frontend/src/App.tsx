import React, { useEffect, useRef, useState } from 'react';
import { useBIStore } from './context/store';
import { translations } from './context/translations';
import Sidebar from './components/Sidebar';
import ChatConsole from './components/ChatConsole';
import ResultVisualizer from './components/ResultVisualizer';
import SourceManager from './components/SourceManager';
import { Settings, Key, HardDrive, X, Eye, EyeOff } from 'lucide-react';
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

  // Dedicated overlay dialogs
  const [showSettings, setShowSettings] = useState(false);
  const [showSources, setShowSources] = useState(false);

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
      if (saved === 'light') return 'light';
      return 'dark'; // Default to premium dark theme
    }
    return 'dark';
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

  // Build the Material UI custom theme synchronized with our active variables
  const muiTheme = React.useMemo(() => {
    return createTheme({
      palette: {
        mode: theme,
        primary: {
          main: '#1a73e8', // Google Blue
        },
        background: {
          default: theme === 'dark' ? '#121212' : '#f8f9fa',
          paper: theme === 'dark' ? '#1e1e1e' : '#ffffff',
        },
        text: {
          primary: theme === 'dark' ? '#e8eaed' : '#202124',
          secondary: theme === 'dark' ? '#9aa0a6' : '#5f6368',
        },
        divider: theme === 'dark' ? '#3c4043' : '#dadce0',
      },
      typography: {
        fontFamily: "'Outfit', 'Roboto', 'Segoe UI', sans-serif",
        fontSize: 13,
        button: {
          textTransform: 'none',
          fontWeight: 600,
        },
      },
      shape: {
        borderRadius: 8,
      },
      components: {
        MuiDialog: {
          styleOverrides: {
            paper: {
              backgroundImage: 'none', // Remove default linear overlay
              border: `1px solid ${theme === 'dark' ? '#3c4043' : '#dadce0'}`,
              boxShadow: theme === 'dark' ? '0 12px 40px rgba(0,0,0,0.6)' : '0 8px 30px rgba(0,0,0,0.1)',
            }
          }
        },
        MuiCard: {
          styleOverrides: {
            root: {
              border: `1px solid ${theme === 'dark' ? '#3c4043' : '#dadce0'}`,
              backgroundImage: 'none',
              boxShadow: 'none',
            }
          }
        },
        MuiTextField: {
          defaultProps: {
            size: 'small',
          }
        },
        MuiButton: {
          styleOverrides: {
            root: {
              borderRadius: 6,
              padding: '6px 16px',
            }
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
        <main className="flex-1 h-full flex overflow-hidden">
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
        </main>

        {/* ── 3. Dedicated LLM Settings Modal (Google Material UI Redesigned) ── */}
        <Dialog
          open={showSettings}
          onClose={() => setShowSettings(false)}
          maxWidth="md"
          fullWidth
          aria-labelledby="settings-dialog-title"
        >
          {/* Header */}
          <DialogTitle
            id="settings-dialog-title"
            sx={{
              p: 2.5,
              borderBottom: '1px solid',
              borderColor: 'divider',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              bgcolor: theme === 'dark' ? 'rgba(26, 115, 232, 0.05)' : 'rgba(26, 115, 232, 0.02)'
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, selectNone: 'none' }}>
              <Box sx={{ width: 36, height: 36, borderRadius: '8px', bgcolor: 'rgba(26, 115, 232, 0.1)', border: '1px solid rgba(26, 115, 232, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a73e8' }}>
                <Settings size={18} />
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 800, fontSize: 13, textTransform: 'uppercase', tracking: '-0.01em', m: 0 }}>
                  {t.llmSettingsTitle}
                </Typography>
                <Typography variant="caption" sx={{ fontSize: 9, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', fontWeight: 'bold' }}>
                  {t.llmSettingsSubtitle}
                </Typography>
              </Box>
            </Box>
            <IconButton onClick={() => setShowSettings(false)} size="small" sx={{ color: 'text.secondary' }}>
              <X size={15} />
            </IconButton>
          </DialogTitle>

          <DialogContent sx={{ p: 0, display: 'flex', minHeight: 480, height: 480, overflow: 'hidden' }}>
            {/* Left Pane - Preset Provider Cards */}
            <Box sx={{ width: '40%', borderRight: '1px solid', borderColor: 'divider', bgcolor: theme === 'dark' ? 'rgba(26, 115, 232, 0.02)' : 'rgba(26, 115, 232, 0.01)', p: 3, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em' }}>
                {t.engineSelection}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {presets.map((p) => {
                  const isActivePreset = selectedPreset === p.value;
                  return (
                    <Card
                      key={p.id}
                      onClick={() => handlePresetChange(p.value)}
                      sx={{
                        cursor: 'pointer',
                        borderColor: isActivePreset ? '#1a73e8' : 'divider',
                        bgcolor: isActivePreset ? 'rgba(26, 115, 232, 0.08)' : 'background.paper',
                        boxShadow: isActivePreset ? '0 0 12px rgba(26, 115, 232, 0.15)' : 'none',
                        transition: 'all 0.2s',
                        borderRadius: '10px',
                        '&:hover': {
                          bgcolor: isActivePreset ? 'rgba(26, 115, 232, 0.12)' : 'action.hover',
                        }
                      }}
                    >
                      <CardActionArea sx={{ p: 2, display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                        <Typography sx={{ fontSize: 13, color: '#1a73e8', mt: 0.2, userSelect: 'none' }}>{p.icon}</Typography>
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', userSelect: 'none' }}>
                            <Typography variant="body2" sx={{ fontWeight: 'bold', fontSize: 11.5 }}>
                              {p.label}
                            </Typography>
                            {isActivePreset && (
                              <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'success.main' }} />
                            )}
                          </Box>
                          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: 9.5, mt: 0.5, display: 'block', lineHeight: 1.3 }}>
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
                  <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Key size={11} style={{ color: '#1a73e8' }} />
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

                <Box sx={{ pt: 2, display: 'flex', gap: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
                  <Button
                    onClick={handleTestConnection}
                    disabled={isTesting || !baseUrl}
                    variant="outlined"
                    sx={{ flex: 1, fontSize: 11, color: 'text.primary', borderColor: 'divider', borderRadius: '8px', py: 1 }}
                  >
                    {isTesting ? <CircularProgress size={14} color="inherit" /> : t.testBtn}
                  </Button>
                  <Button
                    onClick={() => setShowSettings(false)}
                    variant="outlined"
                    sx={{ flex: 1, fontSize: 11, color: 'text.primary', borderColor: 'divider', borderRadius: '8px', py: 1 }}
                  >
                    {t.closeBtn}
                  </Button>
                  <Button
                    type="submit"
                    variant="contained"
                    sx={{
                      flex: 2, fontSize: 11, bgcolor: '#1a73e8', '&:hover': { bgcolor: '#1557b0' },
                      fontWeight: 'bold', color: '#ffffff', borderRadius: '8px', py: 1
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
          {/* Header */}
          <DialogTitle
            id="sources-dialog-title"
            sx={{
              p: 2.5,
              borderBottom: '1px solid',
              borderColor: 'divider',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              bgcolor: theme === 'dark' ? 'rgba(26, 115, 232, 0.05)' : 'rgba(26, 115, 232, 0.02)'
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, selectNone: 'none' }}>
              <Box sx={{ width: 36, height: 36, borderRadius: '8px', bgcolor: 'rgba(26, 115, 232, 0.1)', border: '1px solid rgba(26, 115, 232, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#1a73e8' }}>
                <HardDrive size={18} />
              </Box>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 800, fontSize: 13, textTransform: 'uppercase', tracking: '-0.01em', m: 0 }}>
                  {language === 'tr' ? 'Veri Kaynağı Kurulum & Kontrol Paneli' : 'Data Source Config & Control Panel'}
                </Typography>
                <Typography variant="caption" sx={{ fontSize: 9, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', fontWeight: 'bold' }}>
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
              sx={{ color: 'text.secondary' }}
            >
              <X size={15} />
            </IconButton>
          </DialogTitle>

          <DialogContent sx={{ p: 0, bgcolor: theme === 'dark' ? 'rgba(18, 18, 18, 0.95)' : 'rgba(255, 255, 255, 0.95)', maxH: '80vh' }}>
            <SourceManager />
          </DialogContent>
        </Dialog>

      </div>
    </ThemeProvider>
  );
};

export default App;
