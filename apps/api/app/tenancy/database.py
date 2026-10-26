"""
Database Session Factory and Row-Level Security (RLS) Context Propagation.
"""

from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from apps.api.app.platform.config import settings
from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.context import get_current_tenant_id

# Async engine for application operations
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=False,
)

# Async session factory
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an AsyncSession configured with PostgreSQL Row-Level Security (RLS).
    Executes 'SET LOCAL app.current_tenant_id = :tenant_id' for multi-tenant isolation.
    """
    async with AsyncSessionFactory() as session:
        tenant_id = get_current_tenant_id()
        if tenant_id:
            try:
                # Set PostgreSQL session-local variable for Row-Level Security
                await session.execute(
                    text("SET LOCAL app.current_tenant_id = :tenant_id"),
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
