# 📊 DeepBI Analytics Studio

**Doğal dilden analitik**: seçtiğin veri kaynakları üzerinde sohbet ederek SQL/Pandas analizi çalıştıran, makine öğrenmesi ile tahminleme yapan, kendi kendini düzelten (Self-RAG) ve sonuçları koyu-tema grafiklerle sunan uçtan uca bir iş zekası asistanı.

---

## Neler Var

- **🤖 Çok ajanlı analiz hattı** — Router (niyet) → Coder (SQL/Pandas üretimi) → Critique (şema doğrulama + çalıştırma) → Visualizer (Plotly). Çalışma zamanı hatasında **3 denemeye kadar otonom düzeltme**.
- **🔐 SaaS hazır kimlik katmanı** — JWT oturumlar, bcrypt şifre hash'i, **main admin + kullanıcı** rolleri. Admin kullanıcı oluşturur ve **hangi kullanıcının hangi veritabanına erişeceğini** seçer; kullanıcılar yalnızca yetkili kaynakları görür. Sohbet oturumları kullanıcıya aittir.
- **⚙️ All-in-one Ayarlar sayfası** — Model/sağlayıcı yapılandırması, veri kaynak yönetimi, kullanıcı yönetimi ve **MCP sunucu yapılandırması** tek ekranda.
- **🗄️ 7 veri kaynağı türü** — SQLite, PostgreSQL, MySQL/MariaDB, **SAP S/4HANA (HANA)**, MS SQL Server, Snowflake, Google BigQuery + Excel/CSV/TSV dosyaları. Farklı kaynaklar DuckDB üzerinde hibrit JOIN'lenebilir.
- **🧠 Self-RAG belleği** — Başarılı sorgular kaynak bazlı vektör/TF-IDF belleğe yazılır; pozitif/negatif geri bildirim ağırlıklı, çeşitlilik filtreli geri çağrım ile üretim kalitesi zamanla artar.
- **📜 Denetim kaydı (audit log)** — Girişler, sorgular, kod çalıştırmaları, konfigürasyon değişiklikleri: kim, ne zaman, hangi kaynakta — hassas alanlar maskelenerek, istek ID'siyle ilişkilendirilmiş şekilde.
- **🛡️ Katmanlı güvenlik** — SQL sanitizer (sqlglot AST + whitelist), AST tabanlı izole Python sandbox'ı (fail-closed), bağlantı başına sorgu timeout'u ve devre kesici (circuit breaker).
- **🌙 Linear/Vercel tarzı arayüz** — Koyu zinc + indigo tasarım dili, token tabanlı temalandırma, TR/EN dil desteği.

## Mimari

```
frontend (React 19 + Vite + Zustand + MUI + Tailwind)
   │  REST /api/*  +  WebSocket /ws/chat
   ▼
FastAPI backend
   ├─ routers/         sessions · sources · files · settings · analytics · rag · auth · admin · mcp
   ├─ core/            auth · audit · breaker · config · crypto · duckdb_engine · logger
   │                   sandbox · sql_sanitizer · table_resolver · visualizer · predictor ...
   ├─ agent/           supervisor (kod üretim & düzeltme hattı)
   │                   graph_supervisor (LangGraph akışı, varsayılan)
   │                   rag (Self-RAG belleği) · semantic_cache · prompts · parsing
   └─ database/        manager (metadata.db) · connectors (7 sürücü) · snapshots
```

## Hızlı Başlangıç

### Windows (cmd / çift tık)
```bat
rundevsetup.bat     :: Python venv + pip + npm install + .env hazırlar
rundev.bat          :: Backend (8000) + Frontend (5173) pencerelerini başlatır
```

### Linux / macOS / Git Bash
```bash
./setup_dev_linux.sh    # venv + bağımlılıklar + .env
./run_dev_linux.sh      # backend + frontend (Ctrl+C ile ikisi de kapanır)
```

### İlk giriş
1. `http://localhost:5173` → **admin / admin123** ile giriş yap
2. Sistem ilk girişte şifre değiştirmeni ister
3. İlk admin şifresini önceden belirlemek için `.env`'de `ADMIN_INITIAL_PASSWORD` kullan

> ⚠️ **Üretim notu**: `SECRET_KEY` JWT imzalamada kullanılır; deploy öncesi güçlü rastgele bir değerle değiştirin (`python -c "import secrets; print(secrets.token_urlsafe(48))"`). Değişiklik sonrası kayıtlı veri kaynağı şifrelerini yeniden girmeniz gerekir.

### Ortam Değişkenleri (.env)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `SECRET_KEY` | `changeme...` | JWT + kaynak şifresi şifreleme anahtarı |
| `APP_TOKEN` | *(boş)* | Makine/bootstrap erişimi (X-API-Token) |
| `ADMIN_INITIAL_PASSWORD` | `admin123` | İlk admin şifresi |
| `CORS_ORIGINS` | localhost:5173,3000 | İzinli frontend origin'leri |
| `SANDBOX_TIMEOUT_SECONDS` / `SANDBOX_MAX_MEMORY_MB` | 10 / 512 | Python sandbox limitleri |
| `LOG_LEVEL` / `LOG_FILE` / `LOG_FORMAT` | INFO / ./deepbi.log / text | Loglama (`json` = yapılandırılmış) |
| `AUDIT_RETENTION_DAYS` | 90 | Denetim kaydı saklama süresi |
| `USE_LANGGRAPH` | `true` | `false` → klasik SupervisorAgent |

Tam liste: [backend/.env.example](backend/.env.example)

## Veri Kaynağı Bağlantıları

Kaynak yönetimi Ayarlar → Veri Kaynakları'ndan yapılır; şifreler Fernet ile şifrelenir.

**SAP S/4HANA özel notları:**
- `hdbcli` aktif bağımlılıktır; bağlantı sonrası verilen `schema` oturuma `SET SCHEMA` ile uygulanır
- Şema keşfi S/4HANA ölçeğine göre sınırlıdır: SAP namespace tabloları (`/1BF/...`) dışlanır, `max_tables` (varsayılan 500) ile sınırlanır
- Bağlantı detaylarına eklenebilenler: `table_filter: "KNA%,VBAK%"` (LIKE desenleri), `max_tables`, `encrypt`, `sslValidateCertificate`, `communicationTimeout`, `query_timeout` (saniye — tüm sürücülerde)

## Testler

```bash
cd backend
venv/Scripts/python.exe -m pytest tests/ -q      # Windows
python3 -m pytest tests/ -q                       # Linux/macOS
```

Testler `DEEPBI_METADATA_DB` env değişkeniyle **izole bir veritabanında** çalışır — gerçek verilerinize dokunmaz. Kapsam: SQL sanitizer, sandbox güvenlik kontrolü, auth/roller/oturum sahipliği, connector'lar, HANA (mock sürücü), audit log, API entegrasyonu.

## Proje Yapısı

```
backend/
  main.py                  # FastAPI app, auth middleware, WS chat hattı
  app/routers/             # 9 REST router (auth, admin, sessions, sources, ...)
  app/agent/               # supervisor + graph_supervisor + rag + prompts + parsing
  app/core/                # auth, audit, breaker, duckdb_engine, sandbox, sql_sanitizer...
  app/database/            # manager (metadata.db), connectors (7 DB), snapshots
  tests/                   # 109 test — izole DB'de koşar
frontend/
  src/components/          # ChatConsole, SourceManager, SettingsPage, ResultVisualizer...
  src/context/store.ts     # Zustand store (auth + oturum + kaynaklar)
  src/api/client.ts        # apiFetch (token, timeout, 401 yönetimi)
  src/index.css            # Tasarım token'ları (tek doğruluk kaynağı)
.agents/
  mcp_config.json          # MCP sunucu tanımları (Ayarlar → MCP'den yönetilir)
```

## Yol Haritası

İleride yapılabilecekler — öncelik sırasına göre:

### Veri katmanı
- [ ] **SQLite → PostgreSQL geçişi** + Alembic migration disiplini (şu an şema değişiklikleri elle `ALTER TABLE` bloklarıyla)
- [ ] Tüm DB erişiminin repository katmanına toplanması (dağınık `sqlite3.connect` çağrılarının temizlenmesi)
- [ ] Bağlantı havuzu (pooling) — her sorguda yeni TCP/TLS yerine yeniden kullanım

### Çok kiracılılık (SaaS)
- [ ] `organizations` tablosu + tüm tablolara `tenant_id`, sorgu katmanında otomatik tenant filtresi
- [ ] Planlar ve kullanım ölçümü (`usage` tablosu): sorgu adedi, kaynak sayısı, kullanıcı limiti
- [ ] Faturalama entegrasyonu (Stripe/Iyzico) + LLM maliyeti için BYOK ↔ platform anahtarı kararı

### Kurumsal güvenlik
- [ ] SSO/OIDC (Azure AD/Entra, Okta) ve 2FA (TOTP)
- [ ] Şifre sıfırlama + e-posta doğrulama (SMTP), oturum iptali (refresh token / revoke listesi)
- [ ] Audit log dışa aktarımı (CSV/SIEM besleme)

### Ölçek & operasyon
- [x] Kayıtlı analizler (soru + kaynak kombinasyonu tek tıkla tekrar) — Zamanlanmış raporların altyapısıyla ortak
- [ ] Ağır işlerin (materialization, sandbox) job kuyruğuna taşınması + `jobs` tablosu
- [ ] Docker Compose + reverse proxy ile tek komut deploy (frontend'in `:8000` sabitinin relative `/api`'ye çevrilmesi)
- [ ] Dosya depolamanın S3/Azure Blob'a taşınması
- [ ] Prometheus metrikleri + Sentry hata takibi

### Ürün
- [ ] **S/4HANA released CDS view keşfi** (VDM: `I_*`/`C_*` görünümleri) — ham tablolar yerine SAP'nin önerdiği analitik katman
- [ ] LLM prompt'larına HANA dialect ipuçları (identifier tırnaklama, LIMIT/TOP farkları)
- [x] Zamanlanmış raporlar + e-posta bildirimi (APScheduler + SMTP; Ayarlar → Zamanlanmış Raporlar)
- [ ] Sonuç paylaşım linkleri (süreli, salt-okunur token)
- [x] Ayarlar sayfasında admin "Denetim Kayıtları" görüntüleyici bölümü

## Notlar

- Power BI MCP entegrasyonu ayrı bir istemci yapılandırmasıdır (`.agents/mcp_config.json`); EULA kabulü config'deki `--accept-eula` ile verilir.
- Model sağlayıcılar kullanıcı yapılandırmasıdır: OpenAI, OpenRouter, LM Studio, Ollama veya herhangi bir OpenAI-uyumlu endpoint.
- Kurumsal rapor dışa aktarımı: Excel (.xlsx), PDF (.pdf) ve CSV (.csv) — mesaj kartındaki Export menüsünden.
