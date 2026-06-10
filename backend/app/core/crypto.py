"""
app/core/crypto.py

Fernet tabanlı simetrik şifreleme — veritabanı bağlantı şifrelerini güvenle saklar.
SECRET_KEY'den SHA-256 ile 32-byte anahtar türetir.

Kullanım:
    from app.core.crypto import encrypt_password, decrypt_password

    enc = encrypt_password("my_secret")
    dec = decrypt_password(enc)  # "my_secret"
"""
import os
import base64
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Boş string veya None şifrelenirse olduğu gibi döner
_EMPTY_SENTINEL = ""

# Şifrelenmiş değer prefix — düz metin ile şifreli ayrımı için
_ENC_PREFIX = "enc:"


def _get_fernet():
    """Lazy Fernet örneği — cryptography kütüphanesi opsiyonel."""
    try:
        from cryptography.fernet import Fernet
        from app.core.config import settings
        # SECRET_KEY'den 32-byte Fernet anahtarı türet
        raw_key = settings.secret_key.encode("utf-8")
        hashed = hashlib.sha256(raw_key).digest()
        fernet_key = base64.urlsafe_b64encode(hashed)
        return Fernet(fernet_key)
    except ImportError:
        logger.warning("cryptography paketi yüklü değil, şifreleme devre dışı.")
        return None
    except Exception as e:
        logger.error(f"Fernet başlatılamadı: {e}")
        return None


def encrypt_password(plain: Optional[str]) -> str:
    """
    Şifreyi Fernet ile şifreler ve `enc:<base64>` formatında döndürür.
    cryptography paketi yoksa plain metni döndürür (graceful degradation).
    """
    if not plain:
        return _EMPTY_SENTINEL

    # Zaten şifrelenmiş mi?
    if plain.startswith(_ENC_PREFIX):
        return plain

    fernet = _get_fernet()
    if fernet is None:
        return plain  # Şifrelenememişse düz metin — loglama yeterli

    try:
        encrypted = fernet.encrypt(plain.encode("utf-8")).decode("utf-8")
        return f"{_ENC_PREFIX}{encrypted}"
    except Exception as e:
        logger.error(f"Şifreleme başarısız: {e}")
        return plain  # Güvenli fallback


def decrypt_password(encrypted: Optional[str]) -> str:
    """
    `enc:<base64>` formatındaki şifreli değeri çözer.
    Düz metin veya boş string gelirse olduğu gibi döner (geriye dönük uyumluluk).
    """
    if not encrypted:
        return _EMPTY_SENTINEL

    # Prefix yoksa düz metin (eski kayıt) — olduğu gibi döndür
    if not encrypted.startswith(_ENC_PREFIX):
        return encrypted

    fernet = _get_fernet()
    if fernet is None:
        # Çözümleme yapılamıyor — prefix'i kaldırarak ham değeri döndür
        return encrypted[len(_ENC_PREFIX):]

    try:
        raw = encrypted[len(_ENC_PREFIX):]
        return fernet.decrypt(raw.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.warning(f"Şifre çözme başarısız (eski düz metin kaydı olabilir): {e}")
        # Son çare: prefix kaldırarak ham değer
        return encrypted[len(_ENC_PREFIX):]


def mask_password(connection_details: dict) -> dict:
    """
    connection_details dict içindeki şifre alanlarını UI görüntüleme için maskeler.
    Orijinal dict'i değiştirmez, kopyasını döndürür.
    """
    masked = dict(connection_details)
    for key in ("password", "passwd", "pwd", "secret", "private_key"):
        if key in masked and masked[key]:
            masked[key] = "••••••••"
    return masked
