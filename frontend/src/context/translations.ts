export interface TranslationKeys {
  // Sidebar
  notebooks: string;
  search: string;
  activeDataset: string;
  noDataset: string;
  sources: string;
  settings: string;
  active: string;
  passive: string;
  noResults: string;
  renameTooltip: string;

  // LLM Settings
  llmSettingsTitle: string;
  llmSettingsSubtitle: string;
  engineSelection: string;
  presetsTitle: string;
  presetsSubtitle: string;
  baseUrlLabel: string;
  baseUrlDesc: string;
  apiKeyLabel: string;
  apiKeyDescLocal: string;
  apiKeyDescCloud: string;
  modelLabel: string;
  modelDesc: string;
  testBtn: string;
  testingBtn: string;
  closeBtn: string;
  applyBtn: string;
  savedBtn: string;
  testSuccess: string;
  testFailed: string;

  // Source Manager
  sourcesTitle: string;
  sourcesSubtitle: string;
  refreshBtn: string;
  addBtn: string;
  fileSourcesSection: string;
  fileSourcesDesc: string;
  activeSessionTables: string;
  activeSessionDesc: string;
  mainSourceLabel: string;
  noActiveSource: string;
  additionalSources: string;
  additionalSourcesDesc: string;
  noAdditionalSource: string;
  detailsModalTitle: string;
  metricsLabel: string;
  serverParamsLabel: string;
  labelsCardTitle: string;
  labelsInputPlaceholder: string;
  labelsDesc: string;
  semanticModalTitle: string;
  semanticModalDesc: string;
  loadingSchema: string;
  noTablesFound: string;
  refreshSchemaFirst: string;
  columnCount: string;
  semanticInputAlias: string;
  semanticInputDesc: string;
  semanticBtnSave: string;
  semanticBtnSaving: string;
  noDatabaseConnected: string;
  startAnalysisPrompt: string;
  schemaAnalysis: string;
  tablesDetected: string;
  noTablesDetected: string;
  addNewSourceCard: string;
  addNewSourcePrompt: string;
  securitySectionTitle: string;
  securityPoint1: string;
  securityPoint2: string;
  securityPoint3: string;
  sqlitePathLabel: string;
  sqlitePathPlaceholder: string;
  serverHostLabel: string;
  serverHostPlaceholder: string;
  serverPortLabel: string;
  databaseNameLabel: string;
  databaseNamePlaceholder: string;
  schemaNameLabel: string;
  schemaNamePlaceholder: string;
  dbUserLabel: string;
  dbUserPlaceholder: string;
  dbPasswordLabel: string;
  dbPasswordPlaceholder: string;
  editModeActive: string;
  editModeDesc: string;
  saveConnectionBtn: string;
  saveConnectionLoading: string;

  // File Upload
  uploadTitle: string;
  uploadSubtitle: string;
  dragDropPrompt: string;
  clickToUpload: string;
  fileTypesLabel: string;
  parsingFile: string;
  parsingFileDesc: string;
  dragReleasePrompt: string;
  uploadErrorTitle: string;
  uploadSuccessTitle: string;
  uploadSuccessDesc: string;
  uploadedFilesCardTitle: string;
  noUploadedFiles: string;
  previewPanelTitle: string;
  previewPanelSubtitle: string;
  detectedDataTypes: string;
  rowsCount: string;
  tableHeadNumber: string;
  previewEmptyStateTitle: string;
  previewEmptyStateDesc: string;

  // Chat Console
  queryPlaceholder: string;
  calculating: string;
  queryTitle: string;
  clearChatTooltip: string;
  multisourceTitle: string;
  multisourceSelected: string;
  multisourceDefaultActive: string;
  editBtn: string;
  engineRunning: string;
  commandPaletteTitle: string;
  runCodeBtn: string;
  commandPaletteHint: string;
  editModeLabel: string;
  runEditedCodeTooltip: string;
  cancelBtnTooltip: string;
  editCodeTooltip: string;
  copyTooltip: string;
  downloadTooltip: string;
  executionLogTitle: string;

  // Result Visualizer
  visualizerEmptyTitle: string;
  visualizerEmptyDesc: string;
  chartTitle: string;
  chartShow: string;
  chartHide: string;
  searchInTable: string;
  noDataFound: string;
  noTableData: string;
  exportError: string;
  page: string;

  // Added Premium elements
  closePanelTooltip: string;
  chartTunerPlaceholder: string;
  rowsCountBadge: string;
  selectedCountBadge: string;
  exportExcelTooltip: string;
  exportPdfTooltip: string;
  exportCsvTooltip: string;
  feedbackSuccess: string;
  feedbackTooltipPositive: string;
  feedbackTooltipNegative: string;
  joinTypeInner: string;
  joinTypeLeft: string;
  joinTypeRight: string;
  joinTypeOuter: string;
  schemaDesignerTitle: string;
}

export const translations: Record<'tr' | 'en', TranslationKeys> = {
  tr: {
    notebooks: "Analiz Defterleri",
    search: "ara...",
    activeDataset: "Aktif Veri Kümesi",
    noDataset: "Veri Kaynağı Seçilmedi",
    sources: "Kaynaklar",
    settings: "Ayarlar",
    active: "AKTİF",
    passive: "PASİF",
    noResults: "— Sonuç yok —",
    renameTooltip: "Çift tıklayarak yeniden adlandırın",

    llmSettingsTitle: "Hesaplama Motoru Bağlantı Ayarları",
    llmSettingsSubtitle: "DeepBI Analytics Studio Core Engine",
    engineSelection: "Motor Seçimi",
    presetsTitle: "Bağlantı Parametreleri",
    presetsSubtitle: "Seçilen analitik motor için geçerli kimlik doğrulama anahtarını ve parametreleri girin.",
    baseUrlLabel: "Base URL",
    baseUrlDesc: "URL değiştirirseniz otomatik olarak Özel moda geçilir.",
    apiKeyLabel: "API Bağlantı Anahtarı (API Key)",
    apiKeyDescLocal: "Local modda anahtar gerekmiyor.",
    apiKeyDescCloud: "Anahtarlarınız tarayıcı yerel belleğinde maskeli tutulur.",
    modelLabel: "Hedef Model İsmi",
    modelDesc: "Örn: `deepseek-coder`, `google/gemini-2.5-flash`, `gpt-4o`",
    testBtn: "Test Et",
    testingBtn: "Test ediliyor...",
    closeBtn: "Kapat",
    applyBtn: "Uygula",
    savedBtn: "Kaydedildi",
    testSuccess: "Bağlantı başarılı.",
    testFailed: "Bağlantı başarısız.",

    sourcesTitle: "Veri Kaynakları Merkezi",
    sourcesSubtitle: "Excel/CSV dosyalarınızı yükleyin, veritabanlarınızı bağlayın ve şemalarınızı anında görselleştirin.",
    refreshBtn: "Yenile",
    addBtn: "Yeni Bağlantı Ekle",
    fileSourcesSection: "Dosya Kaynakları",
    fileSourcesDesc: "CSV / Excel yükleyin, şemasını otomatik tarayın ve analiz edin.",
    activeSessionTables: "Aktif Oturum Tabloları",
    activeSessionDesc: "Çalışma oturumuna aktarılan aktif veritabanı ve dosya şemaları.",
    mainSourceLabel: "Ana Çalışma Kaynağı",
    noActiveSource: "(Seçim Yapılmadı)",
    additionalSources: "Çoklu Ek Kaynaklar",
    additionalSourcesDesc: "Sorgu orkestrasyonunda eş zamanlı taranacak diğer kaynaklar.",
    noAdditionalSource: "Ek kaynak seçilmedi.",
    detailsModalTitle: "Kaynak Detayları & Etiketler",
    metricsLabel: "Metrikler",
    serverParamsLabel: "Sunucu Parametreleri",
    labelsCardTitle: "Arama Etiketleri",
    labelsInputPlaceholder: "Örn: satis, üretim, canli",
    labelsDesc: "Etiketleri virgül (,) ile ayırarak giriniz. Yapay Zeka bu etiketler yardımıyla veritabanını daha hızlı keşfeder.",
    semanticModalTitle: "Semantik Metrik Katmanı Tanımlayıcı",
    semanticModalDesc: "Kolonlara takma ad ve iş tanımları ekleyerek yapay zeka analiz doğruluğunu en üst düzeye çıkarın.",
    loadingSchema: "Şema tanımları yükleniyor...",
    noTablesFound: "Bu veri kaynağında tablo bulunamadı.",
    refreshSchemaFirst: "Lütfen önce şemayı yenileyin.",
    columnCount: "KOLON",
    semanticInputAlias: "Görünecek İsim (Takma Ad)",
    semanticInputDesc: "İş Açıklaması (LLM bu kolonu tanımak için kullanır)",
    semanticBtnSave: "Semantik Tanımları Kaydet",
    semanticBtnSaving: "Kaydediliyor...",
    noDatabaseConnected: "Bağlı herhangi bir veritabanı bulunamadı.",
    startAnalysisPrompt: "Sağ üstteki \"Yeni Bağlantı Ekle\" butonunu kullanarak analize başlayın.",
    schemaAnalysis: "Şema Analizi",
    tablesDetected: "Tablo Keşfedildi",
    noTablesDetected: "Bağlantıda herhangi bir tablo keşfedilmedi. Şemayı yenilemeyi deneyin.",
    addNewSourceCard: "Yeni Veri Tabanı Ekle",
    addNewSourcePrompt: "PostgreSQL, MySQL veya SQLite bağlantısı ekleyerek analize başlayın.",
    securitySectionTitle: "Güvenli Erişim & Altyapı",
    securityPoint1: "Tüm SQL sorguları sqlglot ile dezenfekte edilir.",
    securityPoint2: "Yalnızca READ-ONLY yetkisine sahip kullanıcılar kullanılması önerilir.",
    securityPoint3: "Şifreler ve kimlik bilgileri bellekte güvenle maskelenir.",
    sqlitePathLabel: "SQLite Dosya Yolu",
    sqlitePathPlaceholder: "veri.db veya C:\\veriler\\sales.db",
    serverHostLabel: "Sunucu (Host)",
    serverHostPlaceholder: "localhost",
    serverPortLabel: "Port",
    databaseNameLabel: "Veritabanı Adı",
    databaseNamePlaceholder: "müsteri_db",
    schemaNameLabel: "Şema (Schema) - Opsiyonel",
    schemaNamePlaceholder: "public",
    dbUserLabel: "Kullanıcı Adı",
    dbUserPlaceholder: "admin",
    dbPasswordLabel: "Şifre",
    dbPasswordPlaceholder: "••••••••",
    editModeActive: "Düzenleme Modu Aktif",
    editModeDesc: "Seçilen veritabanının parametrelerini güncelliyorsunuz. Şifre değişmeyecekse boş bırakabilirsiniz.",
    saveConnectionBtn: "Bağlantıyı Kaydet & Şemayı Çıkar",
    saveConnectionLoading: "Kaydediliyor...",

    uploadTitle: "Excel / CSV Veri Yükleme",
    uploadSubtitle: "Kendi yerel veri kümelerinizi yükleyin, otomatik şemalandırma ve ön izleme ile anında sorgulayın.",
    dragDropPrompt: "Dosyanızı Buraya Sürükleyin",
    clickToUpload: "veya seçmek için tıklayın",
    fileTypesLabel: "CSV, TSV, XLSX, XLS",
    parsingFile: "Dosya Ayrıştırılıyor...",
    parsingFileDesc: "Sütun tipleri ve satırlar okunuyor...",
    dragReleasePrompt: "Bırakın ve Yükleyin...",
    uploadErrorTitle: "Hata Oluştu",
    uploadSuccessTitle: "Başarıyla Yüklendi",
    uploadSuccessDesc: "Veri kümeniz sisteme başarıyla eklendi.",
    uploadedFilesCardTitle: "Yüklenen Veri Tabloları",
    noUploadedFiles: "Kayıtlı herhangi bir dosya tablosu yok.",
    previewPanelTitle: "Ön İzleme Paneli",
    previewPanelSubtitle: "Yüklenen dosyadaki şema sütun tipleri ve ilk 20 veri satırı.",
    detectedDataTypes: "Otomatik Algılanan Veri Tipleri",
    rowsCount: "SATIR",
    tableHeadNumber: "#",
    previewEmptyStateTitle: "Ön izleme tablosu boş.",
    previewEmptyStateDesc: "Soldaki panelden Excel veya CSV dosyasını yükleyin, veriler otomatik şemalandırılarak burada ön izlenecektir.",

    // Chat Console
    queryPlaceholder: "sorgu girin veya / yazın...",
    calculating: "hesaplanıyor...",
    queryTitle: "Sohbet",
    clearChatTooltip: "Konuşmayı temizle",
    multisourceTitle: "Çoklu Veri Kaynağı Yapılandırması",
    multisourceSelected: "{count} kaynak seçildi",
    multisourceDefaultActive: "Varsayılan: Tüm kaynaklar aktif",
    editBtn: "Düzenle",
    engineRunning: "Analiz motoru çalışıyor...",
    commandPaletteTitle: "KOMUT PALETİ — ↑↓ seçin, Enter uygulayın",
    runCodeBtn: "ÇALIŞTIR",
    commandPaletteHint: "/ yazarak komut paletini açabilirsiniz",
    editModeLabel: "• DÜZENLEME MODU",
    runEditedCodeTooltip: "Kodu Çalıştır",
    cancelBtnTooltip: "Vazgeç",
    editCodeTooltip: "Kodu Düzenle",
    copyTooltip: "Kopyala",
    downloadTooltip: "Kodu İndir",
    executionLogTitle: "İŞLEM KAYDI — {count} ADIM",

    // Result Visualizer
    visualizerEmptyTitle: "Sonuç Görselleştirme Paneli",
    visualizerEmptyDesc: "Sohbet ekranında sorduğunuz analizlerin etkileşimli tabloları ve grafikleri burada anında görüntülenecektir.",
    chartTitle: "Grafik",
    chartShow: "Grafiği Göster",
    chartHide: "Grafiği Gizle",
    searchInTable: "Tabloda ara...",
    noDataFound: "Arama kriterine uygun veri bulunamadı.",
    noTableData: "Sorgu sonucunda herhangi bir veri tablosu bulunamadı.",
    exportError: "Aktarım sırasında bir hata oluştu.",
    page: "Sayfa",

    // Added Premium elements
    closePanelTooltip: "Paneli Kapat",
    chartTunerPlaceholder: "Grafiği düzenle (örn: \"çizgi yap\", \"mor yap\", \"X eksenini ... yap\")",
    rowsCountBadge: "SATIR",
    selectedCountBadge: "SEÇİLİ",
    exportExcelTooltip: "Excel Dosyası Olarak İndir",
    exportPdfTooltip: "PDF Belgesi Olarak İndir",
    exportCsvTooltip: "CSV Metni Olarak İndir",
    feedbackSuccess: "Teşekkürler! Geri bildiriminiz RAG hafızasına başarıyla kaydedildi.",
    feedbackTooltipPositive: "Bu analiz başarılıydı",
    feedbackTooltipNegative: "Bu analiz hatalıydı",
    joinTypeInner: "INNER JOIN (Kesişim)",
    joinTypeLeft: "LEFT JOIN (Sol Kesişim)",
    joinTypeRight: "RIGHT JOIN (Sağ Kesişim)",
    joinTypeOuter: "FULL OUTER JOIN (Tam Kesişim)",
    schemaDesignerTitle: "Etkileşimli İlişkisel Şema Tasarımcısı"
  },
  en: {
    notebooks: "Analysis Notebooks",
    search: "search...",
    activeDataset: "Active Dataset",
    noDataset: "No Data Source Selected",
    sources: "Sources",
    settings: "Settings",
    active: "ACTIVE",
    passive: "PASSIVE",
    noResults: "— No results —",
    renameTooltip: "Double click to rename session",

    llmSettingsTitle: "Calculation Engine Connection Settings",
    llmSettingsSubtitle: "DeepBI Analytics Studio Core Engine",
    engineSelection: "Engine Selection",
    presetsTitle: "Connection Parameters",
    presetsSubtitle: "Enter valid authentication credentials and endpoints for the chosen analytical engine.",
    baseUrlLabel: "Base URL",
    baseUrlDesc: "Changing the URL automatically switches config to Custom preset.",
    apiKeyLabel: "API Authentication Key (API Key)",
    apiKeyDescLocal: "Key is not required in Local offline mode.",
    apiKeyDescCloud: "Your keys are masked and securely stored in your local browser storage.",
    modelLabel: "Target Model Name",
    modelDesc: "E.g.: `deepseek-coder`, `google/gemini-2.5-flash`, `gpt-4o`",
    testBtn: "Test Connection",
    testingBtn: "Testing connection...",
    closeBtn: "Close",
    applyBtn: "Apply Changes",
    savedBtn: "Configuration Saved",
    testSuccess: "Connection successful.",
    testFailed: "Connection failed.",

    sourcesTitle: "Unified Data Sources Hub",
    sourcesSubtitle: "Upload CSV/Excel sheets, connect remote databases, and inspect schema structures instantly.",
    refreshBtn: "Refresh",
    addBtn: "Add New Connection",
    fileSourcesSection: "File Data Sources",
    fileSourcesDesc: "Upload CSV / Excel tables, auto-scan columns, and perform advanced data queries.",
    activeSessionTables: "Active Session Tables",
    activeSessionDesc: "Schema schemas and active database sheets mapped into the workspace.",
    mainSourceLabel: "Main Analysis Workspace",
    noActiveSource: "(No Selection)",
    additionalSources: "Multiple Secondary Sources",
    additionalSourcesDesc: "Additional databases parsed concurrently inside query orchestration.",
    noAdditionalSource: "No secondary sources selected.",
    detailsModalTitle: "Connection Details & Tags",
    metricsLabel: "Metrics Summary",
    serverParamsLabel: "Server Parameters",
    labelsCardTitle: "Discovery Tags",
    labelsInputPlaceholder: "E.g.: sales, production, live",
    labelsDesc: "Enter tags separated by commas. LLM uses these tags to accelerate data discovery and metric classification.",
    semanticModalTitle: "Semantic Metric Layer Configurator",
    semanticModalDesc: "Assign display aliases and business definitions to fields to maximize AI query accuracy.",
    loadingSchema: "Loading database schema maps...",
    noTablesFound: "No tables discovered in this dataset.",
    refreshSchemaFirst: "Please refresh schema map first.",
    columnCount: "COLUMNS",
    semanticInputAlias: "Display Alias Name",
    semanticInputDesc: "Business Definition (LLM reads this to interpret column values)",
    semanticBtnSave: "Save Semantic Layer Mapping",
    semanticBtnSaving: "Saving maps...",
    noDatabaseConnected: "No remote database connections registered.",
    startAnalysisPrompt: "Use the \"Add New Connection\" button in the top-right corner to initiate data modeling.",
    schemaAnalysis: "Schema Analysis",
    tablesDetected: "Tables Discovered",
    noTablesDetected: "No tables discovered. Try refreshing connection schema mapping.",
    addNewSourceCard: "Add Remote Database",
    addNewSourcePrompt: "Establish secure PostgreSQL, MySQL, or SQLite connections to run analysis.",
    securitySectionTitle: "Secure Data Access & Framework",
    securityPoint1: "All executed queries are sanitized and checked using sqlglot engine.",
    securityPoint2: "We highly recommend using accounts with READ-ONLY permissions.",
    securityPoint3: "All credentials and passwords are securely masked in active session memory.",
    sqlitePathLabel: "SQLite Path",
    sqlitePathPlaceholder: "data.db or C:\\data\\sales.db",
    serverHostLabel: "Server Host",
    serverHostPlaceholder: "localhost",
    serverPortLabel: "Port",
    databaseNameLabel: "Database Name",
    databaseNamePlaceholder: "customer_db",
    schemaNameLabel: "Schema (Optional)",
    schemaNamePlaceholder: "public",
    dbUserLabel: "User Name",
    dbUserPlaceholder: "admin",
    dbPasswordLabel: "Password",
    dbPasswordPlaceholder: "••••••••",
    editModeActive: "Edit Mode Active",
    editModeDesc: "Updating properties for the selected database. You can leave password blank to preserve existing.",
    saveConnectionBtn: "Save Connection & Extract Schema",
    saveConnectionLoading: "Saving changes...",

    uploadTitle: "Excel / CSV File Upload",
    uploadSubtitle: "Upload your local datasets to automatically discover tables and run visual analytics immediately.",
    dragDropPrompt: "Drag & Drop File Here",
    clickToUpload: "or click to select from disk",
    fileTypesLabel: "CSV, TSV, XLSX, XLS",
    parsingFile: "Analyzing Data Structures...",
    parsingFileDesc: "Identifying auto-schema columns and rows...",
    dragReleasePrompt: "Drop to parse file...",
    uploadErrorTitle: "Upload Error",
    uploadSuccessTitle: "File Uploaded Successfully",
    uploadSuccessDesc: "Dataset was parsed and successfully integrated into session data.",
    uploadedFilesCardTitle: "Uploaded File Tables",
    noUploadedFiles: "No local files uploaded to this session.",
    previewPanelTitle: "Preview Panel",
    previewPanelSubtitle: "Identified column data types and first 20 rows of visual preview.",
    detectedDataTypes: "Auto-Detected Column Data Types",
    rowsCount: "ROWS",
    tableHeadNumber: "#",
    previewEmptyStateTitle: "Preview workspace is empty.",
    previewEmptyStateDesc: "Upload CSV or Excel files from the left side. Columns and data structures will preview instantly.",

    // Chat Console
    queryPlaceholder: "enter query or type /...",
    calculating: "calculating...",
    queryTitle: "Chat",
    clearChatTooltip: "Clear conversation",
    multisourceTitle: "Multi-Data Source Configuration",
    multisourceSelected: "{count} sources selected",
    multisourceDefaultActive: "Default: All sources active",
    editBtn: "Edit",
    engineRunning: "Analysis engine running...",
    commandPaletteTitle: "COMMAND PALETTE — Use ↑↓ to select, Enter to apply",
    runCodeBtn: "RUN",
    commandPaletteHint: "type / to open command palette",
    editModeLabel: "• EDIT MODE",
    runEditedCodeTooltip: "Run Code",
    cancelBtnTooltip: "Cancel",
    editCodeTooltip: "Edit Code",
    copyTooltip: "Copy",
    downloadTooltip: "Download Code",
    executionLogTitle: "EXECUTION LOG — {count} STEPS",

    // Result Visualizer
    visualizerEmptyTitle: "Result Visualization Panel",
    visualizerEmptyDesc: "Interactive tables and charts of the analyses you ask in the chat console will be displayed instantly here.",
    chartTitle: "Chart",
    chartShow: "Show Chart",
    chartHide: "Hide Chart",
    searchInTable: "Search in table...",
    noDataFound: "No data found matching the search criteria.",
    noTableData: "No data table discovered as a result of query.",
    exportError: "An error occurred during export.",
    page: "Page",

    // Added Premium elements
    closePanelTooltip: "Close Panel",
    chartTunerPlaceholder: "Tune chart (e.g. \"make it line\", \"color it purple\", \"set x axis to ...\")",
    rowsCountBadge: "ROWS",
    selectedCountBadge: "SELECTED",
    exportExcelTooltip: "Download as Excel File",
    exportPdfTooltip: "Download as PDF Document",
    exportCsvTooltip: "Download as CSV Text",
    feedbackSuccess: "Thank you! Your feedback has been recorded in our semantic RAG memory.",
    feedbackTooltipPositive: "This analysis was successful",
    feedbackTooltipNegative: "This analysis was incorrect",
    joinTypeInner: "INNER JOIN (Intersection)",
    joinTypeLeft: "LEFT JOIN (Left Intersection)",
    joinTypeRight: "RIGHT JOIN (Right Intersection)",
    joinTypeOuter: "FULL OUTER JOIN (Full Intersection)",
    schemaDesignerTitle: "Interactive Relational Schema Designer"
  }
};
