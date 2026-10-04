"""
tests/conftest.py

pytest konfigürasyon dosyası.
- app/ dizinindeki üretim kodundaki test_ prefix'li fonksiyonların
  yanlışlıkla toplanmasını engeller.
- Tüm testleri İZOLE bir metadata DB'ye yönlendirir: gerçek metadata.db
  (kullanıcılar, şifreler, kaynaklar) testlerden asla etkilenmez.
"""

import os
import sys
import tempfile

# Uygulama modülleri import edilmeden ÖNCE env ayarlanmalı —
# manager.DB_PATH import zamanında çözülür.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="deepbi_test_db_")
os.environ["DEEPBI_METADATA_DB"] = os.path.join(_TEST_DB_DIR, "test_metadata.db")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

collect_ignore_glob = ["../app/**/*.py"]
