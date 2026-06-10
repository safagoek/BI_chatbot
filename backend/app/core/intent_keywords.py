"""
app/core/intent_keywords.py

Intent yönlendirme için anahtar kelime listeleri.
supervisor.py içinde hardcoded olan tüm keyword listelerini merkezi olarak yönetir.
Yeni dil veya terim eklemek için sadece bu dosyayı düzenlemek yeterlidir.
"""

# ---------------------------------------------------------------------------
# CONCEPTUAL (Kavramsal bilgi / açıklama) sorguları
# ---------------------------------------------------------------------------
CONCEPTUAL_POSITIVE = [
    # Türkçe
    "tahminleyebiliriz", "tahmin edebiliriz", "neleri", "neler yapabiliriz",
    "nedir", "nelerdir", "nasıl çalışır", "nasıl calisir", "ne demektir",
    "ne işe yarar", "ne ise yarar", "bilgi ver", "tanımla", "öğret",
    "neden olur", "anlamı ne", "kavram", "teori", "anlat", "ne anlama",
    # İngilizce
    "what is", "how does", "explain", "what are", "definition of",
    "how it works", "tell me about", "describe",
]

# Conceptual sinyali baskılayan keyword'ler — bunlar varsa sql/python'a yönlendir
CONCEPTUAL_NEGATIVE = [
    "göster", "listele", "hesapla", "çiz", "grafik", "tablo", "kaç",
    "toplam", "ortalama", "yarat", "oluştur", "sorgula", "top 5", "limit",
    "show", "list", "calculate", "chart", "count", "sum", "average", "create",
]

# ---------------------------------------------------------------------------
# PYTHON / ML / Pandas analiz sorguları
# ---------------------------------------------------------------------------
PYTHON_ML_KEYWORDS = [
    # ML & AI
    "python", "pandas", "makine öğrenmesi", "makine ogrenmesi",
    "machine learning", "ml", "yapay zeka", "yapay zekâ",
    "model", "regresyon", "sınıflandırma", "siniflandirma",
    "kümeleme", "kumeleme", "clustering",
    # İstatistik
    "korelasyon", "correlation", "heatmap", "anomali", "anomaly",
    "aykırı", "outlier",
    # Tahmin / Forecast
    "tahmin", "tahminleme", "tahminlemesi", "öngörü", "ongoru",
    "forecast", "forecasting", "predict", "predictive", "prediction",
    "projection", "projeksiyon",
    # Zaman ifadeleri (forecast bağlamında)
    "satacağım", "satacagim", "satıcam", "saticam",
    "satacağız", "satacagiz",
    "gelecek ay", "gelecek yil", "gelecek yıl",
    "önümüzdeki ay", "onumuzdeki ay",
    "önümüzdeki yıl", "onumuzdeki yil",
    "gelecek dönem", "gelecek donem",
    # İş analitiği
    "churn", "müşteri kaybı", "musteri kaybi",
]

# ---------------------------------------------------------------------------
# FORECAST (Zaman serisi tahmini) bağlam keyword'leri
# ---------------------------------------------------------------------------
FORECAST_KEYWORDS = [
    "tahmin", "forecast", "predict", "projeksiyon", "gelecek",
    "prediction", "forecasting",
]

# ---------------------------------------------------------------------------
# ANOMALY (Anomali tespiti) keyword'leri
# ---------------------------------------------------------------------------
ANOMALY_KEYWORDS = [
    "anomali", "aykırı", "outlier", "sapma", "anomaly",
]

# ---------------------------------------------------------------------------
# CORRELATION (Korelasyon analizi) keyword'leri
# ---------------------------------------------------------------------------
CORRELATION_KEYWORDS = [
    "korelasyon", "ilişki", "heatmap", "correlation",
]

# ---------------------------------------------------------------------------
# CLUSTERING (Kümeleme analizi) keyword'leri
# ---------------------------------------------------------------------------
CLUSTERING_KEYWORDS = [
    "kümeleme", "segmentasyon", "segment", "cluster", "clustering",
]

# ---------------------------------------------------------------------------
# LISTING (Listeleme / Tablo gösterimi) keyword'leri
# Bunlar grafik yerine tablo çıktısı üretmeli
# ---------------------------------------------------------------------------
LISTING_KEYWORDS = [
    "göster", "listele", "getir", "örnek", "sample", "random", "rastgele",
    "ilk", "first", "son", "last", "tüm", "all", "tümünü", "hepsini",
    "satır", "row", "kayıt", "record", "veri göster", "veri getir",
]

# ---------------------------------------------------------------------------
# Intent keyword grupları (RAG retrieve_similar için)
# ---------------------------------------------------------------------------
INTENT_KEYWORD_GROUPS = {
    "trend": [
        "trend", "tarih", "zaman", "ay", "yıl", "gun", "gün",
        "seri", "line", "çizgi",
    ],
    "top": [
        "en çok", "en yüksek", "en büyük", "top", "limit",
        "en iyi", "en fazla", "en az", "en düşük",
        "en cok", "en yuksek", "en buyuk", "en dusuk",
    ],
    "distribution": [
        "dağılım", "kategori", "grup", "oran", "pasta", "pie",
        "yüzde", "dagilim", "yuzde",
    ],
}
