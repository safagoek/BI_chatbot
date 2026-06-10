"""
tests/test_sql_sanitizer.py

SQL sanitizasyon modülü için temel güvenlik testleri.
Çalıştırma: cd backend && python -m pytest tests/ -v
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.sql_sanitizer import sanitize_and_validate_sql, SQLSanitationError


class TestSQLSanitizer:
    """SQL injection ve tehlikeli komut testleri."""

    def test_simple_select_passes(self):
        """Basit SELECT sorgusu geçmeli."""
        result = sanitize_and_validate_sql("SELECT * FROM orders")
        assert result is not None
        assert "SELECT" in result.upper()

    def test_drop_table_blocked(self):
        """DROP TABLE engellenmeli."""
        with pytest.raises(SQLSanitationError):
            sanitize_and_validate_sql("DROP TABLE orders")

    def test_delete_blocked(self):
        """DELETE komutu engellenmeli."""
        with pytest.raises(SQLSanitationError):
            sanitize_and_validate_sql("DELETE FROM orders WHERE 1=1")

    def test_insert_blocked(self):
        """INSERT komutu engellenmeli."""
        with pytest.raises(SQLSanitationError):
            sanitize_and_validate_sql("INSERT INTO orders VALUES (1, 'test')")

    def test_update_blocked(self):
        """UPDATE komutu engellenmeli."""
        with pytest.raises(SQLSanitationError):
            sanitize_and_validate_sql("UPDATE orders SET amount=0")

    def test_create_table_blocked(self):
        """CREATE TABLE engellenmeli."""
        with pytest.raises(SQLSanitationError):
            sanitize_and_validate_sql("CREATE TABLE hacked (id INT)")

    def test_union_allowed(self):
        """UNION sorgusu read-only olduğu için izin verilmeli."""
        result = sanitize_and_validate_sql(
            "SELECT * FROM orders UNION SELECT username, password, null FROM users"
        )
        assert result is not None

    def test_comment_injection_handled(self):
        """SQL comment injection güvenle işlenmeli ve AST düzeyinde DROP içermemeli."""
        result = sanitize_and_validate_sql("SELECT * FROM orders--; DROP TABLE orders")
        import sqlglot
        from sqlglot import exp
        parsed = sqlglot.parse_one(result)
        assert parsed.find(exp.Drop) is None

    def test_semicolon_multiple_statements(self):
        """Birden fazla SQL ifadesi engellenmeli."""
        with pytest.raises((SQLSanitationError, Exception)):
            sanitize_and_validate_sql("SELECT * FROM orders; DROP TABLE orders")

    def test_with_cte_allowed(self):
        """WITH (CTE) sorgusu izin verilmeli."""
        result = sanitize_and_validate_sql(
            "WITH summary AS (SELECT id, SUM(amount) FROM orders GROUP BY id) SELECT * FROM summary"
        )
        assert result is not None

    def test_aggregate_query_allowed(self):
        """Aggregate sorgular geçmeli."""
        result = sanitize_and_validate_sql(
            "SELECT category, COUNT(*), AVG(amount) FROM orders GROUP BY category ORDER BY 2 DESC"
        )
        assert result is not None

    def test_subquery_allowed(self):
        """Alt sorgu içeren SELECT geçmeli."""
        result = sanitize_and_validate_sql(
            "SELECT * FROM orders WHERE amount > (SELECT AVG(amount) FROM orders)"
        )
        assert result is not None


class TestCryptoModule:
    """Şifreleme modülü testleri."""

    def test_encrypt_decrypt_roundtrip(self):
        """Şifreleme → Çözme round-trip doğru sonuç vermeli."""
        try:
            from app.core.crypto import encrypt_password, decrypt_password
            plain = "my_secret_password_123"
            encrypted = encrypt_password(plain)
            assert encrypted != plain, "Şifreli değer düz metinden farklı olmalı"
            decrypted = decrypt_password(encrypted)
            assert decrypted == plain, "Çözülen değer orijinaliyle eşleşmeli"
        except ImportError:
            pytest.skip("cryptography paketi yüklü değil")

    def test_empty_password_handled(self):
        """Boş şifre güvenle işlenmeli."""
        from app.core.crypto import encrypt_password, decrypt_password
        assert encrypt_password("") == ""
        assert decrypt_password("") == ""

    def test_none_password_handled(self):
        """None şifre güvenle işlenmeli."""
        from app.core.crypto import encrypt_password, decrypt_password
        assert encrypt_password(None) == ""
        assert decrypt_password(None) == ""

    def test_already_encrypted_not_double_encrypted(self):
        """Zaten şifrelenmiş değer tekrar şifrelenmemeli."""
        try:
            from app.core.crypto import encrypt_password
            plain = "test_password"
            enc1 = encrypt_password(plain)
            enc2 = encrypt_password(enc1)
            # İkinci şifreleme aynı sonucu vermeli (idempotent)
            assert enc1 == enc2
        except ImportError:
            pytest.skip("cryptography paketi yüklü değil")

    def test_mask_password(self):
        """Şifre maskeleme UI güvenliği sağlamalı."""
        from app.core.crypto import mask_password
        details = {"host": "localhost", "password": "super_secret", "username": "admin"}
        masked = mask_password(details)
        assert masked["password"] == "••••••••"
        assert masked["host"] == "localhost"  # Diğer alanlar değişmemeli
        assert details["password"] == "super_secret"  # Orijinal değişmemeli


class TestIntentKeywords:
    """Intent keyword listeleri testleri."""

    def test_conceptual_keywords_not_empty(self):
        """Kavramsal keyword listesi boş olmamalı."""
        from app.core.intent_keywords import CONCEPTUAL_POSITIVE, CONCEPTUAL_NEGATIVE
        assert len(CONCEPTUAL_POSITIVE) > 5
        assert len(CONCEPTUAL_NEGATIVE) > 3

    def test_python_ml_keywords_not_empty(self):
        """Python/ML keyword listesi boş olmamalı."""
        from app.core.intent_keywords import PYTHON_ML_KEYWORDS
        assert len(PYTHON_ML_KEYWORDS) > 10

    def test_forecast_trigger(self):
        """'tahmin' kelimesi forecast listesinde olmalı."""
        from app.core.intent_keywords import FORECAST_KEYWORDS
        q = "gelecek ay satış tahmini"
        assert any(kw in q for kw in FORECAST_KEYWORDS)

    def test_conceptual_trigger(self):
        """'nedir' sorusu conceptual olarak algılanmalı."""
        from app.core.intent_keywords import CONCEPTUAL_POSITIVE, CONCEPTUAL_NEGATIVE
        q = "makine öğrenmesi nedir"
        is_conceptual = any(kw in q for kw in CONCEPTUAL_POSITIVE) and not any(kw in q for kw in CONCEPTUAL_NEGATIVE)
        assert is_conceptual

    def test_conceptual_blocked_by_negative(self):
        """'Göster' içeren soru conceptual OLMAMALI."""
        from app.core.intent_keywords import CONCEPTUAL_POSITIVE, CONCEPTUAL_NEGATIVE
        q = "en iyi ürünleri göster"
        is_conceptual = any(kw in q for kw in CONCEPTUAL_POSITIVE) and not any(kw in q for kw in CONCEPTUAL_NEGATIVE)
        # "göster" CONCEPTUAL_NEGATIVE'de, dolayısıyla False bekliyoruz
        # (veya positive'de hiç match yok)
        assert not is_conceptual
