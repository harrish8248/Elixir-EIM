"""
Database Session Factory and Row-Level Security (RLS) Context Propagation.
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from apps.api.app.platform.config import settings
from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.context import get_current_tenant_id

# Async engine for application operations
engine_kwargs: dict[str, Any] = {"echo": False}
if os.getenv("TESTING") == "1" or settings.elixir_env == "test":
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = settings.database_pool_size
    engine_kwargs["max_overflow"] = settings.database_max_overflow

engine = create_async_engine(
    settings.database_url,
    **engine_kwargs,
)

# Async session factory
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """
    Yields an AsyncSession configured with PostgreSQL Row-Level Security (RLS).
    Executes 'SET LOCAL app.current_tenant_id = :tenant_id' for multi-tenant isolation.
    """
    async with AsyncSessionFactory() as session:
        tenant_id = get_current_tenant_id()
        if tenant_id:
            try:
                # Set PostgreSQL session variable for Row-Level Security across transactions
                await session.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                    {"tenant_id": str(tenant_id)},
                )
            except Exception as exc:
                logger.error(f"Failed to set RLS tenant context: {exc}")
                raise

        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
