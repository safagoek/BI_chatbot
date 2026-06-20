import React, { useState, useEffect } from 'react';
import { useBIStore, BACKEND_BASE } from '../context/store';
import { translations } from '../context/translations';
import FileUpload from './FileUpload';
import {
  Database, Plus, RefreshCw, ShieldCheck, Trash2, X,
  Server, HardDrive, AlertCircle, Eye, Edit3, Copy, Power, Tag, ChevronDown,
  Cpu, Play, Save, Search, Layers, Cloud, Upload
} from 'lucide-react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, TextField, Button,
  ToggleButton, ToggleButtonGroup, Card, CardContent, Grid, Typography, Box,
  IconButton, Tooltip, Accordion, AccordionSummary, AccordionDetails, Chip,
  CircularProgress, Alert, Checkbox, FormControlLabel
} from '@mui/material';

const API = BACKEND_BASE;

type DbType = 'sqlite' | 'postgresql' | 'mysql' | 'sap_s4hana' | 'snowflake' | 'mssql' | 'bigquery';

interface ConnectionForm {
  display_name: string;
  type: DbType;
  // SQLite
  database_path: string;
  // Remote
  host: string;
  port: string;
  database: string;
  schema: string;
  // Credentials
  user: string;
  password: string;
  // Snowflake / BigQuery specific
  account?: string;
  warehouse?: string;
  project_id?: string;
  dataset_id?: string;
  credentials_json?: string;
}

const DEFAULT_FORM: ConnectionForm = {
  display_name: '',
  type: 'postgresql',
  database_path: '',
  host: 'localhost',
  port: '5432',
  database: '',
  schema: '',
  user: '',
  password: '',
  account: '',
  warehouse: '',
  project_id: '',
  dataset_id: '',
  credentials_json: '',
};

const DB_TYPE_OPTIONS = [
  { value: 'sap_s4hana', label: 'SAP S/4HANA', icon: Cpu, color: '#f9ab00' },
  { value: 'postgresql', label: 'PostgreSQL', icon: Database, color: '#0078d4' },   // Fluent Communication Blue
  { value: 'mysql', label: 'MySQL / MariaDB', icon: Server, color: '#00acac' },
  { value: 'sqlite', label: 'SQLite', icon: HardDrive, color: '#7a4dff' },          // Fluent Purple
  { value: 'snowflake', label: 'Snowflake', icon: Cloud, color: '#00c0f3' },
  { value: 'mssql', label: 'MS SQL Server', icon: Database, color: '#e81123' },
  { value: 'bigquery', label: 'Google BigQuery', icon: Layers, color: '#4285f4' },
];


const DEFAULT_PORTS: Record<DbType, string> = {
  sap_s4hana: '30015',
  postgresql: '5432',
  mysql: '3306',
  sqlite: '',
  snowflake: '',
  mssql: '1433',
  bigquery: '',
};

export const SourceManager: React.FC = () => {
  const { 
    sources, files, activeSourceId, selectedSourceIds, 
    fetchSources, fetchFiles, setActiveSourceId, language 
  } = useBIStore();

  const t = translations[language];

  const [showForm, setShowForm] = useState(false);
  const [localSqliteFiles, setLocalSqliteFiles] = useState<string[]>([]);
  const [loadingSqliteFiles, setLoadingSqliteFiles] = useState(false);
  const [showManualPathInput, setShowManualPathInput] = useState(false);
  const [uploadingSqlite, setUploadingSqlite] = useState(false);
  const [uploadSqliteError, setUploadSqliteError] = useState<string | null>(null);
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<ConnectionForm>(DEFAULT_FORM);
  const [detailSourceId, setDetailSourceId] = useState<string | null>(null);
  const [labelsInput, setLabelsInput] = useState('');
  const [labelsSaving, setLabelsSaving] = useState(false);
  const [labelsError, setLabelsError] = useState<string | null>(null);
  const [cloningId, setCloningId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Semantic Layer states
  const [semanticSourceId, setSemanticSourceId] = useState<string | null>(null);
  const [semanticMapping, setSemanticMapping] = useState<Record<string, Record<string, { label: string; description: string }>>>({});
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [semanticSaving, setSemanticSaving] = useState(false);
  const [semanticError, setSemanticError] = useState<string | null>(null);

  // Test state
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Save state
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Refresh / delete states per source
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [snapshotting, _setSnapshotting] = useState<string | null>(null);

  // Selective Snapshot Table Selection States
  const [tableSelectionOpen, setTableSelectionOpen] = useState(false);
  const [tableSelectionSource, setTableSelectionSource] = useState<any>(null);
  const [selectedTables, setSelectedTables] = useState<Record<string, boolean>>({});
  const [tableSearchQuery, setTableSearchQuery] = useState('');

  // Snapshot Progress States
  const [snapshotDialogOpen, setSnapshotDialogOpen] = useState(false);
  const [snapshotSource, setSnapshotSource] = useState<any>(null);
  const [snapshotProgress, setSnapshotProgress] = useState<{
    status: 'idle' | 'running' | 'completed' | 'failed';
    message: string;
    discoveredTables: string[];
    completedTables: Record<string, { rows: number; indexes: number; status: 'pending' | 'running' | 'completed' | 'failed'; error?: string }>;
    currentTable: string;
    currentTableIndex: number;
    currentProgressRows: number;
    logs: string[];
  }>({
    status: 'idle',
    message: '',
    discoveredTables: [],
    completedTables: {},
    currentTable: '',
    currentTableIndex: 0,
    currentProgressRows: 0,
    logs: []
  });

  useEffect(() => {
    fetchSources();
    fetchFiles();
  }, []);

  useEffect(() => {
    if (showForm && formValues.type === 'sqlite') {
      const fetchLocalSqliteFiles = async () => {
        setLoadingSqliteFiles(true);
        try {
          const res = await fetch(`${API}/api/sources/local-sqlite-files`);
          if (res.ok) {
            const data = await res.json();
            setLocalSqliteFiles(data);
            if (!formValues.database_path && data.length > 0) {
              const defaultDb = data[0];
              setFormValues(prev => ({ ...prev, database_path: defaultDb }));
            }
          }
        } catch (err) {
          console.error("Failed to load local SQLite files", err);
        } finally {
          setLoadingSqliteFiles(false);
        }
      };
      fetchLocalSqliteFiles();
    }
  }, [showForm, formValues.type]);

  useEffect(() => {
    if (showForm && formValues.type === 'sqlite' && formValues.database_path) {
      if (localSqliteFiles.length > 0 && !localSqliteFiles.includes(formValues.database_path)) {
        setShowManualPathInput(true);
      }
    }
  }, [showForm, formValues.type, localSqliteFiles, formValues.database_path]);

  const buildConnectionDetails = () => {
    if (formValues.type === 'sqlite') {
      return { database_path: formValues.database_path };
    }
    if (formValues.type === 'snowflake') {
      return {
        account: formValues.account,
        warehouse: formValues.warehouse,
        database: formValues.database,
        schema: formValues.schema,
        user: formValues.user,
        password: formValues.password,
      };
    }
    if (formValues.type === 'bigquery') {
      return {
        project_id: formValues.project_id,
        credentials_json: formValues.credentials_json,
      };
    }
    return {
      host: formValues.host,
      port: formValues.port ? parseInt(formValues.port, 10) : undefined,
      database: formValues.database,
      schema: formValues.schema,
      user: formValues.user,
      password: formValues.password,
    };
  };

  const handleTypeChange = (t: DbType) => {
    setFormValues(prev => ({ ...prev, type: t, port: DEFAULT_PORTS[t] }));
    setTestResult(null);
  };

  const handleStartAdd = () => {
    setEditingSourceId(null);
    setFormValues(DEFAULT_FORM);
    setTestResult(null);
    setSaveError(null);
    setUploadSqliteError(null);
    setShowManualPathInput(false);
    setShowForm(true);
  };

  const handleStartEdit = (e: React.MouseEvent, src: any) => {
    e.stopPropagation();
    setEditingSourceId(src.id);
    const d = src.connection_details ?? {};
    setFormValues({
      display_name: src.display_name,
      type: src.type as DbType,
      database_path: d.database_path ?? '',
      host: d.host ?? '',
      port: String(d.port ?? DEFAULT_PORTS[src.type as DbType] ?? ''),
      database: d.database ?? '',
      schema: d.schema ?? '',
      user: d.user ?? '',
      password: d.password ?? '',
      account: d.account ?? '',
      warehouse: d.warehouse ?? '',
      project_id: d.project_id ?? '',
      dataset_id: d.dataset_id ?? '',
      credentials_json: d.credentials_json ?? '',
    });
    setTestResult(null);
    setSaveError(null);
    setUploadSqliteError(null);
    setShowManualPathInput(false);
    setShowForm(true);
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API}/api/sources/test-connection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: formValues.type, connection_details: buildConnectionDetails() }),
      });
      const data = await res.json();
      setTestResult({ success: data.success, message: data.message });
    } catch {
      setTestResult({ success: false, message: t.serverConnectionFailed });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!testResult?.success) return;
    setSaving(true);
    setSaveError(null);
    try {
      const url = editingSourceId ? `${API}/api/sources/${editingSourceId}` : `${API}/api/sources`;
      const method = editingSourceId ? 'PUT' : 'POST';
      const bodyPayload = editingSourceId ? {
        display_name: formValues.display_name,
        connection_details: buildConnectionDetails(),
      } : {
        display_name: formValues.display_name,
        type: formValues.type,
        connection_details: buildConnectionDetails(),
      };

      const res = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyPayload),
      });
      if (!res.ok) {
        const err = await res.json();
        setSaveError(err.detail || t.saveConnectionFailed);
        return;
      }
      await fetchSources();
      setShowForm(false);
      setEditingSourceId(null);
      setFormValues(DEFAULT_FORM);
      setTestResult(null);
    } catch (e: any) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRefreshSchema = async (e: React.MouseEvent, sourceId: string) => {
    e.stopPropagation();
    setRefreshing(sourceId);
    try {
      const res = await fetch(`${API}/api/sources/${sourceId}/refresh-schema`, { method: 'PUT' });
      if (res.ok) await fetchSources();
    } finally {
      setRefreshing(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, sourceId: string) => {
    e.stopPropagation();
    if (!window.confirm(t.deleteConfirm)) return;
    setDeleting(sourceId);
    try {
      const res = await fetch(`${API}/api/sources/${sourceId}`, { method: 'DELETE' });
      if (res.ok) await fetchSources();
    } finally {
      setDeleting(null);
    }
  };

  const handleStartSnapshotFlow = (e: React.MouseEvent, sourceId: string) => {
    e.stopPropagation();
    const src = sources.find(s => s.id === sourceId);
    if (!src) return;

    const tables = Object.keys(src.schema ?? {});
    if (tables.length === 0) {
      if (window.confirm(t.scanSchemaPrompt)) {
        runSnapshotReplication(src, []);
      }
      return;
    }

    setTableSelectionSource(src);
    const initialSelection: Record<string, boolean> = {};
    tables.forEach(t => {
      initialSelection[t] = true;
    });
    setSelectedTables(initialSelection);
    setTableSearchQuery('');
    setTableSelectionOpen(true);
  };

  const runSnapshotReplication = (src: any, chosenTables: string[]) => {
    setSnapshotSource(src);
    setSnapshotDialogOpen(true);
    
    const initialProgress = {
      status: 'running' as const,
      message: t.initRemoteConnection,
      discoveredTables: [],
      completedTables: {},
      currentTable: '',
      currentTableIndex: 0,
      currentProgressRows: 0,
      logs: [t.snapshotStartLog]
    };
    setSnapshotProgress(initialProgress);

    const queryParam = chosenTables.length > 0 ? `?tables=${encodeURIComponent(chosenTables.join(','))}` : '';
    const eventSource = new EventSource(`${API}/api/sources/${src.id}/snapshot/stream${queryParam}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const timestamp = new Date().toLocaleTimeString();
        const logMsg = `[${timestamp}] ${data.message}`;

        setSnapshotProgress(prev => {
          const updatedLogs = [...prev.logs, logMsg];
          let updatedCompleted = { ...prev.completedTables };
          let updatedDiscovered = [...prev.discoveredTables];
          let updatedCurrentTable = prev.currentTable;
          let updatedIndex = prev.currentTableIndex;
          let updatedRows = prev.currentProgressRows;
          let updatedStatus = prev.status;

          if (data.status === 'schema') {
            updatedDiscovered = data.tables || [];
            updatedCompleted = {};
            updatedDiscovered.forEach(t => {
              updatedCompleted[t] = { rows: 0, indexes: 0, status: 'pending' };
            });
          } else if (data.status === 'table_start') {
            updatedCurrentTable = data.table;
            updatedIndex = data.index || 0;
            updatedRows = 0;
            if (updatedCompleted[data.table]) {
              updatedCompleted[data.table] = {
                ...updatedCompleted[data.table],
                status: 'running'
              };
            }
          } else if (data.status === 'table_progress') {
            updatedRows = data.rows_copied || 0;
            if (updatedCompleted[data.table]) {
              updatedCompleted[data.table] = {
                ...updatedCompleted[data.table],
                rows: data.rows_copied
              };
            }
          } else if (data.status === 'table_done') {
            updatedRows = data.rows_total || 0;
            if (updatedCompleted[data.table]) {
              updatedCompleted[data.table] = {
                rows: data.rows_total,
                indexes: data.indexes_count || 0,
                status: 'completed'
              };
            }
          } else if (data.status === 'table_error') {
            if (updatedCompleted[data.table]) {
              updatedCompleted[data.table] = {
                ...updatedCompleted[data.table],
                status: 'failed',
                error: data.message
              };
            }
          } else if (data.status === 'error') {
            updatedStatus = 'failed';
            eventSource.close();
          } else if (data.status === 'complete') {
            updatedStatus = 'completed';
            fetchSources();
            eventSource.close();
          }

          return {
            ...prev,
            status: updatedStatus,
            message: data.message,
            discoveredTables: updatedDiscovered,
            completedTables: updatedCompleted,
            currentTable: updatedCurrentTable,
            currentTableIndex: updatedIndex,
            currentProgressRows: updatedRows,
            logs: updatedLogs
          };
        });
      } catch (err) {
        console.error('Error parsing SSE event:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('EventSource error:', err);
      const timestamp = new Date().toLocaleTimeString();
      setSnapshotProgress(prev => {
        if (prev.status === 'running') {
          eventSource.close();
          return {
            ...prev,
            status: 'failed',
            message: t.connectionErrorOccurred,
            logs: [...prev.logs, `[${timestamp}] ${t.serverConnLostLog}`]
          };
        }
        return prev;
      });
    };
  };

  const openDetails = (e: React.MouseEvent, sourceId: string) => {
    e.stopPropagation();
    const src = sources.find(s => s.id === sourceId);
    if (!src) return;
    setDetailSourceId(sourceId);
    setLabelsInput((src.labels || []).join(', '));
    setLabelsError(null);
  };

  const closeDetails = () => {
    setDetailSourceId(null);
    setLabelsInput('');
    setLabelsError(null);
  };

  const handleToggleStatus = async (e: React.MouseEvent, sourceId: string, isActive: boolean) => {
    e.stopPropagation();
    setTogglingId(sourceId);
    try {
      const res = await fetch(`${API}/api/sources/${sourceId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !isActive })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || t.updateStatusFailed);
      }
      await fetchSources();
    } catch (err: any) {
      alert(err.message || t.updateStatusFailed);
    } finally {
      setTogglingId(null);
    }
  };

  const handleClone = async (e: React.MouseEvent, sourceId: string) => {
    e.stopPropagation();
    setCloningId(sourceId);
    try {
      const res = await fetch(`${API}/api/sources/${sourceId}/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || t.cloningFailed);
      }
      await fetchSources();
    } catch (err: any) {
      alert(err.message || t.cloningFailed);
    } finally {
      setCloningId(null);
    }
  };

  const handleSaveLabels = async () => {
    if (!detailSourceId) return;
    setLabelsSaving(true);
    setLabelsError(null);
    const labels = labelsInput
      .split(',')
      .map(l => l.trim())
      .filter(Boolean);
    try {
      const res = await fetch(`${API}/api/sources/${detailSourceId}/labels`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ labels })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || t.saveTagsFailed);
      }
      await fetchSources();
      closeDetails();
    } catch (err: any) {
      setLabelsError(err.message || t.saveTagsFailed);
    } finally {
      setLabelsSaving(false);
    }
  };

  const openSemanticModal = async (e: React.MouseEvent, sourceId: string) => {
    e.stopPropagation();
    const src = sources.find(s => s.id === sourceId);
    if (!src) return;

    setSemanticSourceId(sourceId);
    setSemanticLoading(true);
    setSemanticError(null);

    try {
      const res = await fetch(`${API}/api/sources/${sourceId}/semantic`);
      if (!res.ok) throw new Error(t.loadSemanticFailed);
      const data = await res.json();

      const initialMapping: typeof semanticMapping = {};
      if (src.schema) {
        Object.entries(src.schema).forEach(([tbl, cols]) => {
          initialMapping[tbl] = {};
          if (Array.isArray(cols)) {
            cols.forEach((col: string) => {
              const existing = data[tbl]?.[col] || {};
              initialMapping[tbl][col] = {
                label: existing.label || '',
                description: existing.description || ''
              };
            });
          }
        });
      }

      setSemanticMapping(initialMapping);
    } catch (err: any) {
      setSemanticError(err.message || t.loadSemanticError);
    } finally {
      setSemanticLoading(false);
    }
  };

  const handleSaveSemantic = async () => {
    if (!semanticSourceId) return;
    setSemanticSaving(true);
    setSemanticError(null);
    try {
      const cleanMapping: Record<string, Record<string, { label: string; description: string }>> = {};
      Object.entries(semanticMapping).forEach(([tbl, cols]) => {
        const tblClean: Record<string, { label: string; description: string }> = {};
        Object.entries(cols).forEach(([col, info]) => {
          if (info.label.trim() || info.description.trim()) {
            tblClean[col] = {
              label: info.label.trim(),
              description: info.description.trim()
            };
          }
        });
        if (Object.keys(tblClean).length > 0) {
          cleanMapping[tbl] = tblClean;
        }
      });

      const res = await fetch(`${API}/api/sources/${semanticSourceId}/semantic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cleanMapping),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || t.saveSemanticFailed);
      }
      setSemanticSourceId(null);
    } catch (err: any) {
      setSemanticError(err.message || t.saveSemanticError);
    } finally {
      setSemanticSaving(false);
    }
  };

  const colorFor = (type: string) =>
    DB_TYPE_OPTIONS.find(o => o.value === type)?.color ?? '#0078d4';

  const labelTextFor = (type: string) =>
    DB_TYPE_OPTIONS.find(o => o.value === type)?.label ?? type.toUpperCase();

  const hostLabel = (src: any) => {
    const d = src.connection_details ?? {};
    if (src.type === 'sqlite') return d.database_path ?? '—';
    return d.host ? `${d.host}:${d.port ?? ''} / ${d.database ?? ''}` : '—';
  };

  const detailSource = detailSourceId ? sources.find(s => s.id === detailSourceId) : null;
  const detailDetails = detailSource?.connection_details ?? {};

  return (
    <Box sx={{ flex: 1, p: 4, display: 'flex', flexDirection: 'column', gap: 3.5, overflowY: 'auto' }}>
      
      {/* Shell Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', borderBottom: '1px solid', borderColor: 'divider', pb: 2.5 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 'extrabold', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: 1.5, textTransform: 'uppercase' }}>
            <Database className="w-5 h-5 text-gh-accent" />
            {t.sourcesTitle}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
            {t.sourcesSubtitle}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title={t.refreshListTooltip}>
            <IconButton onClick={() => fetchSources()} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px' }}>
              <RefreshCw size={14} />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            onClick={handleStartAdd}
            startIcon={<Plus size={14} />}
            sx={{ bgcolor: '#0078d4', '&:hover': { bgcolor: '#106ebe' }, fontWeight: 600, fontSize: 11, color: '#ffffff', borderRadius: '8px' }}
          >
            {t.addBtn}
          </Button>
        </Box>
      </Box>

      {/* File Upload & Preview Segment */}
      <Card sx={{ bgcolor: 'rgba(0, 120, 212, 0.01)', borderRadius: '8px' }}>
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', borderBottom: '1px solid', borderColor: 'divider', pb: 1.5, mb: 2 }}>
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: 11.5, textTransform: 'uppercase', tracking: '0.05em' }}>
                {t.fileSourcesSection}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                {t.fileSourcesDesc}
              </Typography>
            </Box>
            <IconButton onClick={() => fetchFiles()} size="small" sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '6px' }}>
              <RefreshCw size={12} />
            </IconButton>
          </Box>
          <FileUpload hideHeader />
        </CardContent>
      </Card>

      {/* Active Selection Indicator */}
      <Card sx={{ bgcolor: 'rgba(0, 120, 212, 0.01)', borderRadius: '8px' }}>
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', pb: 1.5, mb: 2 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: 11.5, textTransform: 'uppercase', tracking: '0.05em' }}>
              {t.activeSessionTables}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {t.activeSessionDesc}
            </Typography>
          </Box>
          <Grid container spacing={2.5}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Box className="panel-inset" sx={{ p: 2.5, borderRadius: '6px', minHeight: 140, display: 'flex', flexDirection: 'column', justify: 'space-between' }}>
                <Box>
                  <Typography variant="caption" sx={{ fontWeight: 600, color: 'primary.main', textTransform: 'uppercase', tracking: '0.05em', display: 'block', mb: 1 }}>
                    {t.mainSourceLabel}
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 'extrabold', fontFamily: 'monospace', p: '6px 12px', bgcolor: 'rgba(0, 120, 212, 0.03)', border: '1px solid', borderColor: 'divider', borderRadius: '6px', fontSize: 11 }}>
                    {activeSourceId || t.noActiveSource}
                  </Typography>
                </Box>
                <Box sx={{ mt: 2 }}>
                  <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', display: 'block', mb: 0.5 }}>
                    {t.availableTablesLabel}
                  </Typography>
                  <ul className="text-[11px] list-disc list-inside text-gh-text space-y-0.5 font-mono max-h-[80px] overflow-y-auto pr-1">
                    {(() => {
                      const src = sources.find(s => s.id === activeSourceId);
                      if (src && src.schema) {
                        const tbls = Object.keys(src.schema || {});
                        if (tbls.length === 0) return <li className="text-gh-muted italic">{t.noTablesFoundLabel}</li>;
                        return tbls.map(t => <li key={`active-${t}`} style={{ color: '#0078d4' }}>{t}</li>);
                      }
                      const fileItem = files.find(f => f.id === activeSourceId || f.alias === activeSourceId);
                      if (fileItem) return <li key={`active-file-${fileItem.alias}`} style={{ color: '#0078d4' }}>{fileItem.alias}</li>;
                      return <li className="text-gh-muted italic">{t.emptySelectionLabel}</li>;
                    })()}
                  </ul>
                </Box>
              </Box>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <Box className="panel-inset" sx={{ p: 2.5, borderRadius: '6px', minHeight: 140, display: 'flex', flexDirection: 'column', justify: 'space-between' }}>
                <Box>
                  <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', display: 'block', mb: 0.5 }}>
                    {t.additionalSources} ({selectedSourceIds.length})
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1.5 }}>
                    {t.additionalSourcesDesc}
                  </Typography>
                </Box>
                <Box sx={{ flex: 1, overflowY: 'auto', maxH: 80, pr: 1 }}>
                  {selectedSourceIds.length === 0 ? (
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', fontFamily: 'monospace' }}>
                      {t.noAdditionalSource}
                    </Typography>
                  ) : (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, fontFamily: 'monospace' }}>
                      {selectedSourceIds.map(sid => {
                        const src = sources.find(s => s.id === sid);
                        if (src) {
                          const tbls = Object.keys(src.schema || {});
                          return (
                            <Box key={`sel-${sid}`} sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', bgcolor: 'rgba(0, 120, 212, 0.02)', p: '4px 8px', borderRadius: '4px', border: '1px solid', borderColor: 'divider', fontSize: 10.5 }}>
                              <span style={{ color: '#0078d4', fontWeight: 600 }}>{sid}</span>
                              <span style={{ color: 'var(--color-text)' }}>({tbls.length} {tbls.length === 1 ? t.tableSuffix : t.tablesSuffix})</span>
                            </Box>
                          );
                        }
                        const fileItem = files.find(f => f.id === sid || f.alias === sid);
                        if (fileItem) {
                          return (
                            <Box key={`sel-file-${sid}`} sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', bgcolor: 'rgba(0, 120, 212, 0.02)', p: '4px 8px', borderRadius: '4px', border: '1px solid', borderColor: 'divider', fontSize: 10.5 }}>
                              <span style={{ color: '#0078d4', fontWeight: 600 }}>{fileItem.alias}</span>
                              <span style={{ color: '#0078d4' }}>{t.fileLabel.replace(':', '').trim()}</span>
                            </Box>
                          );
                        }
                        return <div key={`sel-miss-${sid}`} style={{ fontStyle: 'italic', opacity: 0.7 }}>{sid} ({t.notFoundLabel})</div>;
                      })}
                    </Box>
                  )}
                </Box>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Connection details Dialog */}
      <Dialog
        open={!!detailSourceId}
        onClose={closeDetails}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
          <Database size={16} style={{ color: '#0078d4' }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 'extrabold', fontSize: 13, m: 0 }}>
            {t.detailsModalTitle}
          </Typography>
        </DialogTitle>
        <DialogContent sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          {detailSource && (
            <>
              <Grid container spacing={2}>
                <Grid size={6}>
                  <Box className="panel-inset" sx={{ p: 2, borderRadius: '6px' }}>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', display: 'block', mb: 1 }}>
                      {t.metricsLabel}
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 'extrabold', fontSize: 11.5 }}>
                      {detailSource.display_name}
                    </Typography>
                    <Box sx={{ mt: 1.5, display: 'flex', flexDirection: 'column', gap: 1, fontSize: 10.5, color: 'text.secondary' }}>
                      <Box>{t.typeLabel}<Chip label={detailSource.type.toUpperCase()} size="small" sx={{ height: 16, fontSize: 8.5, fontWeight: 600, bgcolor: 'rgba(0, 120, 212, 0.1)', color: '#0078d4', border: 0 }} /></Box>
                      <Box>{t.statusLabel}{detailSource.is_active ? <Chip label={t.active} color="success" size="small" sx={{ height: 16, fontSize: 8.5, fontWeight: 600, border: 0 }} /> : <Chip label={t.passive} color="error" size="small" sx={{ height: 16, fontSize: 8.5, fontWeight: 600, border: 0 }} />}</Box>
                      <Box>{t.tablesLabel}<span style={{ color: '#0078d4', fontWeight: 600, fontFamily: 'monospace' }}>{Object.keys(detailSource.schema || {}).length}</span></Box>
                      <Box sx={{ fontSize: 9.5, opacity: 0.8 }}>{t.lastUpdateLabel}{detailSource.last_schema_update || '—'}</Box>
                    </Box>
                  </Box>
                </Grid>

                <Grid size={6}>
                  <Box className="panel-inset" sx={{ p: 2, borderRadius: '6px' }}>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', display: 'block', mb: 1 }}>
                      {t.serverParamsLabel}
                    </Typography>
                    {detailSource.type === 'sqlite' ? (
                      <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block', wordBreak: 'break-all' }}>
                        {t.fileLabel}<span style={{ color: '#0078d4' }}>{detailDetails.database_path || '—'}</span>
                      </Typography>
                    ) : detailSource.type === 'snowflake' ? (
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, fontFamily: 'monospace', fontSize: 10.5, color: 'text.secondary' }}>
                        <div>Account ID: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.account || '—'}</span></div>
                        <div>Warehouse: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.warehouse || '—'}</span></div>
                        <div>DB: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.database || '—'}</span></div>
                        <div>Schema: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.schema || '—'}</span></div>
                        <div>User: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.user || '—'}</span></div>
                      </Box>
                    ) : detailSource.type === 'bigquery' ? (
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, fontFamily: 'monospace', fontSize: 10.5, color: 'text.secondary' }}>
                        <div>Project ID: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.project_id || '—'}</span></div>
                        <div>JSON Key: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.credentials_json ? t.loadedStatus : '—'}</span></div>
                      </Box>
                    ) : (
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, fontFamily: 'monospace', fontSize: 10.5, color: 'text.secondary' }}>
                        <div>Host: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.host || '—'}</span></div>
                        <div>Port: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.port || '—'}</span></div>
                        <div>DB: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.database || '—'}</span></div>
                        <div>{t.schemaLabel}<span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.schema || '—'}</span></div>
                        <div>User: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.user || '—'}</span></div>
                        <div>{t.dbPasswordLabel}: <span style={{ color: '#0078d4', fontWeight: 600 }}>{detailDetails.password ? '••••••••' : '—'}</span></div>
                      </Box>
                    )}
                  </Box>
                </Grid>
              </Grid>

              <Box className="panel-inset" sx={{ p: 2, borderRadius: '6px', display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between' }}>
                  <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em' }}>
                    {t.labelsCardTitle}
                  </Typography>
                  <Button
                    onClick={handleSaveLabels}
                    disabled={labelsSaving}
                    variant="contained"
                    size="small"
                    sx={{ bgcolor: '#0078d4', '&:hover': { bgcolor: '#106ebe' }, color: '#ffffff', px: 2, height: 24, fontSize: 10, fontWeight: 600 }}
                  >
                    {t.saveBtn}
                  </Button>
                </Box>
                <TextField
                  fullWidth
                  value={labelsInput}
                  onChange={(e) => setLabelsInput(e.target.value)}
                  placeholder={t.labelsInputPlaceholder}
                  sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px' } }}
                />
                {labelsError && <Typography variant="caption" sx={{ color: 'error.main' }}>{labelsError}</Typography>}
                <Typography variant="caption" sx={{ fontSize: 9.5, color: 'text.secondary' }}>
                  {t.labelsDesc}
                </Typography>
              </Box>
            </>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button onClick={closeDetails} variant="outlined" sx={{ borderColor: 'divider', color: 'text.primary' }}>
            {t.closeBtn}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Semantic layer Dialog */}
      <Dialog
        open={!!semanticSourceId}
        onClose={() => setSemanticSourceId(null)}
        maxWidth="md"
        fullWidth
        scroll="paper"
      >
        <DialogTitle sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box sx={{ width: 32, height: 32, borderRadius: '6px', bgcolor: 'rgba(0, 120, 212, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0078d4' }}>
            <Tag size={16} />
          </Box>
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 'extrabold', fontSize: 13, m: 0 }}>
              {t.semanticModalTitle}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.2 }}>
              {t.semanticModalDesc}
            </Typography>
          </Box>
        </DialogTitle>
        <DialogContent sx={{ p: 3 }}>
          {semanticLoading ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 8, gap: 2 }}>
              <CircularProgress size={28} />
              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>{t.loadingSchema}</Typography>
            </Box>
          ) : semanticError ? (
            <Alert severity="error" sx={{ borderRadius: '8px' }}>{semanticError}</Alert>
          ) : Object.keys(semanticMapping).length === 0 ? (
            <Box sx={{ py: 6, color: 'text.secondary', display: 'flex', flexDirection: 'column', alignItems: 'center', justify: 'center' }}>
              <AlertCircle size={28} style={{ opacity: 0.4, marginBottom: 8 }} />
              <Typography variant="body2" sx={{ fontWeight: 600 }}>{t.noTablesFound}</Typography>
              <Typography variant="caption">{t.refreshSchemaFirst}</Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {Object.entries(semanticMapping).map(([tbl, cols]) => (
                <Box key={tbl} sx={{ border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper', borderRadius: '6px', overflow: 'hidden' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'action.hover' }}>
                    <Typography variant="caption" sx={{ fontWeight: 'extrabold', fontFamily: 'monospace', display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Database className="w-3.5 h-3.5 text-gh-accent" />
                      {tbl}
                    </Typography>
                    <Chip label={`${Object.keys(cols).length} ${t.columnCount}`} size="small" sx={{ height: 16, fontSize: 8.5, fontWeight: 600, bgcolor: 'rgba(0, 120, 212, 0.1)', color: '#0078d4' }} />
                  </Box>
                  
                  <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {Object.entries(cols).map(([col, info]) => (
                      <Grid container spacing={2} key={col} sx={{ alignItems: 'center' }}>
                        <Grid size={{ xs: 12, md: 3 }}>
                          <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600, display: 'block', wordBreak: 'break-all' }}>
                            {col}
                          </Typography>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 4.5 }}>
                          <TextField
                            fullWidth
                            value={info.label}
                            onChange={(e) => {
                              setSemanticMapping(prev => ({
                                ...prev,
                                [tbl]: {
                                  ...prev[tbl],
                                  [col]: { ...prev[tbl][col], label: e.target.value }
                                }
                              }));
                            }}
                            placeholder={t.semanticInputAlias}
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px' } }}
                          />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 4.5 }}>
                          <TextField
                            fullWidth
                            value={info.description}
                            onChange={(e) => {
                              setSemanticMapping(prev => ({
                                ...prev,
                                [tbl]: {
                                  ...prev[tbl],
                                  [col]: { ...prev[tbl][col], description: e.target.value }
                                }
                              }));
                            }}
                            placeholder={t.semanticInputDesc}
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px' } }}
                          />
                        </Grid>
                      </Grid>
                    ))}
                  </Box>
                </Box>
              ))}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
          <Button onClick={() => setSemanticSourceId(null)} variant="outlined" sx={{ borderColor: 'divider', color: 'text.primary' }}>
            {t.cancelBtn}
          </Button>
          <Button
            type="primary"
            variant="contained"
            disabled={semanticSaving || semanticLoading}
            onClick={handleSaveSemantic}
            sx={{ bgcolor: '#0078d4', '&:hover': { bgcolor: '#106ebe' }, color: '#ffffff', fontWeight: 600 }}
          >
            {semanticSaving ? t.semanticBtnSaving : t.semanticBtnSave}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Premium Selective Snapshot Table Selection Dialog */}
      <Dialog
        open={tableSelectionOpen}
        onClose={() => setTableSelectionOpen(false)}
        maxWidth="sm"
        fullWidth
        sx={{ '& .MuiDialog-paper': { borderRadius: '12px' } }}
      >
        <DialogTitle sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box sx={{ width: 32, height: 32, borderRadius: '6px', bgcolor: 'rgba(0, 120, 212, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0078d4' }}>
              <Layers size={16} />
            </Box>
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 'extrabold', fontSize: 13, m: 0 }}>
                {t.tableReplicationTitle}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.2 }}>
                {tableSelectionSource?.display_name}
              </Typography>
            </Box>
          </Box>
          <IconButton onClick={() => setTableSelectionOpen(false)} size="small">
            <X size={15} />
          </IconButton>
        </DialogTitle>

        <DialogContent sx={{ p: 2.5, maxHeight: '60vh', display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.4 }}>
            {t.tableReplicationSubtitle}
          </Typography>

          {/* Search Table */}
          <TextField
            fullWidth
            size="small"
            placeholder={t.searchTablesPlaceholder}
            value={tableSearchQuery}
            onChange={(e) => setTableSearchQuery(e.target.value)}
            slotProps={{
               input: {
                 startAdornment: <Search size={14} style={{ marginRight: 8, color: 'var(--color-muted)' }} />
               }
             }}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
          />

          {/* Quick Select Buttons */}
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => {
                const updated = { ...selectedTables };
                Object.keys(tableSelectionSource?.schema ?? {}).forEach(t => {
                  updated[t] = true;
                });
                setSelectedTables(updated);
              }}
              sx={{ borderRadius: '6px', fontSize: 10.5, py: 0.5, px: 1.5, borderColor: 'divider', color: 'text.primary', textTransform: 'none' }}
            >
              {t.selectAll}
            </Button>
            <Button
              size="small"
              variant="outlined"
              onClick={() => {
                const updated = { ...selectedTables };
                Object.keys(tableSelectionSource?.schema ?? {}).forEach(t => {
                  updated[t] = false;
                });
                setSelectedTables(updated);
              }}
              sx={{ borderRadius: '6px', fontSize: 10.5, py: 0.5, px: 1.5, borderColor: 'divider', color: 'text.primary', textTransform: 'none' }}
            >
              {t.clearAllBtn}
            </Button>
          </Box>

          {/* Scrollable list of tables with Checkboxes */}
          <Box sx={{ flex: 1, overflowY: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: '8px', maxHeight: '300px', p: 1, bgcolor: 'action.hover' }}>
            {Object.entries(tableSelectionSource?.schema ?? {})
              .filter(([tblName]) => tblName.toLowerCase().includes(tableSearchQuery.toLowerCase()))
              .map(([tblName, cols]) => (
                <Box
                  key={tblName}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    px: 1.5,
                    py: 0.5,
                    borderRadius: '6px',
                    '&:hover': { bgcolor: 'action.selected' }
                  }}
                >
                  <FormControlLabel
                    control={
                      <Checkbox
                        size="small"
                        checked={!!selectedTables[tblName]}
                        onChange={(e) => {
                          setSelectedTables(prev => ({
                            ...prev,
                            [tblName]: e.target.checked
                          }));
                        }}
                      />
                    }
                    label={
                      <Typography variant="body2" sx={{ fontWeight: 600, fontSize: 12 }}>
                        {tblName}
                      </Typography>
                    }
                  />
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace', fontSize: 9 }}>
                    {(cols as any[]).length} {t.dbColumnSuffix}
                  </Typography>
                </Box>
              ))}

            {Object.keys(tableSelectionSource?.schema ?? {}).filter(t => t.toLowerCase().includes(tableSearchQuery.toLowerCase())).length === 0 && (
              <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', display: 'block', textAlign: 'center', py: 4 }}>
                {t.noTablesFoundLabel}
              </Typography>
            )}
          </Box>
        </DialogContent>

        <DialogActions sx={{ p: 2.5, borderTop: '1px solid', borderColor: 'divider', gap: 1 }}>
          <Button
            onClick={() => setTableSelectionOpen(false)}
            variant="outlined"
            sx={{ borderRadius: '8px', fontSize: 11, fontWeight: 600, px: 2, borderColor: 'divider', color: 'text.primary', textTransform: 'none' }}
          >
            {t.closeBtn}
          </Button>
          <Button
            onClick={() => {
              const chosen = Object.keys(selectedTables).filter(k => selectedTables[k]);
              if (chosen.length === 0) {
                alert(t.selectAtLeastOneTableAlert);
                return;
              }
              setTableSelectionOpen(false);
              runSnapshotReplication(tableSelectionSource, chosen);
            }}
            variant="contained"
            disabled={Object.keys(selectedTables).filter(k => selectedTables[k]).length === 0}
            sx={{ borderRadius: '8px', fontSize: 11, fontWeight: 600, px: 2.5, bgcolor: '#0078d4', '&:hover': { bgcolor: '#106ebe' }, color: '#ffffff', textTransform: 'none' }}
          >
            {t.startReplicationBtn}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Premium Guided Snapshot Progress Dialog */}
      <Dialog
        open={snapshotDialogOpen}
        onClose={snapshotProgress.status !== 'running' ? () => setSnapshotDialogOpen(false) : undefined}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', justify: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box sx={{ width: 32, height: 32, borderRadius: '6px', bgcolor: 'rgba(0, 120, 212, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0078d4' }}>
              <HardDrive size={16} />
            </Box>
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 'extrabold', fontSize: 13, m: 0 }}>
                {t.snapshotPanelTitle}
              </Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.2 }}>
                {snapshotSource?.display_name} → {t.localOfflineStoreLabel}
              </Typography>
            </Box>
          </Box>
          {snapshotProgress.status !== 'running' && (
            <IconButton onClick={() => setSnapshotDialogOpen(false)} size="small">
              <X size={15} />
            </IconButton>
          )}
        </DialogTitle>
        <DialogContent sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          {/* 1. Educational Guided Info Card */}
          <Alert severity="info" icon={<ShieldCheck size={20} />} sx={{ borderRadius: '8px', bgcolor: 'rgba(0, 120, 212, 0.03)', border: '1px solid rgba(0, 120, 212, 0.15)', '& .MuiAlert-message': { width: '100%' } }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: 11, mb: 0.5, color: '#0078d4', textTransform: 'uppercase', letterSpacing: '0.02em' }}>
              {t.howSnapshotWorksTitle}
            </Typography>
            <Typography variant="caption" sx={{ display: 'block', lineHeight: 1.5, color: 'text.secondary' }}>
              {t.howSnapshotWorksDesc}
            </Typography>
          </Alert>

          {/* 2. Visual table-by-table list with live status */}
          <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', overflow: 'hidden', bgcolor: 'background.paper' }}>
            <Box sx={{ px: 2.5, py: 1.5, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'action.hover', display: 'flex', alignItems: 'center', justify: 'space-between' }}>
              <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', tracking: '0.03em', display: 'flex', alignItems: 'center', gap: 1 }}>
                <Database size={13} style={{ color: '#0078d4' }} />
                {t.discoveredTablesReplicationStatus}
              </Typography>
              {snapshotProgress.discoveredTables.length > 0 && (
                <Chip 
                  label={`${snapshotProgress.discoveredTables.length} ${snapshotProgress.discoveredTables.length === 1 ? t.tableSuffix : t.tablesSuffix}`} 
                  size="small" 
                  sx={{ height: 18, fontSize: 8.5, fontWeight: 700, bgcolor: 'rgba(0, 120, 212, 0.1)', color: '#0078d4' }} 
                />
              )}
            </Box>

            <Box sx={{ p: 2.5, maxH: 220, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 1.2 }}>
              {snapshotProgress.discoveredTables.length === 0 ? (
                <Box sx={{ py: 3, textAlign: 'center', color: 'text.secondary' }}>
                  <CircularProgress size={18} sx={{ mb: 1 }} />
                  <Typography variant="caption" sx={{ display: 'block', fontStyle: 'italic' }}>
                    {t.scanningAnalyzingTables}
                  </Typography>
                </Box>
              ) : (
                <Grid container spacing={1.5}>
                  {snapshotProgress.discoveredTables.map((tName) => {
                    const statusInfo = snapshotProgress.completedTables[tName] || { rows: 0, indexes: 0, status: 'pending' };
                    let statusBg = 'rgba(255, 255, 255, 0.02)';
                    let statusBorder = 'divider';
                    let statusColor = 'text.secondary';
                    let statusText = t.pendingStatus;
                    let statusIcon = <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'text.disabled' }} />;

                    if (statusInfo.status === 'running') {
                      statusBg = 'rgba(0, 120, 212, 0.03)';
                      statusBorder = '#0078d4';
                      statusColor = '#0078d4';
                      statusText = t.copyingRowsStatus.replace('{rows}', String(statusInfo.rows));
                      statusIcon = <CircularProgress size={8} color="inherit" />;
                    } else if (statusInfo.status === 'completed') {
                      statusBg = 'rgba(46, 125, 50, 0.03)';
                      statusBorder = 'rgba(46, 125, 50, 0.25)';
                      statusColor = 'success.main';
                      statusText = t.successRowsIdxStatus.replace('{rows}', String(statusInfo.rows)).replace('{indexes}', String(statusInfo.indexes));
                      statusIcon = <ShieldCheck size={10} style={{ color: 'var(--color-success)' }} />;
                    } else if (statusInfo.status === 'failed') {
                      statusBg = 'rgba(211, 47, 47, 0.03)';
                      statusBorder = 'rgba(211, 47, 47, 0.25)';
                      statusColor = 'error.main';
                      statusText = t.failedStatus;
                      statusIcon = <AlertCircle size={10} style={{ color: 'var(--color-error)' }} />;
                    }

                    return (
                      <Grid size={{ xs: 12, sm: 6 }} key={`snapshot-tab-${tName}`}>
                        <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', p: '6px 12px', border: '1px solid', borderColor: statusBorder, bgcolor: statusBg, borderRadius: '6px', fontSize: 10.5 }}>
                          <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{tName}</span>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: statusColor, fontWeight: 700, fontSize: 9.5 }}>
                            {statusIcon}
                            <span>{statusText}</span>
                          </Box>
                        </Box>
                      </Grid>
                    );
                  })}
                </Grid>
              )}
            </Box>
          </Box>

          {/* 3. Progress bars and live counts */}
          {snapshotProgress.discoveredTables.length > 0 && (
            <Box className="panel-inset" sx={{ p: 2, borderRadius: '8px', display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Box sx={{ display: 'flex', justify: 'space-between', alignItems: 'center', fontSize: 11, fontWeight: 600 }}>
                <span>
                  {t.overallReplicationProgress}
                </span>
                <span style={{ color: '#0078d4' }}>
                  {snapshotProgress.status === 'completed' 
                    ? t.completedStatus
                    : `${snapshotProgress.currentTableIndex + 1} / ${snapshotProgress.discoveredTables.length} ${snapshotProgress.discoveredTables.length === 1 ? t.tableSuffix : t.tablesSuffix}`}
                </span>
              </Box>

              {/* Progress bar */}
              <Box sx={{ height: 6, width: '100%', bgcolor: 'divider', borderRadius: '3px', overflow: 'hidden' }}>
                <Box 
                   sx={{ 
                    height: '100%', 
                    bgcolor: snapshotProgress.status === 'completed' ? 'success.main' : '#0078d4', 
                    borderRadius: '3px', 
                    transition: 'width 0.3s ease', 
                    width: `${((snapshotProgress.status === 'completed' ? snapshotProgress.discoveredTables.length : snapshotProgress.currentTableIndex) / snapshotProgress.discoveredTables.length) * 100}%` 
                  }} 
                />
              </Box>
            </Box>
          )}

          {/* 4. Live log outputs console */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.8 }}>
            <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.03em' }}>
              {t.liveOperationLogsConsole}
            </Typography>
            <Box 
              sx={{ 
                p: 2, 
                bgcolor: 'black', 
                color: '#00ff00', 
                fontFamily: 'monospace', 
                fontSize: 10, 
                borderRadius: '6px', 
                minHeight: 110, 
                maxHeight: 140, 
                overflowY: 'auto',
                border: '1px solid',
                borderColor: 'divider',
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5
              }}
              ref={(el: any) => { if (el) el.scrollTop = el.scrollHeight; }}
            >
              {snapshotProgress.logs.map((log, idx) => (
                <div key={`log-${idx}`} style={{ wordBreak: 'break-all' }}>{log}</div>
              ))}
            </Box>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5, borderTop: '1px solid', borderColor: 'divider', gap: 1 }}>
          {snapshotProgress.status !== 'running' && (
            <Button onClick={() => setSnapshotDialogOpen(false)} variant="contained" sx={{ bgcolor: '#0078d4', '&:hover': { bgcolor: '#106ebe' }, color: '#ffffff', fontWeight: 600 }}>
              {t.closeBtn}
            </Button>
          )}
          {snapshotProgress.status === 'running' && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pr: 1 }}>
              <CircularProgress size={14} />
              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                {snapshotProgress.message}
              </Typography>
            </Box>
          )}
        </DialogActions>
      </Dialog>

      {/* Main Grid View */}
      <Grid container spacing={3}>
        
        {/* Left Side: Master Connections list */}
        <Grid size={{ xs: 12, lg: showForm ? 7 : 12 }} sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          {sources.length === 0 && (
            <Box className="panel p-12" sx={{ textCenter: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', borderStyle: 'dashed', borderRadius: '8px', bgcolor: 'rgba(0, 120, 212, 0.02)' }}>
              <Database className="w-10 h-10 mb-3 opacity-30 text-gh-muted" />
              <Typography variant="body2" sx={{ fontWeight: 600 }}>{t.noDatabaseConnected}</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary', mt: 0.5 }}>{t.startAnalysisPrompt}</Typography>
            </Box>
          )}

          {sources.map((src) => {
            const isSelected = activeSourceId === src.id;
            const tableCount = Object.keys(src.schema ?? {}).length;
            const accentColor = src.connection_details?.is_snapshot ? '#800080' : colorFor(src.type);
            const isActive = src.is_active ?? true;

            return (
              <Card
                key={src.id}
                onClick={() => setActiveSourceId(src.id)}
                sx={{
                  cursor: 'pointer',
                  borderColor: isSelected ? '#0078d4' : 'divider',
                  bgcolor: isSelected ? 'rgba(0, 120, 212, 0.04)' : 'background.paper',
                  borderLeft: `4px solid ${accentColor}`,
                  borderRadius: '8px',
                  transition: 'all 0.2s',
                  opacity: !isActive ? 0.7 : 1,
                  '&:hover': {
                    borderColor: isSelected ? '#0078d4' : 'text.secondary',
                  }
                }}
              >
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', gap: 2, flexWrap: 'wrap' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minWidth: 0 }}>
                      <Box sx={{ width: 36, height: 36, borderRadius: '8px', border: '1px solid', borderColor: isSelected ? 'rgba(0, 120, 212, 0.3)' : 'divider', display: 'flex', alignItems: 'center', justifyContent: 'center', color: isSelected ? '#0078d4' : 'text.secondary', bgcolor: isSelected ? 'rgba(0, 120, 212, 0.08)' : 'background.default' }}>
                        {src.connection_details?.is_snapshot ? (
                          <HardDrive className="w-4.5 h-4.5 text-[#a371f7]" />
                        ) : (
                          <Database className="w-4.5 h-4.5" />
                        )}
                      </Box>
                      <Box sx={{ minWidth: 0 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                          <Typography variant="body2" sx={{ fontWeight: 'extrabold', fontSize: 12 }}>{src.display_name}</Typography>
                          <Chip label={src.connection_details?.is_snapshot ? 'SNAPSHOT' : labelTextFor(src.type).toUpperCase()} size="small" sx={{ height: 16, fontSize: 8, fontWeight: 600, bgcolor: src.connection_details?.is_snapshot ? 'rgba(163, 113, 247, 0.15)' : 'rgba(0, 120, 212, 0.1)', color: src.connection_details?.is_snapshot ? '#a371f7' : '#0078d4', border: 0 }} />
                          {!isActive && <Chip label={t.passive} size="small" sx={{ height: 16, fontSize: 8, fontWeight: 600, bgcolor: 'rgba(255, 255, 255, 0.08)', color: 'text.secondary', border: 0 }} />}
                          {isSelected && <Chip label={t.active} size="small" color="success" sx={{ height: 16, fontSize: 8, fontWeight: 600, border: 0 }} />}
                        </Box>
                        <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace', display: 'block', mt: 0.5 }} title={hostLabel(src)}>
                          {hostLabel(src)}
                        </Typography>
                        {src.labels && src.labels.length > 0 && (
                          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
                            {src.labels.slice(0, 3).map((label: string) => (
                              <Chip key={label} label={label} size="small" sx={{ height: 14, fontSize: 7.5, fontWeight: 600, bgcolor: 'action.hover', border: '1px solid', borderColor: 'divider', color: 'text.secondary' }} />
                            ))}
                            {src.labels.length > 3 && (
                              <span style={{ fontSize: 8, color: '#9aa6bf', fontWeight: 600 }}>+{src.labels.length - 3}</span>
                            )}
                          </Box>
                        )}
                      </Box>
                    </Box>

                    {/* Actions Toolbar */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }} onClick={(e) => e.stopPropagation()}>
                      <Tooltip title={t.viewDetailsTooltip}>
                        <IconButton size="small" onClick={(e) => openDetails(e, src.id)}>
                          <Eye size={13.5} />
                        </IconButton>
                      </Tooltip>

                      <Tooltip title={t.semanticLayerTooltip}>
                        <IconButton size="small" onClick={(e) => openSemanticModal(e, src.id)}>
                          <Tag size={13.5} />
                        </IconButton>
                      </Tooltip>

                      <Tooltip title={t.cloneConnectionTooltip}>
                        <IconButton size="small" onClick={(e) => handleClone(e, src.id)} disabled={cloningId === src.id}>
                          {cloningId === src.id ? <CircularProgress size={13.5} /> : <Copy size={13.5} />}
                        </IconButton>
                      </Tooltip>

                      <Tooltip title={isActive ? t.toggleStatusActiveTooltip : t.toggleStatusPassiveTooltip}>
                        <IconButton size="small" onClick={(e) => handleToggleStatus(e, src.id, isActive)} disabled={togglingId === src.id}>
                          {togglingId === src.id ? <CircularProgress size={13.5} /> : <Power size={13.5} style={{ color: isActive ? 'inherit' : '#0078d4' }} />}
                        </IconButton>
                      </Tooltip>

                      <Tooltip title={t.editConnectionTooltip}>
                        <IconButton size="small" onClick={(e) => handleStartEdit(e, src)}>
                          <Edit3 size={13.5} />
                        </IconButton>
                      </Tooltip>

                      {src.type !== 'sqlite' && !src.connection_details?.is_snapshot && (
                        <Tooltip title={t.takeSnapshotTooltip}>
                          <IconButton size="small" onClick={(e) => handleStartSnapshotFlow(e, src.id)} disabled={snapshotting === src.id}>
                            {snapshotting === src.id ? <CircularProgress size={13.5} /> : <HardDrive size={13.5} />}
                          </IconButton>
                        </Tooltip>
                      )}

                      <Tooltip title={t.refreshSchemaTooltip}>
                        <IconButton size="small" onClick={(e) => handleRefreshSchema(e, src.id)} disabled={refreshing === src.id}>
                          {refreshing === src.id ? <CircularProgress size={13.5} /> : <RefreshCw size={13.5} />}
                        </IconButton>
                      </Tooltip>

                      <Tooltip title={t.deleteDatabaseTooltip}>
                        <IconButton size="small" color="error" onClick={(e) => handleDelete(e, src.id)} disabled={deleting === src.id}>
                          {deleting === src.id ? <CircularProgress size={13.5} color="inherit" /> : <Trash2 size={13.5} />}
                        </IconButton>
                      </Tooltip>

                      {!isSelected && (
                        <Button
                          size="small"
                          onClick={() => setActiveSourceId(src.id)}
                          sx={{ fontSize: 9.5, fontWeight: 600, border: '1px solid', borderColor: 'divider', color: 'text.secondary', borderRadius: '6px', py: 0.3 }}
                        >
                          {t.selectSourceBtn}
                        </Button>
                      )}
                    </Box>
                  </Box>

                  {/* Schema Analysis details Accordion */}
                  <Accordion
                    disableGutters
                    elevation={0}
                    sx={{ mt: 1.5, borderTop: '1px solid', borderColor: 'divider', bgcolor: 'transparent', '&:before': { display: 'none' } }}
                  >
                    <AccordionSummary
                      expandIcon={<ChevronDown size={14} />}
                      sx={{ minHeight: 'auto', p: 0, '& .MuiAccordionSummary-content': { my: 1 } }}
                    >
                      <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em' }}>
                        {t.schemaAnalysis} ({tableCount} {t.tablesDetected})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails sx={{ p: 0, pb: 1 }}>
                      {tableCount === 0 ? (
                        <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', display: 'block', pt: 1 }}>
                          {t.noTablesDetected}
                        </Typography>
                      ) : (
                        <Grid container spacing={1.5} sx={{ pt: 1 }}>
                          {Object.entries(src.schema).map(([tbl, cols]) => (
                            <Grid size={{ xs: 12, sm: 6 }} key={tbl}>
                              <Box className="panel-inset" sx={{ p: 1.5, borderRadius: '8px', bgcolor: 'rgba(0, 120, 212, 0.02)', border: '1px solid', borderColor: 'divider' }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', borderBottom: '1px solid', borderColor: 'divider', pb: 0.5, mb: 1 }}>
                                  <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: 10.5 }}>{tbl}</span>
                                  <span style={{ fontSize: 9, color: '#9aa6bf', fontFamily: 'monospace' }}>{(cols as string[]).length} {t.dbColumnSuffix}</span>
                                </Box>
                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                  {(cols as string[]).map(col => (
                                    <span key={col} style={{ fontFamily: 'monospace', padding: '1px 5px', fontSize: 9, color: '#9aa6bf', backgroundColor: 'rgba(0, 120, 212, 0.01)', border: '1px solid rgba(0, 120, 212, 0.15)', borderRadius: '3px' }}>
                                      {col}
                                    </span>
                                  ))}
                                </Box>
                              </Box>
                            </Grid>
                          ))}
                        </Grid>
                      )}
                    </AccordionDetails>
                  </Accordion>

                </CardContent>
              </Card>
            );
          })}
        </Grid>

        {/* Right Side: Setup & Edit Connection form */}
        {showForm && (
          <Grid size={{ xs: 12, lg: 5 }}>
            <Card sx={{ bgcolor: 'background.paper', borderRadius: '8px', border: '1px solid', borderColor: 'divider' }}>
              <CardContent sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                {/* Form Header */}
                <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', borderBottom: '1px solid', borderColor: 'divider', pb: 1.5 }}>
                  <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.primary', textTransform: 'uppercase', tracking: '0.05em', display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Database className="w-3.5 h-3.5 text-gh-accent" />
                    {editingSourceId ? t.editConnectionTooltip : t.addBtn}
                  </Typography>
                  <IconButton onClick={() => { setShowForm(false); setEditingSourceId(null); }} size="small">
                    <X size={15} />
                  </IconButton>
                </Box>

                {/* Toggle group for Database types */}
                {!editingSourceId && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                      {t.dbTypeLabel}
                    </Typography>
                    <ToggleButtonGroup
                      value={formValues.type}
                      exclusive
                      onChange={(_, v) => v && handleTypeChange(v as DbType)}
                      fullWidth
                      sx={{
                        border: '1px solid rgba(0, 120, 212, 0.15)', borderRadius: '8px', p: 0.5, bgcolor: 'rgba(0, 120, 212, 0.01)',
                        '& .MuiToggleButton-root': {
                          border: 0, borderRadius: '6px', py: 1, textTransform: 'none', color: 'text.secondary', fontWeight: 600, fontSize: 10,
                          '&.Mui-selected': { bgcolor: 'rgba(0, 120, 212, 0.1)', color: '#60cdff' }
                        }
                      }}
                    >
                      {DB_TYPE_OPTIONS.map(opt => {
                        const IconComp = opt.icon;
                        return (
                          <ToggleButton value={opt.value} key={opt.value}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
                              <IconComp size={16} style={{ color: opt.color }} />
                              <span style={{ fontSize: 8.5, marginTop: 2 }}>{opt.label}</span>
                            </Box>
                          </ToggleButton>
                        );
                      })}
                    </ToggleButtonGroup>
                  </Box>
                )}

                {/* Edit warnings */}
                {editingSourceId && (
                  <Alert severity="info" sx={{ borderRadius: '8px', fontSize: 11, py: 0.5 }}>
                    <span style={{ fontWeight: 'extrabold', display: 'block' }}>{t.editModeActive}</span>
                    {t.editModeDesc.replace('veritabanının', labelTextFor(formValues.type))}
                  </Alert>
                )}

                {/* Spaced forms */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                      {t.displayConnectionNameLabel}
                    </Typography>
                    <TextField
                      fullWidth
                      value={formValues.display_name}
                      onChange={e => setFormValues(p => ({ ...p, display_name: e.target.value }))}
                      placeholder={t.displayConnectionNamePlaceholder}
                      sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                    />
                  </Box>

                  {formValues.type === 'sqlite' ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em' }}>
                          {t.sqlitePathLabel}
                        </Typography>
                        {localSqliteFiles.length > 0 && (
                          <Button
                            variant="text"
                            size="small"
                            onClick={() => setShowManualPathInput(!showManualPathInput)}
                            sx={{ fontSize: 9, p: 0, minWidth: 'auto', textTransform: 'none', color: '#0078d4' }}
                          >
                            {showManualPathInput 
                              ? (language === 'tr' ? 'Listeden Seç' : 'Select from List')
                              : (language === 'tr' ? 'Manuel Yol Gir' : 'Enter Manually')}
                          </Button>
                        )}
                      </Box>
                      {loadingSqliteFiles ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
                          <CircularProgress size={16} />
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            {language === 'tr' ? 'SQLite dosyaları listeleniyor...' : 'Listing SQLite files...'}
                          </Typography>
                        </Box>
                      ) : (showManualPathInput || localSqliteFiles.length === 0) ? (
                        <TextField
                          fullWidth
                          value={formValues.database_path}
                          onChange={e => setFormValues(p => ({ ...p, database_path: e.target.value }))}
                          placeholder={t.sqlitePathPlaceholder}
                          slotProps={{
                            input: {
                              startAdornment: <HardDrive size={13.5} style={{ marginRight: 6, color: '#0078d4' }} />
                            }
                          }}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        />
                      ) : (
                        <TextField
                          select
                          fullWidth
                          value={formValues.database_path}
                          onChange={e => setFormValues(p => ({ ...p, database_path: e.target.value }))}
                          slotProps={{
                            input: {
                              startAdornment: <HardDrive size={13.5} style={{ marginRight: 6, color: '#0078d4' }} />
                            },
                            select: {
                              native: true
                            }
                          }}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        >
                          {!formValues.database_path && (
                            <option value="">{language === 'tr' ? '-- Bir dosya seçin --' : '-- Select a file --'}</option>
                          )}
                          {localSqliteFiles.map((f) => (
                            <option key={f} value={f}>
                              {f}
                            </option>
                          ))}
                        </TextField>
                      )}

                      {/* SQLite File Picker (File Manager) Upload */}
                      <Box sx={{ mt: 1.5 }}>
                        <input
                          type="file"
                          accept=".db,.sqlite,.sqlite3"
                          style={{ display: 'none' }}
                          id="sqlite-file-picker-input"
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (!file) return;
                            
                            const formData = new FormData();
                            formData.append('file', file);
                            
                            setUploadingSqlite(true);
                            setUploadSqliteError(null);
                            try {
                              const res = await fetch(`${API}/api/sources/upload-sqlite`, {
                                method: 'POST',
                                body: formData
                              });
                              if (res.ok) {
                                const data = await res.json();
                                setFormValues(prev => ({ ...prev, database_path: data.database_path }));
                                setLocalSqliteFiles(prev => {
                                  if (prev.includes(data.database_path)) return prev;
                                  return [...prev, data.database_path].sort();
                                });
                                setShowManualPathInput(false);
                              } else {
                                const err = await res.json();
                                setUploadSqliteError(err.detail || (language === 'tr' ? 'Dosya yüklenemedi.' : 'Failed to upload file.'));
                              }
                            } catch (err: any) {
                              setUploadSqliteError(err.message || (language === 'tr' ? 'Bağlantı hatası.' : 'Connection error.'));
                            } finally {
                              setUploadingSqlite(false);
                              e.target.value = '';
                            }
                          }}
                        />
                        <label htmlFor="sqlite-file-picker-input">
                          <Button
                            variant="outlined"
                            component="span"
                            fullWidth
                            disabled={uploadingSqlite}
                            startIcon={uploadingSqlite ? <CircularProgress size={14} color="inherit" /> : <Upload size={14} />}
                            sx={{
                              borderStyle: 'dashed',
                              borderRadius: '8px',
                              borderColor: 'divider',
                              textTransform: 'none',
                              fontSize: 10.5,
                              py: 0.8,
                              color: 'text.secondary',
                              '&:hover': {
                                borderColor: '#0078d4',
                                bgcolor: 'rgba(0, 120, 212, 0.04)'
                              }
                            }}
                          >
                            {uploadingSqlite 
                              ? (language === 'tr' ? 'Dosya yükleniyor...' : 'Uploading file...') 
                              : (language === 'tr' ? 'Bilgisayardan SQLite Dosyası Seç (.db, .sqlite)' : 'Select SQLite File from Computer (.db, .sqlite)')}
                          </Button>
                        </label>
                        {uploadSqliteError && (
                          <Typography variant="caption" color="error" sx={{ display: 'block', mt: 0.5, fontSize: 9.5 }}>
                            {uploadSqliteError}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                  ) : formValues.type === 'snowflake' ? (
                    <>
                      <Grid container spacing={2}>
                        <Grid size={12}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.snowflakeAccountIdLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.account}
                              onChange={e => setFormValues(p => ({ ...p, account: e.target.value }))}
                              placeholder="e.g. xy12345.us-east-2"
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                      </Grid>

                      <Grid container spacing={2}>
                        <Grid size={6}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.databaseNameLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.database}
                              onChange={e => setFormValues(p => ({ ...p, database: e.target.value }))}
                              placeholder="e.g. ANALYTICS_DB"
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                        <Grid size={6}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.schemaNameLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.schema}
                              onChange={e => setFormValues(p => ({ ...p, schema: e.target.value }))}
                              placeholder="e.g. PUBLIC"
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                      </Grid>

                      <Grid container spacing={2}>
                        <Grid size={12}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              Warehouse
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.warehouse}
                              onChange={e => setFormValues(p => ({ ...p, warehouse: e.target.value }))}
                              placeholder="e.g. COMPUTE_WH"
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                      </Grid>

                      <Grid container spacing={2}>
                        <Grid size={6}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.dbUserLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.user}
                              onChange={e => setFormValues(p => ({ ...p, user: e.target.value }))}
                              placeholder="e.g. user_name"
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                        <Grid size={6}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.dbPasswordLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              type="password"
                              value={formValues.password}
                              onChange={e => setFormValues(p => ({ ...p, password: e.target.value }))}
                              placeholder={editingSourceId ? t.passwordPlaceholderEdit : t.passwordPlaceholderNew}
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                      </Grid>
                    </>
                  ) : formValues.type === 'bigquery' ? (
                    <>
                      <Grid container spacing={2}>
                        <Grid size={12}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.googleCloudProjectIdLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.project_id}
                              onChange={e => setFormValues(p => ({ ...p, project_id: e.target.value }))}
                              placeholder="e.g. my-gcp-project"
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                      </Grid>

                      <Grid container spacing={2}>
                        <Grid size={12}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.serviceAccountKeyJsonLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              multiline
                              rows={5}
                              value={formValues.credentials_json}
                              onChange={e => setFormValues(p => ({ ...p, credentials_json: e.target.value }))}
                              placeholder='{ "type": "service_account", ... }'
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontFamily: 'monospace', fontSize: 11 } }}
                            />
                          </Box>
                        </Grid>
                      </Grid>
                    </>
                  ) : (
                    <>
                      <Grid container spacing={2}>
                        <Grid size={8}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.serverHostLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.host}
                              onChange={e => setFormValues(p => ({ ...p, host: e.target.value }))}
                              placeholder={t.serverHostPlaceholder}
                              slotProps={{
                                input: {
                                  startAdornment: <Server size={13.5} style={{ marginRight: 6, color: '#0078d4' }} />
                                }
                              }}
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                        <Grid size={4}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.serverPortLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.port}
                              onChange={e => setFormValues(p => ({ ...p, port: e.target.value }))}
                              placeholder={DEFAULT_PORTS[formValues.type]}
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                      </Grid>

                      <Grid container spacing={2}>
                        <Grid size={6}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.databaseNameLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.database}
                              onChange={e => setFormValues(p => ({ ...p, database: e.target.value }))}
                              placeholder={formValues.type === 'sap_s4hana' ? 'HDB' : t.databaseNamePlaceholder}
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                        <Grid size={6}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.schemaNameLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.schema}
                              onChange={e => setFormValues(p => ({ ...p, schema: e.target.value }))}
                              placeholder={formValues.type === 'sap_s4hana' ? 'S4H' : t.schemaNamePlaceholder}
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                      </Grid>

                      <Grid container spacing={2}>
                        <Grid size={6}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.dbUserLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              value={formValues.user}
                              onChange={e => setFormValues(p => ({ ...p, user: e.target.value }))}
                              placeholder={t.dbUserPlaceholder}
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                        <Grid size={6}>
                          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', mb: 0.5 }}>
                              {t.dbPasswordLabel}
                            </Typography>
                            <TextField
                              fullWidth
                              type="password"
                              value={formValues.password}
                              onChange={e => setFormValues(p => ({ ...p, password: e.target.value }))}
                              placeholder={editingSourceId ? t.passwordPlaceholderEdit : t.passwordPlaceholderNew}
                              sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                            />
                          </Box>
                        </Grid>
                      </Grid>
                    </>
                  )}
                </Box>

                {/* Connection Validation alerts */}
                {testResult && (
                  <Alert severity={testResult.success ? 'success' : 'error'} sx={{ borderRadius: '8px', fontSize: 11, py: 0.5 }}>
                    {testResult.message}
                  </Alert>
                )}

                {saveError && (
                  <Alert severity="error" sx={{ borderRadius: '8px', fontSize: 11, py: 0.5 }}>
                    {saveError}
                  </Alert>
                )}

                {/* Form Buttons */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                  <Button
                    onClick={handleTest}
                    disabled={testing}
                    variant="outlined"
                    startIcon={!testing && <Play size={14} />}
                    sx={{ width: '100%', borderRadius: '8px', borderColor: 'divider', color: 'text.primary', fontWeight: 600, fontSize: 11, py: 1 }}
                  >
                    {testing ? <CircularProgress size={14} color="inherit" /> : t.testConnectionBtn}
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={!testResult?.success || saving}
                    variant="contained"
                    startIcon={!saving && <Save size={14} />}
                    sx={{
                      width: '100%', borderRadius: '8px', bgcolor: testResult?.success ? 'success.main' : 'action.disabledBackground',
                      color: testResult?.success ? '#ffffff' : 'text.disabled', fontWeight: 600, fontSize: 11, py: 1.2,
                      '&:hover': { bgcolor: testResult?.success ? 'success.dark' : 'action.disabledBackground' }
                    }}
                  >
                    {saving ? <CircularProgress size={14} color="inherit" /> : (editingSourceId ? t.updateConnectionBtn : t.saveConnectionBtnLong)}
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Right Side: Setup new card when showForm is False */}
        {!showForm && (
          <Grid size={{ xs: 12, lg: sources.length === 0 ? 12 : 4 }} sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            <Card
              onClick={handleStartAdd}
              sx={{
                borderStyle: 'dashed', cursor: 'pointer', borderColor: 'divider', bgcolor: 'rgba(0, 120, 212, 0.01)',
                transition: 'all 0.2s', borderRadius: '8px', textAlign: 'center', p: 3,
                '&:hover': { borderColor: '#0078d4', bgcolor: 'rgba(0, 120, 212, 0.04)' }
              }}
            >
              <Box sx={{ width: 40, height: 40, borderRadius: '50%', border: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'text.secondary', mx: 'auto', mb: 2 }}>
                <Plus className="w-5 h-5" />
              </Box>
              <Typography variant="body2" sx={{ fontWeight: 'extrabold', textTransform: 'uppercase', fontSize: 11, tracking: '0.05em' }}>{t.addNewSourceCard}</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1, maxWidth: 200, mx: 'auto', lineHeight: 1.4 }}>
                {t.addNewSourcePrompt}
              </Typography>
            </Card>

            <Card sx={{ bgcolor: 'rgba(0, 120, 212, 0.01)', borderRadius: '8px', border: '1px solid', borderColor: 'divider' }}>
              <CardContent sx={{ p: 2.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, borderBottom: '1px solid', borderColor: 'divider', pb: 1, mb: 1.5 }}>
                  <ShieldCheck className="w-4 h-4 text-gh-accent" />
                  <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.primary', textTransform: 'uppercase', tracking: '0.05em' }}>
                    {t.securitySectionTitle}
                  </Typography>
                </Box>
                <ul className="text-[11px] text-gh-muted leading-relaxed space-y-2 list-none p-0 m-0 select-none">
                  <li className="flex items-start gap-2">
                    <span style={{ color: '#0078d4', fontWeight: 600 }}>•</span>
                    <span>{t.securityPoint1}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span style={{ color: '#0078d4', fontWeight: 600 }}>•</span>
                    <span>{t.securityPoint2}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span style={{ color: '#0078d4', fontWeight: 600 }}>•</span>
                    <span>{t.securityPoint3}</span>
                  </li>
                </ul>
              </CardContent>
            </Card>
          </Grid>
        )}

      </Grid>
      
    </Box>
  );
};

export default SourceManager;


