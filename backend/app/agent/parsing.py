"""Slash-command parsing and intent-keyword dispatch helpers for SupervisorAgent.

Pure functions extracted mechanically from the router logic in supervisor.py.
No behavior change: same command table, same match semantics, same outputs.
"""
from typing import Dict, Any, List, Optional, Tuple
import re

from app.core.intent_keywords import (
    CONCEPTUAL_POSITIVE, CONCEPTUAL_NEGATIVE,
    PYTHON_ML_KEYWORDS, FORECAST_KEYWORDS, ANOMALY_KEYWORDS,
    CORRELATION_KEYWORDS, CLUSTERING_KEYWORDS, LISTING_KEYWORDS,
)

# Exact command mappings for Autocomplete commands, then Legacy/Alias mappings.
# Order matters: it mirrors the original startswith ladder in supervisor.py.
# (command, forced_intent, status_label, strip_len, sets_is_ml)
SLASH_COMMAND_TABLE = [
    # Exact command mappings for Autocomplete commands
    ("/graph", "file_analysis", "FILE_ANALYSIS (Görsel Grafik Çizimi)", 6, False),
    ("/ask", "ask", "ASK (Soru-Cevap + Metin Özeti)", 4, False),
    ("/ml", "file_analysis", "FILE_ANALYSIS (Makine Öğrenmesi)", 3, True),
    ("/table", "sql_query", "SQL_QUERY (Tablo Listeleme)", 6, False),
    ("/sqlquery", "sql_query", "SQL_QUERY (SQL Sorgusu)", 9, False),
    ("/pythonscript", "file_analysis", "FILE_ANALYSIS (Python Script)", 13, False),
    ("/explain", "explain", "EXPLAIN (Veri Kümesi Açıklaması)", 8, False),
    ("/forecast", "file_analysis", "FILE_ANALYSIS (Zaman Serisi Tahmini)", 9, True),
    ("/clean", "file_analysis", "FILE_ANALYSIS (Veri Temizleme & Keşif)", 6, False),
    ("/pivot", "file_analysis", "FILE_ANALYSIS (Dinamik Pivot Analizi)", 6, False),
    ("/corr", "file_analysis", "FILE_ANALYSIS (Korelasyon Analizi)", 5, False),
    ("/help", "help", "HELP (Kullanım Rehberi)", 5, False),
    # Legacy/Alias mappings
    ("/python", "file_analysis", "FILE_ANALYSIS (Python/Pandas)", 7, False),
    ("/sql", "sql_query", "SQL_QUERY", 4, False),
    ("/sorgu", "sql_query", "SQL_QUERY", 6, False),
    ("/sor", "ask", "ASK (Soru-Cevap + Metin Özeti)", 4, False),
    ("/bilgi", "conceptual", "CONCEPTUAL (Kavramsal Bilgi)", 6, False),
    ("/konsept", "conceptual", "CONCEPTUAL (Kavramsal Bilgi)", 8, False),
    ("/rapor", "report", "REPORT (Gelişmiş Raporlama)", 6, False),
    ("/report", "report", "REPORT (Gelişmiş Raporlama)", 7, False),
]


def match_slash_command(cleaned_question: str) -> Optional[Tuple[str, str, bool, str]]:
    """Match a manual slash command.

    Returns (forced_intent, cleaned_question, is_ml, status_label) when the
    question starts with a known slash command, otherwise None.
    Equivalent to the original startswith ladder:
        startswith("/cmd ") or == "/cmd"
    """
    for cmd, intent, label, strip_len, sets_ml in SLASH_COMMAND_TABLE:
        if cleaned_question.startswith(cmd + " ") or cleaned_question == cmd:
            return intent, cleaned_question[strip_len:].strip(), sets_ml, label
    return None


def is_conceptual_question(q_low: str) -> bool:
    """Conceptual question heuristic — intent_keywords.py merkezi listeleri."""
    return (
        any(kw in q_low for kw in CONCEPTUAL_POSITIVE)
        and not any(kw in q_low for kw in CONCEPTUAL_NEGATIVE)
    )


def route_heuristic_intent(q_low: str, is_file_source: bool) -> Tuple[str, bool]:
    """Heuristic routing for non-slash, non-conceptual questions.

    Returns (intent, is_ml).
    """
    wants_python = any(kw in q_low for kw in PYTHON_ML_KEYWORDS)

    if wants_python or (is_file_source and any(kw in q_low for kw in FORECAST_KEYWORDS + ANOMALY_KEYWORDS + CORRELATION_KEYWORDS)):
        intent = "file_analysis"
        is_ml = wants_python or any(kw in q_low for kw in FORECAST_KEYWORDS + ANOMALY_KEYWORDS + CLUSTERING_KEYWORDS)
    else:
        intent = "sql_query"
        is_ml = False
    return intent, is_ml


def detect_analysis_intents(q_low: str) -> Dict[str, bool]:
    """Detect prediction, anomaly, correlation, clustering and listing intents."""
    return {
        "is_forecast": any(kw in q_low for kw in FORECAST_KEYWORDS),
        "is_anomaly": any(kw in q_low for kw in ANOMALY_KEYWORDS),
        "is_correlation": any(kw in q_low for kw in CORRELATION_KEYWORDS),
        "is_clustering": any(kw in q_low for kw in CLUSTERING_KEYWORDS),
        "is_listing": any(kw in q_low for kw in LISTING_KEYWORDS),
    }


def extract_cluster_count(q_low: str, default: int = 3) -> int:
    """Parse an explicit cluster/segment count from the question, e.g. '5 küme'."""
    match = re.search(r'(\d+)\s*(küme|segment|cluster)', q_low)
    if match:
        try:
            return int(match.group(1))
        except Exception:
            pass
    return default


# ── Komut → bayrak zorlaması ve Coder yönergeleri ────────────────────────────
# Komutlar yalnızca yönü belirlememeli; özel davranışları (tahmin modeli,
# korelasyon matrisi...) kalan metindeki anahtar kelime şansına bırakılmamalı.
# Bu eşleme, komut görüldüğünde detect_analysis_intents sonuçlarının ÜZERİNE
# zorla OR'lanır.
COMMAND_FORCED_FLAGS: Dict[str, Dict[str, bool]] = {
    "/forecast": {"is_forecast": True},
    "/corr": {"is_correlation": True},
    "/ml": {},  # is_ml zaten tabloda
    # /pivot ve /clean için özel yürütme yok; yönerge metni Coder'a gider
}

# Komut bazlı Coder yönergeleri — üretilecek koda net talimat olarak eklenir.
COMMAND_DIRECTIVES: Dict[str, str] = {
    "/pivot": (
        "Bu istek DİNAMİK PİVOT analizidir: kullanıcı 'x' ile ayırdığı kolonları "
        "kullanarak pivot_table (index, columns, values, aggfunc) üret ve alt toplamlar "
        "(margins=True) ekle. Sonucu 'result' değişkenine DataFrame olarak ata."
    ),
    "/clean": (
        "Bu istek VERİ TEMİZLİK ve KEŞİF analizidir: her kolon için eksik değer sayısı "
        "(isna), tekrarlanan satır sayısı (duplicated), sayısal kolonlarda aykırı değer "
        "(IQR yöntemi) tespiti ve önerilen temizleme adımlarını içeren bir özet DataFrame üret."
    ),
    "/corr": (
        "Bu istek KORELASYON analizidir: yalnızca sayısal kolonlar arası Pearson "
        "korelasyon matrisi üret. result = df.select_dtypes('number').corr()"
    ),
    "/forecast": (
        "Bu istek ZAMAN SERİSİ TAHMİNİdir: tarih/zaman kolonunu sırala, sayısal hedef kolonu "
        "içeren bir zaman serisi üret; result'a gerçek + tahmin değerlerini içeren DataFrame ata."
    ),
    "/graph": (
        "Bu istek GÖRSELLEŞTİRME odaklıdır: 'fig' değişkenine uygun bir Plotly grafiği ata."
    ),
}


def find_command(cleaned_question: str) -> Optional[str]:
    """Sorunun başındaki komutu döndürür (yoksa None)."""
    for cmd, *_rest in SLASH_COMMAND_TABLE:
        if cleaned_question.startswith(cmd + " ") or cleaned_question == cmd:
            return cmd
    return None


def command_flags(command: str) -> Dict[str, bool]:
    """Komutun zorladığı analysis bayrakları (detect_analysis_intents üzerine OR'lanır)."""
    return dict(COMMAND_FORCED_FLAGS.get(command, {}))


def command_directive(command: str) -> Optional[str]:
    """Komutun Coder prompt'una eklenecek yönerge metni (yoksa None)."""
    return COMMAND_DIRECTIVES.get(command)
