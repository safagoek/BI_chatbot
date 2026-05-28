"""
app/core/config.py
Pydantic BaseSettings tabanlı type-safe ortam değişkeni yöneticisi.
Uygulama genelinde `from app.core.config import settings` ile kullanılır.
"""
import os
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # === LLM ===
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-coder"

    # === Server ===
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    secret_key: str = "changeme_super_secret_key_32chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # === Storage ===
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50
    allowed_extensions: str = ".xlsx,.xls,.csv,.tsv"

    # === Sandbox ===
    sandbox_timeout_seconds: float = 10.0
    sandbox_max_memory_mb: int = 512

    # === RAG ===
    memory_file: str = "./query_memory.json"
    rag_top_k: int = 3
    rag_max_correct_attempts: int = 3

    # === Logging ===
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # === Remote DB ===
    pg_host: Optional[str] = None
    pg_port: int = 5432
    pg_db: Optional[str] = None
    pg_user: Optional[str] = None
    pg_password: Optional[str] = None

    mysql_host: Optional[str] = None
    mysql_port: int = 3306
    mysql_db: Optional[str] = None
    mysql_user: Optional[str] = None
    mysql_password: Optional[str] = None

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()]


# Global singleton
settings = Settings()
