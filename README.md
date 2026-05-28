# 📊 DeepBI Analytics Studio: Çok Kaynaklı Otonom Yapay Zekâ Veri Asistanı & BI İstasyonu

DeepBI Analytics Studio; yapılandırılmış ilişkisel veritabanları (SQLite, PostgreSQL, MySQL, SAP S/4HANA) ve yüklenen veri dosyaları (Excel, CSV, TSV) üzerinde doğal dilde analitik sorgular gerçekleştiren, veri görselleştirmeleri üreten, otonom hata düzeltme (Self-Correction) döngüsüne sahip, **RAM dostu DuckDB analitik SQL motoru** ve **Yerel Depolama Yedeği (Snapshots)** altyapısı barındıran **otonom bir veri bilimi ve iş zekası (BI) asistanıdır**.

Proje, modern ve premium bir **Google Material Blue** React/TypeScript arayüzü ile FastAPI/Uvicorn tabanlı güvenli, yüksek hızlı ve diskten akışlı bir SQL analiz katmanını bir araya getirerek; kullanıcılara verileriyle doğal dilde sohbet etme, çoklu veri ilişkileri kurma (Multi-Source JOIN) ve canlı kod düzenleme özgürlüğü sunar.

---

## 🎯 Projenin Amacı ve Temel Misyonu

Geleneksel BI araçları (PowerBI, Tableau vb.) statik paneller sunarken ve SQL bilgisi gerektirirken; **DeepBI**, teknik bilgisi olmayan iş birimlerinin veya hız kazanmak isteyen veri analistlerinin **doğal dil kullanarak karmaşık veri tabanlarından anında yanıtlar almasını sağlar**. 

Sistem, kullanıcının sorularını analiz eder, otonom olarak SQL veya Python kodları yazar, bu kodları izole bir sandbox ortamında çalıştırır, çıkan verileri right-aligned spreadsheet tabloları haline getirir, Plotly ile etkileşimli grafikler çizer, makine öğrenmesi modelleriyle zaman serisi tahminleri yapar ve tek tıkla kurumsal PDF/Excel raporları üretir.

---

## 🏗️ Ajan Mimarisi ve Çalışma Mantığı (Agentic Architecture)

DeepBI, uçtan uca veri güvenliği, ultra hızlı işlem süreleri ve minimum RAM tüketimi sağlamak üzere **modüler ve ajansı (agentic) bir yapıda** tasarlanmıştır:

```mermaid
graph TB
    %% Frontend Layer
    subgraph Frontend [React/TypeScript Arayüzü]
        UI[Sidebar & Chat & Visualizer] <--> Store[Zustand Store]
    end

    %% API Layer
    subgraph Backend [FastAPI / Uvicorn Sunucusu]
        API[FastAPI REST & WebSocket /ws/chat]
        DB_Meta[(metadata.db SQLite - WAL Modu)]
        DuckEngine[DuckDB SQL Engine - Bellek İçi & Disk]
        SQL_Exec[SQL Engine - SQLite/Postgres/MySQL/HANA]
    end

    %% Agentic & RAG Layer
    subgraph AgenticSystem [Çoklu Ajan ve Self-RAG Katmanı]
        Supervisor[SupervisorAgent]
        Router[RouterAgent]
        Coder[CoderAgent]
        Visualizer[Plotly Grafik Motoru]
        Critique[CritiqueAgent]
        RAG[Memory-Backed Semantic Retriever]
        MemStore[(query_memory.json - RAM Caching)]
    end

    %% Data Flow Connections
    UI <-->|WebSocket & REST API| API
    API <-->|Session & SQLite WAL| DB_Meta
    API <-->|Process Query| Supervisor
    
    # Process
    Supervisor -->|1. Route| Router
    Supervisor -->|2. Context Retrieval| RAG
    RAG <-->|TF-IDF + Schema Overlap| MemStore
    
    # Agents
    Supervisor -->|3. SQL Code Gen| Coder
    Supervisor -->|4. Style Injection| Visualizer
    Supervisor -->|5. Verify & Execution| Critique
    
    # Critique
    Critique -->|Pre-execution Critique| Coder
    Critique -->|Execute Files & Mixed| DuckEngine
    Critique -->|Execute Direct DB| SQL_Exec
```

### 🤖 Çoklu Ajan İşbirliği (Multi-Agent Consensus)
Sürecin her adımı, kendi uzmanlık alanına sahip **özel ajanların ardışık ortaklığıyla** yürütülür:
* **RouterAgent (Yönlendirici)**: Kullanıcı sorusunu ve seçilen kaynakları analiz eder. Doğal dildeki ML/tahminleme niyetlerini otomatik yakalayarak veya slash komutlarını algılayarak rotayı çizer.
* **CoderAgent (Yazılımcı)**: Seçilen kaynağın kolon şemasını temel alarak, RAG hafızasından gelen benzer başarılı SQL şablonlarının rehberliğinde **analitik DuckDB SQL** sorgusunu veya ML kodunu yazar.
* **CritiqueAgent (Denetçi)**: SQL sorgusunu çalıştırmadan önce şema kolon doğruluğu ve SQL güvenlik kuralları yönünden inceler. Hata algılarsa sandbox'ı tetiklemeden kodu düzeltmesi için LLM'e geri gönderir. Uygunsa güvenli sandbox ortamında koşturur.
* **VisualizerAgent (Görselleştirici)**: DuckDB sorgu sonuçlarını alan akıllı grafik motorumuz, koyu tema (`#0d1117`) arayüz tasarımıyla mükemmel uyum sağlayacak şekilde Plotly figürüne; **tam şeffaf arka planlar (`rgba(0,0,0,0)`), özelleştirilmiş ızgara kılavuz çizgileri (`#21262d`), Inter yazı tipleri ve zarif kenar marjinleri** enjekte eder.

---

## 🛠️ Teknolojik Altyapı (Tech Stack)

### Arayüz (Frontend):
* **Çekirdek**: React 18+, TypeScript, Vite (Ultra Hızlı Derleme)
* **Durum Yönetimi**: Zustand (Hafif ve Hızlı Global State)
* **Tasarım Sistemi**: Google Material UI v6 & Custom Vanilla CSS (Modern Dark Mode & Glassmorphism)
* **İkon Kütüphanesi**: Lucide-React
* **Grafik Motoru**: Plotly.js (Çevrimdışı ve Yüksek Hızlı Vektör Grafikler)

### Sunucu ve Karar Motoru (Backend):
* **Web Sunucusu**: FastAPI, Uvicorn, WebSockets (Gerçek Zamanlı Durum Akışı)
* **Analitik SQL Motoru**: DuckDB (RAM'i şişirmeyen, diskten akışlı yüksek performanslı analitik sorgu motoru)
* **Veritabanı Katmanı**: SQLite (WAL - Write-Ahead Logging moduyla metadata ve LLM yapılandırma yönetimi)
* **Veri Bilimi ve ML**: Pandas, Scikit-Learn (ML Regresyon & Tahminleme modelleri)
* **Raporlama**: ReportLab (Kurumsal resmi PDF jeneratörü), OpenPyXL (Excel dışa aktarım motoru)

---

## ✨ Son Eklenen Gelişmiş Özellikler (Premium Upgrades)

* 🎨 **Google Material Blue & Grey Teması:** Tüm platform Google Cloud ve Gemini esintileri taşıyan premium Material Blue temasına kavuşturuldu. Google Blue `#1a73e8` birincil vurguları, özel yuvarlatılmış kart köşeleri, Outfit tipografisi ve harika geçiş animasyonları entegre edildi.
* 🌍 **Çift Dilli Arayüz Desteği (i18n):** Sol panelin en tepesinde yer alan kapsül butonla **Türkçe (TR) ve İngilizce (EN)** dilleri arasında tek tıkla geçiş yapabilirsiniz. Tüm butonlar, formlar, hata mesajları ve grafik başlıkları anında tercüme edilir.
* 💾 **Zustand SQLite Ayarlar Senkronizasyonu:** LLM Motoru Ayarları (API Key, Base URL, Seçilen Model) yerel tarayıcı hafızasından (localStorage) alınarak backend'deki güvenli SQLite veritabanına taşındı. API uç noktaları üzerinden senkronize edilen ayarlar, WebSocket bağlantılarına güvenle beslenir.
* 🎛️ **Tam Panel Kapatma & Otomatik Geri Getirme (Dynamic Split View):**
  - Sağ taraftaki grafik ve tablo içeren analiz panelini tek tıkla (`X` butonu) tamamen kapatabilirsiniz. Kapatıldığında aradaki sürükleme çizgisi gizlenir ve **Chat Ekranı yumuşak bir animasyonla ekranın %100'ünü kaplar**.
  - Sohbet geçmişinden **herhangi bir mesaja tekrar tıkladığınızda** veya yeni bir analiz başlattığınızda panel otomatik olarak sıfırlanıp kendini tekrar açar.
* ⌨️ **Komut Paleti Klavye Navigasyonu ve Auto-Scroll:**
  - `/` yazdığınızda açılan kılavuz komut listesi **12 adet gelişmiş BI ve veri bilimi komutuna** çıkarıldı (örn: `/explain`, `/forecast`, `/clean`, `/pivot`, `/corr`, `/help`).
  - Yön tuşlarıyla listede aşağı/yukarı gezinirken, seçilen eleman görünüm sınırını aşarsa **liste konteyneri klavyeyle senkronize olarak otomatik kayar**, fare ihtiyacını tamamen ortadan kaldırır!
* 🔮 **Doğal Dilli ML Tahminleme Yönlendiricisi:**
  - Sistem, kullanıcıların doğal dilde sorduğu tahminleme sorularını (örn: *"Önümüzdeki ay şu malzemeden kaç tane satacağım?"*, *"Satışlarım ne olur?"*) otomatik olarak analiz eder.
  - `/ml` yazılmasa dahi, ML niyetini anında anlayıp DuckDB verisini Python Sandbox'ına aktarır ve **Scikit-Learn regresyon modellerini koşturarak** trend grafiklerini Plotly üzerine yansıtır.
* 🔒 **Oturum Bazlı Çoklu Kaynak ve İlişki İzolasyonu (Session-Isolated Workspace):**
  - Her sohbet oturumu (Session), tamamen izole edilmiş **bağımsız bir analitik çalışma alanı** olarak davranır. X oturumunda seçilen veri kaynakları (örneğin A ve B veritabanları) ve aralarındaki özel JOIN ilişkileri, Y oturumunu (örneğin A ve X kaynakları) kesinlikle etkilemez; **oturumlar arası veri veya şema karışıklığı/çakışması (collision) kesinlikle yaşanmaz**.
  - Kullanıcı sol panelden farklı bir oturuma geçiş yaptığında, Zustand durum yönetimi o oturumun veritabanı şemalarını ve bağlantılarını SQLite `metadata.db` (`selected_sources` ve `relationships` sütunları) üzerinden anında geri yükler. Backend WebSocket kanalı ve Supervisor Agent sadece bu oturuma aktif seçilmiş kaynakları temel alarak analitik kod üretir ve çalıştırır.
* 🧬 **SAP HANA Entegrasyonu ve Akıllı Snapshot Yönetimi (SAP HANA & Local Snapshots):**
  - Kurumsal SAP HANA sistemlerine entegrasyon için optimize edilmiş `hdbcli` sürücüsüyle, HANA bağlantıları otomatik şema keşfi yapabilir (`SELECT 1 FROM DUMMY`).
  - Devasa kurumsal tabloların analitik sorgu performansını artırmak amacıyla **Lokal Snapshot (Yedek)** motoru geliştirilmiştir. SAP HANA üzerindeki veri kümeleri bellek dostu parçalar halinde (`fetchmany` tabanlı batching) çekilerek yerel DuckDB replikasına aktarılır. Bu sayede canlı sistemlerine yük bindirmeden, tüm SQL/ML sorguları yerel DuckDB üzerinde milisaniyeler seviyesinde çalıştırılır.

---

## ⚡ Kurulum ve Çalıştırma Kılavuzu (Setup Guide)

### Sistem Gereksinimleri
- **Python 3.10+** (Backend için)
- **Node.js 18+** (Frontend için)

### 1. Backend (Python/FastAPI) Kurulumu

1. Projenin `backend` klasörüne gidin:
   ```bash
   cd backend
   ```

2. Sanal bir Python ortamı (virtual environment) oluşturun ve aktif edin:
   * **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * **macOS / Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

4. Çevresel Değişkenleri Yapılandırın:
   `backend` dizininde bir `.env` dosyası oluşturun ve LLM anahtarlarınızı girin (Sistem ayrıca arayüzdeki Ayarlar panelinden DB'ye kaydetmeyi de destekler):
   ```env
   DEEPSEEK_API_KEY=sk-your-api-key-here
   DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
   ```

5. Backend sunucusunu başlatın:
   ```bash
   python -m uvicorn main:app --reload --port 8000
   ```
   *Backend REST API ve WebSocket sunucusu artık `http://localhost:8000` adresinde aktiftir.*

---

### 2. Frontend (React/TypeScript) Kurulumu

1. Projenin `frontend` klasörüne gidin:
   ```bash
   cd frontend
   ```

2. Gerekli Node.js paketlerini yükleyin:
   ```bash
   npm install
   ```

3. Geliştirici sunucusunu başlatın:
   ```bash
   npm run dev
   ```
   *Arayüz geliştirici portalı `http://localhost:5173` adresinde çalışmaya başlayacaktır.*

---

## 📊 Veritabanı ve Metadata Şeması

Tüm oturumlar, chat mesajları, durum geçmişleri ve LLM ayarları backend'deki SQLite (`metadata.db`) veritabanında **WAL (Write-Ahead Logging)** moduyla yüksek performanslı olarak saklanır. 

Veritabanı tablolarının sütun yapıları, ilişkileri ve detaylı şema açıklamaları için [metadata_schema.md](file:///c:/Users/safgok/Desktop/BI/metadata_schema.md) dosyasını inceleyebilirsiniz.

---

## 💡 Kurumsal Raporlama ve Analiz Dışa Aktarımı
* **Excel Belgesi:** Analiz edilen verileri tam formatlı ve right-aligned sayısal hücrelerle Excel (`.xlsx`) dosyası olarak indirir.
* **PDF Belgesi:** Oluşturulan etkileşimli Plotly grafiğini vektörel görsele dönüştürerek, kurumsal logo, başlıklar ve analiz özetleriyle birlikte resmi bir PDF analiz raporu üretir.
