"""
app/core/sql_sanitizer.py

Tüm SQL statement'ları (çoklu statement desteği) güvenli şekilde doğrular.
Sadece SELECT / WITH / UNION (read-only) sorgulara izin verir.
Tehlikeli komutlar: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, COPY,
ATTACH, DETACH, EXPORT, IMPORT, CALL, PRAGMA (DuckDB-specific).
"""
import re
import sqlglot
from sqlglot import exp

class SQLSanitationError(Exception):
    pass

# DuckDB'ye özgü tehlikeli anahtar kelimeler (sqlglot AST'ında Command olarak parse edilir)
_DUCKDB_DANGEROUS_KEYWORDS = re.compile(
    r"""
    ^\s*(?:
        COPY | ATTACH | DETACH | EXPORT | IMPORT |
        INSTALL | LOAD | SET\s+(?!search_path) |
        CALL | PRAGMA | CHECKPOINT | VACUUM |
        BEGIN | COMMIT | ROLLBACK | SAVEPOINT |
        USE\b
    )\b
    """,
    re.IGNORECASE | re.VERBOSE
)

# Güvensiz AST node tipleri — bunların hiçbiri read-only değil
_UNSAFE_TYPES = (
    exp.Insert, exp.Update, exp.Delete,
    exp.Drop, exp.Alter, exp.Create,
    exp.Command, exp.Transaction,
)


def _validate_single_statement(expression: exp.Expression, original_sql: str) -> None:
    """
    Tek bir sqlglot expression'ı denetler.
    Unsafe node tipi veya DuckDB tehlikeli komutu bulursa SQLSanitationError fırlatır.
    """
    # 1. Regex tabanlı ön kontrol (ATTACH, COPY, PRAGMA, vb.)
    if _DUCKDB_DANGEROUS_KEYWORDS.search(original_sql):
        first_word = original_sql.strip().split()[0].upper()
        raise SQLSanitationError(
            f"Güvenlik İhlali: '{first_word}' komutu bu ortamda çalıştırılamaz. "
            f"Sadece veri okuma (SELECT) sorgularına izin verilir."
        )

    # 2. AST tabanlı kontrol — her node'u gez
    for node in expression.walk():
        if isinstance(node, _UNSAFE_TYPES):
            raise SQLSanitationError(
                f"Güvenlik İhlali: Sorgu sadece veri okuma (SELECT) yapabilir. "
                f"Tehlikeli işlem algılandı: {node.__class__.__name__}"
            )

def _map_db_type_to_sqlglot_dialect(db_type: Optional[str]) -> Optional[str]:
    if not db_type:
        return None
    t = db_type.lower()
    if t in ("postgresql", "postgres"):
        return "postgres"
    if t in ("mysql", "mariadb"):
        return "mysql"
    if t in ("sap_s4hana", "hana", "s4hana"):
        return "hana"
    if t in ("mssql", "sqlserver"):
        return "tsql"
    if t in ("bigquery", "google_bigquery"):
        return "bigquery"
    if t == "snowflake":
        return "snowflake"
    if t == "sqlite":
        return "sqlite"
    return None


def sanitize_and_validate_sql(sql_query: str, default_limit: int = 5000, db_type: Optional[str] = None) -> str:
    """
    Parses ALL statements in the SQL string using sqlglot, verifies every
    statement is read-only (SELECT/WITH/UNION), and enforces a maximum row
    limit on the primary statement.

    Raises SQLSanitationError on any violation.
    Returns the validated (and possibly limit-injected) SQL string.
    """
    # ── Temizle ──────────────────────────────────────────────────────────────
    cleaned_sql = sql_query.strip().strip(";").strip()

    read_dialect = _map_db_type_to_sqlglot_dialect(db_type)

    # Çoklu statement kontrolü: ";" ile ayrılmış ifadeler
    # (quoted string içindeki ";" ile karışmaması için basit split yeterli;
    #  sqlglot parse() zaten hepsini döndürür)
    try:
        parsed_expressions = sqlglot.parse(cleaned_sql, read=read_dialect)
    except Exception as e:
        raise SQLSanitationError(f"SQL Ayrıştırma Hatası: Geçersiz SQL yazımı. Detay: {str(e)}")

    if not parsed_expressions or parsed_expressions[0] is None:
        raise SQLSanitationError("Sorgu boş veya ayrıştırılamadı.")

    # ── Tüm statement'ları doğrula ─────────────────────────────────────────
    if len(parsed_expressions) > 1:
        raise SQLSanitationError(
            f"Güvenlik İhlali: Birden fazla SQL ifadesi (statement) tespit edildi "
            f"({len(parsed_expressions)} adet). Sadece tek bir SELECT sorgusu gönderin."
        )

    expression = parsed_expressions[0]

    # Her statement için tam AST + regex denetimi
    _validate_single_statement(expression, cleaned_sql)

    # ── LIMIT zorlama (yalnızca birincil SELECT) ────────────────────────────
    limit_node = expression.find(exp.Limit)
    has_limit = False

    if limit_node:
        has_limit = True
        try:
            val = int(str(limit_node.expression))
            if val > default_limit:
                limit_node.set("expression", exp.Literal.number(default_limit))
        except (ValueError, AttributeError):
            limit_node.set("expression", exp.Literal.number(default_limit))

    if not has_limit:
        if hasattr(expression, "limit"):
            expression = expression.limit(default_limit)
            has_limit = True

    modified_sql = expression.sql(dialect=read_dialect)

    if not has_limit and "limit" not in modified_sql.lower() and "top" not in modified_sql.lower():
        modified_sql = f"{modified_sql} LIMIT {default_limit}"

    return modified_sql

