"""
Apply alembic migrations cleanly.
"""

import asyncio
import sys
import importlib
sys.path.insert(0, ".")
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from apps.api.app.platform.config import settings
from alembic.migration import MigrationContext
from alembic.operations import Operations

async def main():
    engine = create_async_engine(settings.migration_database_url, echo=False)
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1;"))
        row = res.fetchone()
        current_rev = row[0] if row else None
        print("Current alembic revision in DB:", current_rev)

        m9 = importlib.import_module("migrations.versions.0009_universal_intake_and_guardrails")
        print("Applying migration 0009_universal_intake_and_guardrails...")

        def run_upg(sync_conn):
            ctx = MigrationContext.configure(sync_conn)
            op = Operations(ctx)
            m9.op = op
            m9.upgrade()
            sync_conn.execute(text("UPDATE alembic_version SET version_num = '0009_universal_intake';"))
            print("Upgraded alembic_version to 0009_universal_intake")

        await conn.run_sync(run_upg)
    await engine.dispose()
    print("Migration finished cleanly!")

if __name__ == "__main__":
    asyncio.run(main())
