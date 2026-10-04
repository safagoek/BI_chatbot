---
name: deepbi-frontend-design
description: DeepBI frontend tasarım sistemi — sıcak aydınlık (kırık beyaz + koralj) tasarım dili, tek kolon sohbet / opsiyonel stüdyo düzeni, token sistemi ve bileşen kuralları. Bu repoda React/TSX bileşeni oluştururken, stillerken, tema/renk değiştirirken, yeni sayfa/modal/panel eklerken, UI/UX düzenlerken KULLAN — kullanıcı "tasarım", "UI", "görünüm", "renk", "buton", "stil", "dizayn" dese de demese de tetikle.
---

# DeepBI Frontend Tasarım Sistemi

**Tasarım felsefesi (kullanıcı kararları, 2026-10):** Deneyim önce, estetik sonra. Akış net olmalı (kaynak seç → sor → keşfet); varsayılan görünüm **tek kolon sohbet**; estetik **sıcak aydınlık nötr** (kırık beyaz + koralj vurgu, Claude/Notion hissi). Koyu tema opsiyonel ve sıcak taş paleti.

## Önce oku

Stil işine başlamadan önce şu iki dosyayı oku (token'ların gerçek kaynağı):

1. `frontend/src/index.css` — `:root` (light, DEFAULT), `:root.dark`, `:root.light` blokları
2. `frontend/src/components/LoginPage.tsx` — yeni bileşenler için stil üslubu örneği (inline style + CSS var)

## Renk token'ları (index.css'ten, değerleri yeniden icat etme)

| Token | Light (DEFAULT) | Dark | Kullanım |
|---|---|---|---|
| `--color-bg` | `#faf9f7` (kırık beyaz) | `#1b1917` | Uygulama zemini |
| `--color-canvas` | `#ffffff` | `#211f1c` | Panel/ekran zemini |
| `--color-surface` | `#f6f5f2` | `#282521` | Kart, girdi yüzeyi |
| `--color-surface2` | `#edebe6` | `#332f2a` | Hover / yükseltilmiş yüzey |
| `--color-border` | rgba(28,25,23,.09) | rgba(255,255,255,.10) | Tüm çizgiler 1px |
| `--color-text` | `#1f1e1c` | `#faf9f7` | Ana metin |
| `--color-muted` / `--color-faint` | `#78716c` / `#a8a29e` | aynı | İkincil metin |
| `--color-accent` | `#c96442` (koralj) | `#e08a63` | Primary buton, aktif göstergeler (az kullan) |
| `--color-accent-hover/press` | `#b8532f` / `#a34628` | `#e89a77` / `#c96442` | Hover/aktif |
| `--color-accent-subtle` | rgba(201,100,66,.09) | rgba(224,138,99,.14) | Seçili/odak zemin |
| `--color-success/warning/danger` | emerald/amber/red | aynı aile | Semantik durumlar |

Tailwind eşlemesi `tailwind.config.js`'te `gh-*` önekiyle (`bg-gh-surface`, `text-gh-muted`...). MUI teması App.tsx'te light-first.

## YASAK renkler

Eski indigo teması: `#6366f1`, `#818cf8`, `#a5b4fc`, `#4f46e5`, `#7c3aed` + rgba(99,102,241,...). Daha eski Fluent mavisi: `#0078d4`, `#0f766e`. Görürsen koralj eşdeğerleriyle değiştir. Tek istisna: `--color-done` (#8b5cf6, semantik "tamamlandı" durumu).

## Görsel kurallar (nedeniyle)

- **Sıcaklık**: kırık beyaz zemin + yumuşak gölge — sert siyah kenarlık hissi yok. Gölge ilk estetik araçtır: kartlar `0 2px 6px rgba(28,25,23,0.06)`, dialog `0 12px 32px rgba(28,25,23,0.10)`; overlay scrim `rgba(28,25,23,0.35)`.
- **Katmanlama**: bg → canvas (beyaz kart) → surface → surface2. Hover yüzey değişimiyle olur.
- **Border**: 1px `var(--color-border)`; gölge + border birlikte abartılmaz (ikisinden biri baskın).
- **Radius**: 8px küçük, 12px kart/modal.
- **Accent seyreklik**: koralj yalnızca primary buton, aktif durum, odak halkası, tek vurgu noktası. Marka gradyanı: `linear-gradient(135deg, #c96442, #b8532f 60%, #a34628)`.
- **Font**: `var(--font-sans)` (Inter), `var(--font-mono)` (IBM Plex Mono). Bölüm başlıkları 9.5-10.5px uppercase letter-spacing 0.05em `--color-faint`.
- **Grafikler**: Plotly şablonu tema-duyarlı — dark → `plotly_dark` benzeri açık metin, light → `plotly_white`. Backend (`app/core/visualizer.py`) artık nötr üretir (`plotly_white`, orta gri metin, şeffaf zemin); tema stili frontend'te uygulanır.

## Yapısal kurallar (deneyim kararları)

- **İki mod**: Sohbet görünümü varsayılan **tek kolon** — sonuçlar (grafik/tablo/kod) agent mesajının içinde (InlineResult). **Stüdyo** (`store.studioMode`, topbar toggle) kullanıcı istediğinde sağ paneli açar; split asla zorunlu değil.
- **Akış görünürlüğü**: komposerda **kaynak çipi** (aktif kaynak adı, tıkla → seçici açılır; kaynak yoksa "＋ Kaynak seç" vurgulu). Boş ekranda **3 adımlı rehber**: ① Kaynak seç → ② Sorunu yaz → ③ Sonucu keşfet.
- **Tek navigasyon merkezi**: görünüm geçişleri yalnızca üst navbar segmented switcher'da (Sohbet/Dashboard/RAG/Ayarlar) + dil/tema/Stüdyo toggle'ları. Sidebar: marka, oturum listesi, aktif veri kümesi, kullanıcı kartı + çıkış.
- **Ayarlar tam sayfa** (`SettingsPage.tsx`), bölüm-nav düzenli.
- **Boş durumlar dolgu üretmez**: otomatik "Varsayılan Sohbet" gibi yapay kayıt yok; hero + adım rehberi + örnek çipler.
- **Zustand**: full-store destructuring yasak — alan başına selector (`useBIStore(s => s.x)`).
- **REST**: ad-hoc `fetch` değil `apiFetch` (`src/api/client.ts`); ham Response gereken yerde (blob/SSE) token'ı `getAuthToken()` ile elle ekle.
- **MUI**: ağır bileşenler (Dialog/Select) için ok; basit bileşenler inline style + token (LoginPage üslubu).

## İş akışı kuralları

- Sadece stil isteniyorsa mantığa dokunma: handler/state/koşul birebir kalır.
- Her stil işi sonrası `npx tsc -p tsconfig.app.json --noEmit` temiz olmalı; bütünlük için `npm run build`.
- Büyük restyle'da paralel ajan kullanılabilir; her ajana mutlak dosya sahipliği sınırı ver.

## Yeni bileşen şablonu

```tsx
<div style={{
  background: 'var(--color-canvas)',
  border: '1px solid var(--color-border)',
  borderRadius: 12,
  boxShadow: '0 2px 6px rgba(28,25,23,0.06)',
  padding: 16,
}}>
  <div style={{
    fontSize: 10, fontWeight: 600, color: 'var(--color-faint)',
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10,
  }}>
    BÖLÜM BAŞLIĞI
  </div>
  {/* içerik: metin --color-text/--color-muted, vurgu --color-accent-fg */}
</div>
```
