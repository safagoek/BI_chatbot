import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useBIStore, BACKEND_BASE } from '../context/store';
import { translations } from '../context/translations';
import {
  Table as TableIcon, BarChart2, Search as SearchIcon, ChevronLeft, ChevronRight, Eye,
  ChevronDown, ChevronUp, FileDown, X, Sparkles
} from 'lucide-react';

import {
  Box, Typography, Paper, IconButton, Tooltip,
  ToggleButtonGroup, ToggleButton, Select, MenuItem, FormControl,
  TextField, InputAdornment, TableContainer, Table, TableHead, TableRow, TableCell,
  TableBody, Chip, Button
} from '@mui/material';

declare global {
  interface Window { Plotly?: any; }
}

const CHART_COLORS = [
  { hex: '#6366f1', name: 'Indigo Accent' },
  { hex: '#10b981', name: 'Emerald Success' },
  { hex: '#f59e0b', name: 'Amber Warning' },
  { hex: '#ef4444', name: 'Rose Danger' },
  { hex: '#8b5cf6', name: 'Violet Premium' },
];

export const ResultVisualizer: React.FC = () => {
  const { chatHistory, activeSessionId, language, activeMessageId, messageSelectionCount, setVisualizerDismissed } = useBIStore();
  const t = translations[language];

  // Get the most recent message with data
  const messagesWithData = chatHistory.filter(m => m.data || m.visualization || m.error);
  
  const activeMessage = useMemo(() => {
    if (activeMessageId) {
      const found = chatHistory.find(m => m.id === activeMessageId);
      if (found && (found.data || found.visualization || found.error)) {
        return found;
      }
    }
    return messagesWithData.length > 0 ? messagesWithData[messagesWithData.length - 1] : null;
  }, [chatHistory, activeMessageId, messagesWithData]);

  const data = activeMessage?.data;
  const visualization = activeMessage?.visualization;
  const columns = data?.columns || [];
  const rawRows = data?.rows || [];

  // Table state
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 50;

  // Chart state
  const [chartCollapsed, setChartCollapsed] = useState(false);
  const [chartType, setChartType] = useState<'Line' | 'Bar' | 'Scatter' | 'Area' | 'Pie'>('Bar');

  // Custom Grid Sorting & Checkbox Selection States (Suggestion 6)
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc' | 'none'>('none');
  const [selectedRows, setSelectedRows] = useState<any[][]>([]);
  const [xAxisCol, setXAxisCol] = useState('');
  const [yAxisCol, setYAxisCol] = useState('');

  const [themeColor, setThemeColor] = useState('#6366f1');
  const chartRef = useRef<HTMLDivElement>(null);

  // Resize states
  const [chartHeight, setChartHeight] = useState(280);
  const isResizingRef = useRef(false);

  useEffect(() => {
    const handlePointerMove = (e: PointerEvent) => {
      if (!isResizingRef.current || !chartRef.current) return;
      const rect = chartRef.current.getBoundingClientRect();
      const newHeight = e.clientY - rect.top;
      if (newHeight >= 140 && newHeight <= 800) {
        setChartHeight(newHeight);
      }
    };

    const handlePointerUp = () => {
      isResizingRef.current = false;
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);

    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, []);

  const startResize = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    isResizingRef.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  // Auto-resize Plotly when chartHeight changes
  useEffect(() => {
    if (window.Plotly && chartRef.current && !chartCollapsed) {
      try {
        window.Plotly.Plots.resize(chartRef.current);
      } catch (err) {
        console.error("Plotly resize error", err);
      }
    }
  }, [chartHeight, chartCollapsed]);

  // Dark mode tracking
  const [isDarkMode, setIsDarkMode] = useState(() =>
    typeof document !== 'undefined' ? document.documentElement.classList.contains('dark') : false
  );
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const obs = new MutationObserver(() =>
      setIsDarkMode(document.documentElement.classList.contains('dark'))
    );
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => obs.disconnect();
  }, []);

  // Reset on data / session change / explicit click selection
  useEffect(() => {
    setCurrentPage(1);
    setSearchTerm('');
    setChartCollapsed(false);
    setSelectedRows([]);
    setSortColumn(null);
    setSortDirection('none');
  }, [data, visualization, activeSessionId, activeMessageId, messageSelectionCount]);


  // Auto-detect axes and chart type from visualization hint
  useEffect(() => {
    if (!data || columns.length === 0) return;

    const firstCol = columns[0];
    const numericCols = columns.filter((_, idx) =>
      rawRows.some(row => {
        const v = row[idx];
        return v !== null && v !== undefined && !isNaN(Number(v)) && typeof v !== 'boolean';
      })
    );
    const firstNumeric = numericCols.find(c => c !== firstCol) || numericCols[0] || columns[1] || columns[0];

    let autoX = firstCol;
    let autoY = firstNumeric;
    let autoType: typeof chartType = 'Bar';
    let autoColor = themeColor;

    if (visualization?.data?.[0]) {
      const t = visualization.data[0];
      if (t.type === 'pie') autoType = 'Pie';
      else if (t.type === 'bar') autoType = 'Bar';
      else if (t.type === 'scatter') {
        autoType = t.fill ? 'Area' : t.mode === 'markers' ? 'Scatter' : 'Line';
      }
      if (t.x && Array.isArray(t.x)) {
        const xStr = JSON.stringify(t.x);
        const found = columns.find((_, ci) => JSON.stringify(rawRows.map(r => r[ci])) === xStr);
        if (found) autoX = found;
      }
      if (t.y && Array.isArray(t.y)) {
        const yStr = JSON.stringify(t.y);
        const found = columns.find((_, ci) => JSON.stringify(rawRows.map(r => r[ci])) === yStr);
        if (found) autoY = found;
      }
      const col = t.marker?.color || t.line?.color;
      if (typeof col === 'string' && col.startsWith('#')) autoColor = col;
    }

    setXAxisCol(autoX);
    setYAxisCol(autoY);
    setChartType(autoType);
    setThemeColor(autoColor);
  }, [data, visualization]);

  // Auto-detect numeric columns for perfect right alignment in tables
  const numericColsSet = useMemo(() => {
    if (!columns || !rawRows || rawRows.length === 0) return new Set<string>();
    const set = new Set<string>();
    columns.forEach((col, idx) => {
      const isNum = rawRows.every(row => {
        const val = row[idx];
        return val === null || val === undefined || val === '' || !isNaN(Number(val));
      });
      if (isNum) set.add(col);
    });
    return set;
  }, [columns, rawRows]);

  // Plotly render
  useEffect(() => {
    if (!visualization || chartCollapsed || !chartRef.current || !data || !xAxisCol || !yAxisCol || !window.Plotly) return;

    try {
      const xIdx = columns.indexOf(xAxisCol);
      const yIdx = columns.indexOf(yAxisCol);
      if (xIdx === -1 || yIdx === -1) return;

      const xValues = rawRows.map(r => r[xIdx]);
      const yValues = rawRows.map(r => {
        const v = r[yIdx];
        return v === null || v === undefined ? null : (Number(v) ?? v);
      });

      let trace: any = {};
      if (chartType === 'Line') {
        trace = { x: xValues, y: yValues, type: 'scatter', mode: 'lines+markers', line: { color: themeColor, width: 2.5 }, marker: { size: 5, color: themeColor }, name: yAxisCol };
      } else if (chartType === 'Bar') {
        trace = { x: xValues, y: yValues, type: 'bar', marker: { color: themeColor }, name: yAxisCol };
      } else if (chartType === 'Scatter') {
        trace = { x: xValues, y: yValues, type: 'scatter', mode: 'markers', marker: { size: 7, color: themeColor }, name: yAxisCol };
      } else if (chartType === 'Area') {
        trace = { x: xValues, y: yValues, type: 'scatter', mode: 'lines', fill: 'tozeroy', line: { color: themeColor, width: 2 }, fillcolor: themeColor + '22', name: yAxisCol };
      } else if (chartType === 'Pie') {
        trace = {
          labels: xValues.map(v => String(v || '')),
          values: yValues.map(v => Number(v) || 0),
          type: 'pie', hole: 0.38,
          marker: { colors: CHART_COLORS.map(c => c.hex) }
        };
      }

      const title = visualization?.layout?.title?.text || visualization?.layout?.title || '';
      const layout = {
        title: title ? { text: title, font: { color: isDarkMode ? '#e8eaed' : '#202124', size: 13, family: 'Outfit, sans-serif', weight: 'bold' } } : undefined,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: isDarkMode ? '#9aa0a6' : '#5f6368', family: 'Outfit, sans-serif', size: 11 },
        xaxis: {
          title: { text: xAxisCol, font: { size: 11, family: 'Outfit, sans-serif', weight: 'bold' } },
          gridcolor: isDarkMode ? '#2d2d2d' : '#e8eaed',
          linecolor: isDarkMode ? '#3c4043' : '#dadce0',
          tickfont: { size: 10 }
        },
        yaxis: {
          title: { text: yAxisCol, font: { size: 11, family: 'Outfit, sans-serif', weight: 'bold' } },
          gridcolor: isDarkMode ? '#2d2d2d' : '#e8eaed',
          linecolor: isDarkMode ? '#3c4043' : '#dadce0',
          tickfont: { size: 10 }
        },
        margin: { t: title ? 48 : 24, r: 24, l: 64, b: 54 },
        autosize: true,
        showlegend: chartType === 'Pie',
        legend: { font: { size: 10, family: 'Outfit, sans-serif' } }
      };

      window.Plotly.newPlot(chartRef.current, [trace], layout, { responsive: true, displayModeBar: false });
    } catch (err) {
      console.error("Plotly render error", err);
    }
  }, [chartCollapsed, chartType, xAxisCol, yAxisCol, themeColor, data, isDarkMode, visualization]);

  // ─── Table filtering & pagination ─────────────────────────────────────────
  const sortedRows = useMemo(() => {
    if (sortDirection === 'none' || !sortColumn || !columns || !rawRows) return rawRows;
    const colIdx = columns.indexOf(sortColumn);
    if (colIdx === -1) return rawRows;

    return [...rawRows].sort((a, b) => {
      const valA = a[colIdx];
      const valB = b[colIdx];

      if (valA === null || valA === undefined) return sortDirection === 'asc' ? -1 : 1;
      if (valB === null || valB === undefined) return sortDirection === 'asc' ? 1 : -1;

      // Try numeric comparison
      const numA = Number(valA);
      const numB = Number(valB);
      if (!isNaN(numA) && !isNaN(numB)) {
        return sortDirection === 'asc' ? numA - numB : numB - numA;
      }

      // Fallback to localeCompare
      const strA = String(valA);
      const strB = String(valB);
      return sortDirection === 'asc' 
        ? strA.localeCompare(strB, undefined, { numeric: true, sensitivity: 'base' })
        : strB.localeCompare(strA, undefined, { numeric: true, sensitivity: 'base' });
    });
  }, [rawRows, sortColumn, sortDirection, columns]);

  const filteredRows = useMemo(() => {
    if (!sortedRows) return [];
    return sortedRows.filter(row =>
      !searchTerm || row.some(cell => String(cell).toLowerCase().includes(searchTerm.toLowerCase()))
    );
  }, [sortedRows, searchTerm]);

  const totalPages = Math.ceil(filteredRows.length / itemsPerPage);
  const paginatedRows = filteredRows.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  // ─── Export handlers ───────────────────────────────────────────────────────
  const handleExport = async (format: 'pdf' | 'excel' | 'csv') => {
    let chartImage: string | null = null;
    if (window.Plotly && chartRef.current && !chartCollapsed) {
      try {
        chartImage = await window.Plotly.toImage(chartRef.current, {
          format: 'png',
          width: 800,
          height: 400
        });
      } catch (e) {
        console.error("Chart export failed", e);
      }
    }

    try {
      const response = await fetch(`${BACKEND_BASE}/api/sessions/${activeSessionId}/messages/${activeMessage?.id}/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          format: format,
          chart_image: chartImage,
          selected_rows: selectedRows.length > 0 ? selectedRows : null
        })
      });

      if (!response.ok) {
        throw new Error('Export request failed');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      let extension = 'csv';
      if (format === 'excel') extension = 'xlsx';
      else if (format === 'pdf') extension = 'pdf';

      a.download = `${language === 'tr' ? 'analiz_raporu' : 'analysis_report'}_${activeMessage?.id.substring(0, 6)}.${extension}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export error", err);
      alert(t.exportError);
    }
  };

  // ─── Empty state ──────────────────────────────────────────────────────────
  if (!activeMessage) {
    return (
      <Box sx={{ flex: 1, height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', p: 4, bgcolor: 'background.default', borderLeft: '1px solid', borderColor: 'divider' }}>
        <Paper
          elevation={0}
          sx={{
            p: 5,
            maxWidth: 420,
            textAlign: 'center',
            borderRadius: '16px',
            border: '1px solid',
            borderColor: 'divider',
            background: isDarkMode
              ? 'linear-gradient(135deg, rgba(24, 24, 27, 0.7) 0%, rgba(9, 9, 11, 0.85) 100%)'
              : 'linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(244, 244, 245, 0.9) 100%)',
            backdropFilter: 'blur(20px)',
            boxShadow: isDarkMode ? '0 16px 40px rgba(0, 0, 0, 0.4)' : '0 16px 40px rgba(99, 102, 241, 0.04)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center'
          }}
        >
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: '16px',
              border: '1px solid rgba(99, 102, 241, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mb: 3,
              bgcolor: 'rgba(99, 102, 241, 0.08)',
              boxShadow: '0 8px 24px rgba(99, 102, 241, 0.15)',
              animation: 'pulseSubtle 2s infinite ease-in-out',
            }}
          >
            <Eye size={24} style={{ color: '#6366f1' }} />
          </Box>
          <Typography variant="body2" sx={{ fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', fontSize: 12, color: 'text.primary', mb: 1.5, fontFamily: 'var(--font-mono)' }}>
            {t.visualizerEmptyTitle}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', maxWidth: 300, textAlign: 'center', lineHeight: 1.6, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
            {t.visualizerEmptyDesc}
          </Typography>
        </Paper>
      </Box>
    );
  }

  const highlightText = (text: string, search: string) => {
    if (!search.trim()) return <span>{text}</span>;
    const regex = new RegExp(`(${search.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')})`, 'gi');
    const parts = text.split(regex);
    return (
      <span>
        {parts.map((part, i) => 
          regex.test(part) ? (
            <span key={i} style={{ backgroundColor: 'rgba(99, 102, 241, 0.2)', color: '#818cf8', fontWeight: 600, padding: '2px 4px', borderRadius: '4px' }}>{part}</span>
          ) : part
        )}
      </span>
    );
  };

  const hasChart = !!visualization;


  return (
    <Box sx={{ flex: 1, height: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default', borderLeft: '1px solid', borderColor: 'divider', overflow: 'hidden' }}>

      {/* ── Chart Section (collapsible) ── */}
      {hasChart && (
        <Box sx={{ flexShrink: 0, borderBottom: '1px solid', borderColor: 'divider', bgcolor: isDarkMode ? 'rgba(99, 102, 241, 0.015)' : 'rgba(99, 102, 241, 0.005)', display: 'flex', flexDirection: 'column', position: 'relative' }}>

          {/* Chart header / toolbar */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifycontent: 'space-between', px: 2.5, py: 1.5, borderBottom: '1px solid', borderColor: 'divider', flexWrap: 'wrap', gap: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <BarChart2 size={16} style={{ color: '#6366f1' }} />
              <Typography variant="caption" sx={{ fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'text.primary', fontFamily: 'var(--font-mono)' }}>
                {t.chartTitle}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>

              {/* Chart type segmented pills using ToggleButtonGroup */}
              <ToggleButtonGroup
                value={chartType}
                exclusive
                onChange={(_, val) => val && setChartType(val)}
                size="small"
                sx={{
                  height: 28, border: '1px solid', borderColor: 'divider', borderRadius: '8px', p: 0.2, bgcolor: 'background.paper',
                  '& .MuiToggleButton-root': {
                    border: 0, px: 1.5, py: 0, fontSize: 10, fontWeight: 600, textTransform: 'none', color: 'text.secondary',
                    borderRadius: '6px',
                    fontFamily: 'var(--font-mono)',
                    '&.Mui-selected': { bgcolor: 'rgba(99, 102, 241, 0.12)', color: '#6366f1', '&:hover': { bgcolor: 'rgba(99, 102, 241, 0.18)' } }
                  }
                }}
              >
                {(['Bar', 'Line', 'Area', 'Scatter', 'Pie'] as const).map(item => (
                  <ToggleButton value={item} key={item}>{item}</ToggleButton>
                ))}
              </ToggleButtonGroup>

              {/* Axis selectors (hide for Pie) */}
              {chartType !== 'Pie' && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <FormControl size="small" sx={{ m: 0, p: 0 }}>
                    <Select
                      value={xAxisCol}
                      onChange={e => setXAxisCol(e.target.value)}
                      sx={{
                        fontSize: 10, height: 28, fontFamily: 'var(--font-mono)', borderRadius: '8px', bgcolor: 'background.paper', minWidth: 90,
                        '& .MuiSelect-select': { py: 0.5, px: 1.5 }
                      }}
                      title={language === 'tr' ? "X Ekseni" : "X Axis"}
                    >
                      {columns.map(c => <MenuItem key={c} value={c} sx={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>{c}</MenuItem>)}
                    </Select>
                  </FormControl>

                  <span style={{ fontSize: 11, color: 'text.secondary', fontWeight: 600 }}>×</span>

                  <FormControl size="small" sx={{ m: 0, p: 0 }}>
                    <Select
                      value={yAxisCol}
                      onChange={e => setYAxisCol(e.target.value)}
                      sx={{
                        fontSize: 10, height: 28, fontFamily: 'var(--font-mono)', borderRadius: '8px', bgcolor: 'background.paper', minWidth: 90,
                        '& .MuiSelect-select': { py: 0.5, px: 1.5 }
                      }}
                      title={language === 'tr' ? "Y Ekseni" : "Y Axis"}
                    >
                      {columns.map(c => <MenuItem key={c} value={c} sx={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>{c}</MenuItem>)}
                    </Select>
                  </FormControl>
                </Box>
              )}

              {/* Color swatches */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {CHART_COLORS.map(c => (
                  <button
                    key={c.hex}
                    onClick={() => setThemeColor(c.hex)}
                    title={c.name}
                    style={{
                      width: 14, height: 14, borderRadius: '50%', backgroundColor: c.hex, border: themeColor === c.hex ? '2px solid var(--color-text)' : '1px solid transparent',
                      cursor: 'pointer', outline: 'none', padding: 0, transition: 'all 0.15s',
                      boxShadow: themeColor === c.hex ? '0 0 8px rgba(99, 102, 241, 0.45)' : 'none'
                    }}
                  />
                ))}
              </Box>

              {/* Collapse toggle */}
              <Tooltip title={chartCollapsed ? t.chartShow : t.chartHide}>
                <IconButton onClick={() => setChartCollapsed(p => !p)} size="small" sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', p: 0.6, mr: 1 }}>
                  {chartCollapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                </IconButton>
              </Tooltip>

              {/* Close / Dismiss visualizer panel */}
              <Tooltip title={t.closePanelTooltip}>
                <IconButton onClick={() => setVisualizerDismissed(true)} size="small" sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', p: 0.6, color: 'error.main', '&:hover': { bgcolor: 'rgba(239, 68, 68, 0.08)', borderColor: 'error.light' } }}>
                  <X size={14} />
                </IconButton>
              </Tooltip>

            </Box>
          </Box>

          {/* Plotly canvas */}
          {!chartCollapsed && (
            <Box ref={chartRef} sx={{ height: chartHeight, width: '100%', px: 0.5, py: 1 }} />
          )}

          {/* Dynamic Natural Language Chart Tuner (Suggestion 6) */}
          {!chartCollapsed && (
            <Box sx={{ px: 2.5, pb: 1.5, display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <TextField
                fullWidth
                size="small"
                variant="outlined"
                placeholder={t.chartTunerPlaceholder}
                slotProps={{
                  input: {
                    startAdornment: (
                      <InputAdornment position="start">
                        <Sparkles size={13} style={{ color: '#6366f1' }} />
                      </InputAdornment>
                    ),
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const val = (e.target as HTMLInputElement).value.toLowerCase().trim();
                    if (!val) return;
                    
                    // Chart Type mapping
                    if (val.includes('çizgi') || val.includes('line')) setChartType('Line');
                    else if (val.includes('bar') || val.includes('sütun') || val.includes('column')) setChartType('Bar');
                    else if (val.includes('alan') || val.includes('area')) setChartType('Area');
                    else if (val.includes('saçılım') || val.includes('scatter') || val.includes('nokta')) setChartType('Scatter');
                    else if (val.includes('pie') || val.includes('pasta') || val.includes('daire')) setChartType('Pie');
                    
                    // Theme color mapping
                    if (val.includes('mavi') || val.includes('blue')) setThemeColor('#6366f1');
                    else if (val.includes('yeşil') || val.includes('green')) setThemeColor('#10b981');
                    else if (val.includes('sarı') || val.includes('yellow')) setThemeColor('#f59e0b');
                    else if (val.includes('kırmızı') || val.includes('red')) setThemeColor('#ef4444');
                    else if (val.includes('mor') || val.includes('purple')) setThemeColor('#8b5cf6');
                    
                    // Column mapping
                    columns.forEach(col => {
                      const colLower = col.toLowerCase();
                      if (val.includes(`x ekseni ${colLower}`) || val.includes(`x eksenini ${colLower}`) || val.includes(`x ekseni ${colLower} yap`) || val.includes(`x:${colLower}`)) {
                        setXAxisCol(col);
                      } else if (val.includes(`y ekseni ${colLower}`) || val.includes(`y eksenini ${colLower}`) || val.includes(`y ekseni ${colLower} yap`) || val.includes(`y:${colLower}`)) {
                        setYAxisCol(col);
                      }
                    });
                    
                    (e.target as HTMLInputElement).value = '';
                  }
                }}
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: '8px',
                    height: 28,
                    fontSize: 10.5,
                    bgcolor: 'background.paper',
                    fontFamily: 'var(--font-mono)',
                    '& input': { py: 0.5 }
                  }
                }}
              />
            </Box>
          )}

          {/* Divider Drag Handle for Resizing */}
          {!chartCollapsed && (
            <Box
              onPointerDown={startResize}
              sx={{
                height: 6, bgcolor: 'divider', '&:hover': { bgcolor: '#6366f1' }, cursor: 'row-resize',
                transition: 'background-color 0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', zIndex: 10
              }}
            >
              <Box sx={{ position: 'absolute', width: 32, height: 3, borderRadius: '4px', bgcolor: 'text.secondary', opacity: 0.3 }} />
            </Box>
          )}
        </Box>
      )}

      {/* ── Table Section ── */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0 }}>

        {/* Table toolbar */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2.5, py: 1.5, borderBottom: '1px solid', borderColor: 'divider', bgcolor: isDarkMode ? 'rgba(99, 102, 241, 0.008)' : 'rgba(99, 102, 241, 0.002)', flexShrink: 0, gap: 2, flexWrap: 'wrap' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flex: 1, minWidth: 260 }}>
            <TableIcon size={16} style={{ color: '#6366f1' }} />
            <TextField
              size="small"
              value={searchTerm}
              onChange={e => { setSearchTerm(e.target.value); setCurrentPage(1); }}
              placeholder={t.searchInTable}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon size={13} style={{ color: 'text.secondary' }} />
                    </InputAdornment>
                  )
                }
              }}
              sx={{
                maxWidth: 240,
                '& .MuiOutlinedInput-root': {
                  borderRadius: '8px',
                  height: 28,
                  fontSize: 11,
                  bgcolor: 'background.paper',
                  fontFamily: 'var(--font-mono)',
                  '& input': { py: 0.5 }
                }
              }}
            />
            <Chip
              label={`${filteredRows.length} ${t.rowsCountBadge}`}
              size="small"
              sx={{ height: 18, fontSize: 9, fontWeight: 600, bgcolor: 'rgba(99, 102, 241, 0.12)', color: '#818cf8', border: 0, borderRadius: '6px', fontFamily: 'var(--font-mono)' }}
            />
            {selectedRows.length > 0 && (
              <Chip
                label={`${selectedRows.length} ${t.selectedCountBadge}`}
                size="small"
                sx={{ height: 18, fontSize: 9, fontWeight: 600, bgcolor: 'rgba(16, 185, 129, 0.12)', color: '#10b981', border: 0, borderRadius: '6px', animation: 'pulseSubtle 1.5s infinite', fontFamily: 'var(--font-mono)' }}
              />
            )}
          </Box>

          {/* Export buttons */}
          {data && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Tooltip title={t.exportExcelTooltip}>
                <Button
                  onClick={() => handleExport('excel')}
                  size="small"
                  variant="outlined"
                  startIcon={<FileDown size={12} />}
                  sx={{
                    py: 0.5, px: 1.5, fontSize: 10, fontWeight: 600, textTransform: 'none',
                    borderColor: 'rgba(16, 185, 129, 0.2)', color: 'success.main', borderRadius: '6px',
                    bgcolor: 'rgba(16, 185, 129, 0.05)',
                    fontFamily: 'var(--font-mono)',
                    '&:hover': { borderColor: 'success.dark', bgcolor: 'rgba(16, 185, 129, 0.12)' }
                  }}
                >
                  Excel
                </Button>
              </Tooltip>

              <Tooltip title={t.exportPdfTooltip}>
                <Button
                  onClick={() => handleExport('pdf')}
                  size="small"
                  variant="outlined"
                  startIcon={<FileDown size={12} />}
                  sx={{
                    py: 0.5, px: 1.5, fontSize: 10, fontWeight: 600, textTransform: 'none',
                    borderColor: 'rgba(239, 68, 68, 0.2)', color: 'error.main', borderRadius: '6px',
                    bgcolor: 'rgba(239, 68, 68, 0.05)',
                    fontFamily: 'var(--font-mono)',
                    '&:hover': { borderColor: 'error.dark', bgcolor: 'rgba(239, 68, 68, 0.12)' }
                  }}
                >
                  PDF
                </Button>
              </Tooltip>

              <Tooltip title={t.exportCsvTooltip}>
                <Button
                  onClick={() => handleExport('csv')}
                  size="small"
                  variant="outlined"
                  startIcon={<FileDown size={12} />}
                  sx={{
                    py: 0.5, px: 1.5, fontSize: 10, fontWeight: 600, textTransform: 'none',
                    borderColor: 'divider', color: 'text.secondary', borderRadius: '6px',
                    bgcolor: 'action.hover',
                    fontFamily: 'var(--font-mono)',
                    '&:hover': { borderColor: 'text.primary', bgcolor: 'rgba(255, 255, 255, 0.05)' }
                  }}
                >
                  CSV
                </Button>
              </Tooltip>
              {/* Close / Dismiss entire visualizer panel */}
              <Tooltip title={t.closePanelTooltip}>
                <IconButton 
                  onClick={() => setVisualizerDismissed(true)} 
                  size="small" 
                  sx={{ 
                    border: '1px solid', 
                    borderColor: 'divider', 
                    borderRadius: '6px', 
                    p: 0.6, 
                    color: 'error.main', 
                    '&:hover': { bgcolor: 'rgba(239, 68, 68, 0.08)', borderColor: 'error.light' },
                    ml: 0.5
                  }}
                >
                  <X size={12} />
                </IconButton>
              </Tooltip>
            </Box>
          )}
        </Box>

        {/* Table viewport */}
        {data ? (
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0, p: 2.5, gap: 2 }}>
            <TableContainer
              component={Paper}
              variant="outlined"
              sx={{
                flex: 1,
                overflow: 'auto',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: '12px',
                minHeight: 0,
                boxShadow: isDarkMode ? 'inset 0 0 12px rgba(0,0,0,0.3)' : 'none',
                bgcolor: 'background.paper'
              }}
            >
              <Table size="small" stickyHeader sx={{ '& th, & td': { p: 1.2, fontSize: 11.5, fontFamily: 'var(--font-mono)' } }}>
                <TableHead>
                  <TableRow>
                    {/* Header Selection Checkbox */}
                    <TableCell align="center" sx={{ width: 48, bgcolor: 'background.paper', borderRight: '1px solid', borderColor: 'divider', p: 0.5 }}>
                      <input
                        type="checkbox"
                        checked={filteredRows.length > 0 && selectedRows.length === filteredRows.length}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedRows(filteredRows);
                          } else {
                            setSelectedRows([]);
                          }
                        }}
                        style={{ cursor: 'pointer', width: 13, height: 13 }}
                      />
                    </TableCell>
                    <TableCell align="center" sx={{ fontWeight: 600, bgcolor: 'background.paper', borderRight: '1px solid', borderColor: 'divider', width: 48, color: 'text.secondary', fontSize: 10.5 }}>#</TableCell>
                    {columns.map(col => {
                      const isNumeric = numericColsSet.has(col);
                      const isSorted = sortColumn === col;
                      return (
                        <TableCell
                           key={col}
                           align={isNumeric ? 'right' : 'left'}
                           onClick={() => {
                             if (sortColumn === col) {
                               if (sortDirection === 'asc') setSortDirection('desc');
                               else if (sortDirection === 'desc') setSortDirection('none');
                               else setSortDirection('asc');
                             } else {
                               setSortColumn(col);
                               setSortDirection('asc');
                             }
                           }}
                           sx={{
                             fontWeight: 600,
                             bgcolor: 'background.paper',
                             borderRight: '1px solid',
                             borderColor: 'divider',
                             color: isSorted ? '#6366f1' : 'text.primary',
                             fontSize: 11,
                             cursor: 'pointer',
                             userSelect: 'none',
                             transition: 'background-color 0.15s',
                             '&:hover': { bgcolor: 'action.hover' }
                           }}
                        >
                          <Box sx={{ display: 'inline-flex', alignItems: 'center', justifyContent: isNumeric ? 'flex-end' : 'flex-start', gap: 0.5 }}>
                            <span>{col}</span>
                            {isSorted && sortDirection !== 'none' && (
                              <span style={{ fontSize: 9, color: '#6366f1', fontWeight: 600 }}>
                                {sortDirection === 'asc' ? '▲' : '▼'}
                              </span>
                            )}
                          </Box>
                        </TableCell>
                      );
                    })}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paginatedRows.map((row, rIdx) => {
                    const rowStr = JSON.stringify(row);
                    const isChecked = selectedRows.some(r => JSON.stringify(r) === rowStr);
                    return (
                      <TableRow 
                        key={rIdx} 
                        hover 
                        selected={isChecked}
                        sx={{ 
                          '&:hover': { bgcolor: 'rgba(99, 102, 241, 0.04) !important' },
                          '&.Mui-selected': { bgcolor: 'rgba(16, 185, 129, 0.06) !important', '&:hover': { bgcolor: 'rgba(16, 185, 129, 0.1) !important' } }
                        }}
                      >
                        {/* Row Checkbox Cell */}
                        <TableCell align="center" sx={{ borderRight: '1px solid', borderColor: 'divider', p: 0.5 }}>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedRows(prev => [...prev, row]);
                              } else {
                                setSelectedRows(prev => prev.filter(r => JSON.stringify(r) !== rowStr));
                              }
                            }}
                            style={{ cursor: 'pointer', width: 13, height: 13 }}
                          />
                        </TableCell>
                        <TableCell align="center" sx={{ bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.01)' : 'rgba(0, 0, 0, 0.01)', borderRight: '1px solid', borderColor: 'divider', color: 'text.secondary', fontSize: 10 }}>
                          {(currentPage - 1) * itemsPerPage + rIdx + 1}
                        </TableCell>
                        {row.map((cell, cIdx) => {
                        const col = columns[cIdx];
                        const isNumeric = numericColsSet.has(col);
                        return (
                          <TableCell
                            key={cIdx}
                            align={isNumeric ? 'right' : 'left'}
                            sx={{ borderRight: '1px solid', borderColor: 'divider', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: 200 }}
                            title={String(cell)}
                          >
                            {cell === null ? (
                              <span style={{ fontStyle: 'italic', color: 'text.secondary', opacity: 0.45, fontSize: 10.5 }}>null</span>
                            ) : (
                              highlightText(String(cell), searchTerm)
                            )}
                          </TableCell>
                        );
                      })}
                      </TableRow>
                    );
                  })}
                  {paginatedRows.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={columns.length + 2} align="center" sx={{ py: 8, fontStyle: 'italic', color: 'text.secondary' }}>
                        {t.noDataFound}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                <IconButton
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(p => p - 1)}
                  size="small"
                  sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px' }}
                >
                  <ChevronLeft size={14} />
                </IconButton>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                  {t.page} <strong style={{ color: '#6366f1' }}>{currentPage}</strong> / {totalPages}
                </Typography>
                <IconButton
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(p => p + 1)}
                  size="small"
                  sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px' }}
                >
                  <ChevronRight size={14} />
                </IconButton>
              </Box>
            )}
          </Box>
        ) : (
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', p: 6, m: 2.5, border: '1px dashed', borderColor: 'divider', borderRadius: '12px', bgcolor: 'rgba(99, 102, 241, 0.005)' }}>
            <TableIcon size={32} style={{ color: '#6366f1', opacity: 0.3, marginBottom: 12 }} />
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', maxWidth: 260, mx: 'auto', textAlign: 'center', lineHeight: 1.6, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              {t.noTableData}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default ResultVisualizer;



