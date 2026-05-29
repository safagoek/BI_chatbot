import React, { useState } from 'react';
import { useBIStore, BACKEND_BASE } from '../context/store';
import { translations } from '../context/translations';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, Trash2, FileSpreadsheet, Loader2, Eye } from 'lucide-react';
import { useTheme } from '@mui/material/styles';
import {
  List, ListItem, ListItemSecondaryAction, Card, CardContent, Grid,
  Typography, Box, IconButton, Tooltip, Chip, Alert,
  TableContainer, Table, TableHead, TableRow, TableCell, TableBody, TablePagination, Paper
} from '@mui/material';

interface FileUploadProps {
  hideHeader?: boolean;
}

export const FileUpload: React.FC<FileUploadProps> = ({ hideHeader = false }) => {
  const muiTheme = useTheme();
  const isDark = muiTheme.palette.mode === 'dark';
  const { files, fetchFiles, deleteFile, activeSourceId, setActiveSourceId, language } = useBIStore();
  const t = translations[language];

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  
  // Preview states
  const [previewData, setPreviewData] = useState<{
    columns: string[];
    rows: any[][];
    row_count: number;
    alias: string;
    id: string;
    schema: Record<string, string>;
  } | null>(null);

  // Pagination states
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(8);

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  // Automatically fetch file preview when activeSourceId changes
  React.useEffect(() => {
    const activeFile = files.find(f => f.id === activeSourceId);
    if (activeFile) {
      const fetchPreview = async () => {
        setUploading(true);
        setUploadError(null);
        try {
          const res = await fetch(`${BACKEND_BASE}/api/files/${activeSourceId}/preview`);
          if (res.ok) {
            const data = await res.json();
            setPreviewData({
              columns: data.preview.columns,
              rows: data.preview.rows,
              row_count: data.preview.row_count,
              alias: data.preview.alias,
              id: data.preview.id,
              schema: data.preview.schema
            });
            setPage(0);
          } else {
            const err = await res.json();
            setUploadError(err.detail || (language === 'tr' ? 'Ön izleme yükleme hatası.' : 'Preview loading error.'));
          }
        } catch (err: any) {
          setUploadError(err.message || (language === 'tr' ? 'Ön izleme alınırken bağlantı hatası oluştu.' : 'Connection error occurred while retrieving preview.'));
        } finally {
          setUploading(false);
        }
      };
      fetchPreview();
    } else {
      setPreviewData(null);
    }
  }, [activeSourceId, files, language]);

  React.useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const onDrop = async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const file = acceptedFiles[0];
    
    // Autopopulate alias
    const fileBaseName = file.name.split('.')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_');
    setUploadError(null);
    setPreviewData(null);
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('alias', fileBaseName);
    
    setUploading(true);
    
    try {
      const response = await fetch(`${BACKEND_BASE}/api/files/upload`, {
        method: 'POST',
        body: formData,
      });
      
      const result = response.ok ? await response.json() : null;
      
      if (!response.ok || !result) {
        const errDetail = result?.detail || (language === 'tr' ? 'Dosya yükleme hatası.' : 'File upload error.');
        throw new Error(errDetail);
      }
      
      setPreviewData({
        columns: result.preview.columns,
        rows: result.preview.rows,
        row_count: result.preview.row_count,
        alias: result.metadata.alias,
        id: result.metadata.id,
        schema: result.metadata.schema
      });
      
      await fetchFiles();
      // Select uploaded file automatically
      setActiveSourceId(result.metadata.id);
      
    } catch (err: any) {
      setUploadError(err.message || (language === 'tr' ? 'Bilinmeyen bir hata oluştu.' : 'An unknown error occurred.'));
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteFile = (e: React.MouseEvent, id: string, name: string) => {
    e.stopPropagation();
    if (!window.confirm(language === 'tr' ? `"${name}" dosyasını silmek istediğinizden emin misiniz?` : `Are you sure you want to delete file "${name}"?`)) return;
    try {
      deleteFile(id);
    } catch (err: any) {
      alert(language === 'tr' ? 'Dosya silinirken hata oluştu.' : 'Error occurred while deleting file.');
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: {
      'text/csv': ['.csv'],
      'text/tab-separated-values': ['.tsv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls']
    }
  });

  // Map rows to Material UI Table structure
  const tableData = previewData
    ? previewData.rows.map((row, rIdx) => {
        const item: Record<string, any> = { id: rIdx };
        previewData.columns.forEach((col, cIdx) => {
          item[col] = row[cIdx];
        });
        return item;
      })
    : [];

  const visibleRows = React.useMemo(() => {
    return tableData.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
  }, [tableData, page, rowsPerPage]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3.5, width: '100%' }}>
      
      {/* View Header */}
      {!hideHeader && (
        <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', borderBottom: '1px solid', borderColor: 'divider', pb: 2.5 }}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 'extrabold', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: 1.5, textTransform: 'uppercase' }}>
              <FileSpreadsheet className="w-5 h-5 text-gh-accent" />
              {t.uploadTitle}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
              {t.uploadSubtitle}
            </Typography>
          </Box>
        </Box>
      )}

      <Grid container spacing={3}>
        
        {/* Left Side: Upload Box & Metadata Management */}
        <Grid size={{ xs: 12, lg: 4 }} sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          
          {/* Styled Dropzone Container */}
          <Box 
            {...getRootProps()} 
            sx={{
              p: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
              cursor: 'pointer', border: '2px dashed', borderColor: isDragActive ? '#0078d4' : 'divider', borderRadius: '8px',
              bgcolor: isDragActive ? 'rgba(0, 120, 212, 0.04)' : 'rgba(0, 120, 212, 0.01)', transition: 'all 0.2s',
              '&:hover': { borderColor: '#0078d4', bgcolor: 'rgba(0, 120, 212, 0.04)' }
            }}
          >
            <input {...getInputProps()} />
            <Box sx={{
              width: 40, height: 40, borderRadius: '8px', border: '1px solid', borderColor: isDragActive ? '#0078d4' : 'divider',
              display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 2, color: 'text.secondary', bgcolor: 'background.paper'
            }}>
              {uploading ? (
                <Loader2 className="w-5 h-5 animate-spin text-gh-accent" />
              ) : (
                <Upload className="w-5 h-5 animate-pulse text-gh-accent" />
              )}
            </Box>
            
            {uploading ? (
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 'extrabold', fontSize: 11.5 }}>{t.parsingFile}</Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>{t.parsingFileDesc}</Typography>
              </Box>
            ) : isDragActive ? (
              <Typography variant="body2" sx={{ fontWeight: 'extrabold', color: 'primary.main', fontSize: 11.5 }}>{t.dragReleasePrompt}</Typography>
            ) : (
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 'extrabold', fontSize: 11.5 }}>{t.dragDropPrompt}</Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>{t.clickToUpload}</Typography>
              </Box>
            )}
            <span style={{ fontSize: 9, padding: '2px 6px', border: '1px solid rgba(0, 120, 212, 0.15)', background: 'rgba(0, 120, 212, 0.01)', color: '#9aa6bf', fontFamily: 'monospace', borderRadius: '4px', marginTop: 16 }}>
              {t.fileTypesLabel}
            </span>
          </Box>

          {/* Feedback alerts */}
          {uploadError && (
            <Alert severity="error" sx={{ borderRadius: '8px', fontSize: 11 }}>
              {uploadError}
            </Alert>
          )}

          {previewData && (
            <Alert severity="success" sx={{ borderRadius: '8px', fontSize: 11 }}>
              {language === 'tr' 
                ? `Veri kümeniz "${previewData.alias}" adıyla sisteme eklendi.` 
                : `Your dataset was added to the system as "${previewData.alias}".`}
            </Alert>
          )}

          {/* Uploaded Files List Card */}
          <Card sx={{ bgcolor: 'rgba(0, 120, 212, 0.01)', borderRadius: '8px', border: '1px solid', borderColor: 'divider' }}>
            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', display: 'block', mb: 2, borderBottom: '1px solid', borderColor: 'divider', pb: 1 }}>
                {t.uploadedFilesCardTitle}
              </Typography>
              
              <List sx={{ p: 0, display: 'flex', flexDirection: 'column', gap: 1, maxH: 260, overflowY: 'auto', pr: 0.5 }}>
                {files.map((file) => {
                  const isSelected = activeSourceId === file.id;
                  return (
                    <ListItem 
                      key={file.id} 
                      onClick={() => setActiveSourceId(file.id)}
                      sx={{
                        p: 1.2, borderRadius: '8px', border: '1px solid',
                        borderColor: isSelected ? '#0078d4' : 'divider',
                        bgcolor: isSelected ? 'rgba(0, 120, 212, 0.08)' : 'rgba(0, 120, 212, 0.02)',
                        cursor: 'pointer', transition: 'all 0.2s',
                        '&:hover': { bgcolor: isSelected ? 'rgba(0, 120, 212, 0.12)' : 'action.hover' }
                      }}
                    >
                      <Box sx={{ width: 28, height: 28, borderRadius: '6px', border: '1px solid', borderColor: isSelected ? 'rgba(0, 120, 212, 0.3)' : 'divider', display: 'flex', alignItems: 'center', justifyContent: 'center', color: isSelected ? '#0078d4' : 'text.secondary', bgcolor: 'background.paper', mr: 1.5, shrink: 0 }}>
                        <FileSpreadsheet className="w-3.5 h-3.5" />
                      </Box>
                      <Box sx={{ minWidth: 0, flex: 1, pr: 3 }}>
                        <Typography variant="body2" sx={{ fontWeight: 'extrabold', fontSize: 11.5, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                          {file.alias}
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.2, fontSize: 9, fontFamily: 'monospace', color: 'text.secondary' }}>
                          <Chip label={language === 'tr' ? `${file.row_count} SATIR` : `${file.row_count} ROWS`} size="small" sx={{ height: 14, fontSize: 7.5, fontWeight: 600, bgcolor: 'rgba(0, 120, 212, 0.1)', color: '#0078d4', border: 0 }} />
                          <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: 80 }} title={file.original_name}>{file.original_name}</span>
                        </Box>
                      </Box>
                      <ListItemSecondaryAction sx={{ right: 8 }}>
                        <Tooltip title={language === 'tr' ? 'Dosya Kaynağını Sil' : 'Delete File Source'}>
                          <IconButton edge="end" size="small" onClick={(e) => handleDeleteFile(e, file.id, file.alias)}>
                            <Trash2 size={13.5} />
                          </IconButton>
                        </Tooltip>
                      </ListItemSecondaryAction>
                    </ListItem>
                  );
                })}

                {files.length === 0 && (
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', display: 'block', textAlign: 'center', py: 4 }}>
                    {t.noUploadedFiles}
                  </Typography>
                )}
              </List>
            </CardContent>
          </Card>
          
        </Grid>

        {/* Right Side: Preview Table Panel */}
        <Grid size={{ xs: 12, lg: 8 }} sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          <Card sx={{ bgcolor: isDark ? 'rgba(0, 120, 212, 0.01)' : '#ffffff', borderRadius: '8px' }}>
            <CardContent sx={{ p: 2.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', borderBottom: '1px solid', borderColor: 'divider', pb: 1.5, mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Eye className="w-4 h-4 text-gh-accent" />
                  <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: 11.5, textTransform: 'uppercase', tracking: '0.05em' }}>
                      {t.previewPanelTitle}
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      {t.previewPanelSubtitle}
                    </Typography>
                  </Box>
                </Box>
                {uploading ? (
                  <span style={{ fontSize: 8.5, color: '#0078d4', fontFamily: 'monospace', fontWeight: 600, animation: 'pulse 1.5s infinite' }}>
                    {language === 'tr' ? 'AKILLI TARAMA ÇALIŞIYOR...' : 'SMART SCAN RUNNING...'}
                  </span>
                ) : previewData ? (
                  <Chip label={language === 'tr' ? `TOPLAM ${previewData.row_count} SATIR` : `TOTAL ${previewData.row_count} ROWS`} size="small" sx={{ height: 16, fontSize: 8.5, fontWeight: 600, bgcolor: 'rgba(0, 120, 212, 0.1)', color: '#0078d4', border: 0 }} />
                ) : null}
              </Box>

              {uploading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', justify: 'center', alignItems: 'center', py: 12, gap: 1.5 }}>
                  <Loader2 className="w-8 h-8 animate-spin text-gh-accent" />
                  <Typography variant="body2" sx={{ fontWeight: 'extrabold' }}>{language === 'tr' ? 'Veri Yapısı Keşfediliyor...' : 'Discovering Data Structure...'}</Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>{language === 'tr' ? 'Sütun veri tipleri otomatik algılanıp şemalandırılıyor.' : 'Column data types are automatically detected and structured.'}</Typography>
                </Box>
              ) : previewData ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3.5 }}>
                  
                  {/* Visual Schema Tags */}
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', display: 'block', mb: 1.5 }}>
                      {t.detectedDataTypes}
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {Object.entries(previewData.schema).map(([colName, colType]) => {
                        let color: 'primary' | 'secondary' | 'success' | 'warning' | 'info' | 'default' = 'default';
                        if (colType === 'Sayı') color = 'info';
                        else if (colType === 'Tarih') color = 'warning';
                        else if (colType === 'Boole') color = 'success';
                        
                        let colTypeLabel = colType;
                        if (language === 'en') {
                          if (colType === 'Sayı') colTypeLabel = 'Number';
                          else if (colType === 'Tarih') colTypeLabel = 'Date';
                          else if (colType === 'Boole') colTypeLabel = 'Boolean';
                          else if (colType === 'Metin') colTypeLabel = 'Text';
                        }
                        
                        return (
                          <Box key={colName} sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 0.5, bgcolor: 'rgba(0, 120, 212, 0.01)', border: '1px solid', borderColor: 'divider', borderRadius: '6px' }}>
                            <span style={{ fontFamily: 'monospace', fontSize: 10.5, fontWeight: 600 }}>{colName}</span>
                            <Chip label={colTypeLabel.toUpperCase()} size="small" color={color} sx={{ height: 14, fontSize: 7, fontWeight: 600, border: 0, borderRadius: '4px' }} />
                          </Box>
                        );
                      })}
                    </Box>
                  </Box>

                  {/* Data Preview Table using MUI components */}
                  <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', tracking: '0.05em', display: 'block', mb: 1.5 }}>
                      {language === 'tr' ? 'Veri Tablosu (İlk 20 Satır)' : 'Data Table (First 20 Rows)'}
                    </Typography>
                    
                    <TableContainer component={Paper} variant="outlined" sx={{ border: '1px solid', borderColor: 'divider', bgcolor: 'rgba(0, 120, 212, 0.01)', maxHeight: 380 }}>
                      <Table size="small" stickyHeader>
                        <TableHead>
                          <TableRow>
                            <TableCell align="center" sx={{ fontWeight: 600, fontSize: 10.5, bgcolor: 'background.paper', borderRight: '1px solid', borderColor: 'divider', width: 48, p: 1 }}>{t.tableHeadNumber}</TableCell>
                            {previewData.columns.map((col) => (
                              <TableCell key={col} sx={{ fontWeight: 600, fontSize: 10.5, bgcolor: 'background.paper', borderRight: '1px solid', borderColor: 'divider', p: 1 }}>{col}</TableCell>
                            ))}
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {visibleRows.map((row, rIdx) => (
                            <TableRow key={rIdx} hover>
                              <TableCell align="center" sx={{ fontFamily: 'monospace', fontSize: 10, borderRight: '1px solid', borderColor: 'divider', p: 0.8, bgcolor: 'rgba(0, 120, 212, 0.02)' }}>
                                {page * rowsPerPage + rIdx + 1}
                              </TableCell>
                              {previewData.columns.map((col) => (
                                <TableCell key={col} sx={{ fontFamily: 'monospace', fontSize: 10, borderRight: '1px solid', borderColor: 'divider', p: 0.8, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxW: 140 }}>
                                  {row[col] === null ? <span style={{ fontStyle: 'italic', opacity: 0.5 }}>—</span> : String(row[col])}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>

                    <TablePagination
                      rowsPerPageOptions={[8, 12, 20]}
                      component="div"
                      count={tableData.length}
                      rowsPerPage={rowsPerPage}
                      page={page}
                      onPageChange={handleChangePage}
                      onRowsPerPageChange={handleChangeRowsPerPage}
                      sx={{
                        borderTop: '0', fontSize: 10.5, color: 'text.secondary',
                        '& .MuiTablePagination-actions': { color: 'text.secondary' }
                      }}
                    />
                  </Box>
                  
                </Box>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justify: 'center', py: 12, color: 'text.secondary' }}>
                  <FileText className="w-12 h-12 mb-3 opacity-30 text-gh-muted" />
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{t.previewEmptyStateTitle}</Typography>
                  <Typography variant="caption" sx={{ mt: 0.5, maxWidth: 260, textCenter: 'center', lineHeight: 1.4 }}>
                    {t.previewEmptyStateDesc}
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

      </Grid>

    </Box>
  );
};

export default FileUpload;


