"""
Unit tests for production configuration, database URL normalization, and CORS origins parsing.
"""

import pytest
from app.core.config import Settings


def test_cors_origins_list_parsing():
    # 1. Default list
    s1 = Settings()
    assert "http://localhost:3000" in s1.cors_origins_list

    # 2. JSON array string
    s2 = Settings(BACKEND_CORS_ORIGINS='["https://tripwiser.vercel.app", "https://custom.domain.com"]')
    assert s2.cors_origins_list == ["https://tripwiser.vercel.app", "https://custom.domain.com"]

    # 3. Comma-separated string
    s3 = Settings(BACKEND_CORS_ORIGINS="https://app.vercel.app, https://preview.vercel.app")
    assert s3.cors_origins_list == ["https://app.vercel.app", "https://preview.vercel.app"]

    # 4. Native list
    s4 = Settings(BACKEND_CORS_ORIGINS=["https://tripwiser.vercel.app"])
    assert s4.cors_origins_list == ["https://tripwiser.vercel.app"]


def test_async_database_url_normalization():
    # 1. Standard postgresql+asyncpg passes through
    s1 = Settings(DATABASE_URL="postgresql+asyncpg://tripwiser:secret@localhost:5432/tripwiser_db")
    assert s1.ASYNC_DATABASE_URL == "postgresql+asyncpg://tripwiser:secret@localhost:5432/tripwiser_db"

    # 2. postgres:// converted to postgresql+asyncpg://
    s2 = Settings(DATABASE_URL="postgres://railway_user:p4ssword@containers-us-west-1.railway.app:5432/railway")
    assert s2.ASYNC_DATABASE_URL == "postgresql+asyncpg://railway_user:p4ssword@containers-us-west-1.railway.app:5432/railway"

    # 3. postgresql:// converted to postgresql+asyncpg://
    s3 = Settings(DATABASE_URL="postgresql://user:pass@host:5432/db")
    assert s3.ASYNC_DATABASE_URL == "postgresql+asyncpg://user:pass@host:5432/db"

    # 4. sslmode=require mapped to ssl=require without weakening SSL
    s4 = Settings(DATABASE_URL="postgresql://user:pass@host:5432/db?sslmode=require")
    assert s4.ASYNC_DATABASE_URL == "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"

    # 5. sslmode=verify-full mapped to ssl=require
    s5 = Settings(DATABASE_URL="postgresql://user:pass@host:5432/db?sslmode=verify-full")
    assert s5.ASYNC_DATABASE_URL == "postgresql+asyncpg://user:pass@host:5432/db?ssl=require"

    # 6. sslmode=disable mapped to ssl=disable
    s6 = Settings(DATABASE_URL="postgresql://user:pass@host:5432/db?sslmode=disable")
    assert s6.ASYNC_DATABASE_URL == "postgresql+asyncpg://user:pass@host:5432/db?ssl=disable"

