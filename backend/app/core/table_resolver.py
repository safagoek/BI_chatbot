"""
app/core/table_resolver.py

SQL sorgusunda referans edilen tablo adlarını çıkaran ve izinli tablo
listesine göre fuzzy-match tabanlı otomatik düzeltme yapan paylaşılan modül.

Supervisor (chat akışı) ve sessions router (kullanıcının düzenlediği kodu
çalıştırma) aynı davranışı kullanır; eşik parametreleri burada tek noktadan
yönetilir.
"""
import re
from typing import Dict, List, Set, Tuple

# Eşikler: yüksek eşleşme güvenli kabul edilir; iki aday arasındaki skor
# farkı margin'den küçükse eşleşme belirsiz sayılır.
DEFAULT_CUTOFF = 0.72
DEFAULT_MARGIN = 0.20

_TABLE_REF_PATTERN = re.compile(r"\bfrom\s+([\w\"\'\.]+)|\bjoin\s+([\w\"\'\.]+)", re.IGNORECASE)


def extract_table_refs(sql: str) -> Set[str]:
    """SQL'deki FROM/JOIN ile referans edilen tablo adlarını (küçük harf) döndürür."""
    refs = set()
    for m in _TABLE_REF_PATTERN.finditer(sql):
        t = m.group(1) or m.group(2)
        if not t:
            continue
        t_clean = t.strip().strip('"').strip("'")
        # Alias'ı ve şema önekini (ör. db.tablo) at
        t_clean = t_clean.split()[:1][0]
        if "." in t_clean:
            t_clean = t_clean.split(".")[-1]
        if t_clean:
            refs.add(t_clean.lower())
    return refs


def resolve_unknown_tables(
    sql: str,
    allowed_tables: Set[str],
    cutoff: float = DEFAULT_CUTOFF,
    margin: float = DEFAULT_MARGIN,
) -> Tuple[str, Dict[str, str], List[str], List[str]]:
    """
    Bilinmeyen tablo referanslarını izinli tablolara fuzzy-match ile düzeltir.

    Returns:
        (corrected_sql, corrections, ambiguous, unknown)
        corrections: {yanlış_ad: düzeltilmiş_ad}
        ambiguous:   birden fazla adaya eşit yakınlıkta olan, düzeltilemeyen adlar
        unknown:     sorguda geçen ama izinli listede olmayan tüm adlar
    """
    import difflib

    allowed_map = {t.lower(): t for t in allowed_tables}
    refs = extract_table_refs(sql)
    unknown = [r for r in refs if r and r not in allowed_map]

    corrections: Dict[str, str] = {}
    ambiguous: List[str] = []
    for u in unknown:
        candidates = difflib.get_close_matches(u, list(allowed_map.keys()), n=2, cutoff=cutoff)
        if len(candidates) == 1:
            corrections[u] = allowed_map[candidates[0]]
        elif len(candidates) > 1:
            score0 = difflib.SequenceMatcher(None, u, candidates[0]).ratio()
            score1 = difflib.SequenceMatcher(None, u, candidates[1]).ratio()
            if abs(score0 - score1) > margin:
                corrections[u] = allowed_map[candidates[0] if score0 > score1 else candidates[1]]
            else:
                ambiguous.append(u)
        else:
            ambiguous.append(u)

    corrected = sql
    for src, tgt in corrections.items():
        try:
            corrected = re.sub(rf"\b{re.escape(src)}\b", tgt, corrected, flags=re.IGNORECASE)
        except Exception:
            pass

    return corrected, corrections, ambiguous, unknown
