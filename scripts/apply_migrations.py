"""
Apply alembic migrations cleanly.
"""

import asyncio
import sys
sys.path.insert(0, ".")
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from apps.api.app.platform.config import settings

async def main():
    engine = create_async_engine(settings.migration_database_url, echo=False)
    async with engine.begin() as conn:
        # Check current version
        res = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1;"))
        row = res.fetchone()
        current_rev = row[0] if row else None
        print("Current alembic revision in DB:", current_rev)

        import importlib
        m5 = importlib.import_module("migrations.versions.0005_idp_capture")
        
        # We can execute upgrade using the engine directly
        print("Creating IDP tables and RLS policies...")
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        
        def run_upg(sync_conn):
            ctx = MigrationContext.configure(sync_conn)
            op = Operations(ctx)
            # monkey-patch op into m5
            m5.op = op
            m5.upgrade()
            sync_conn.execute(text("UPDATE alembic_version SET version_num = '0005_idp_capture';"))
            print("Upgraded alembic_version to 0005_idp_capture")

        await conn.run_sync(run_upg)
    await engine.dispose()
    print("Migration finished cleanly!")

if __name__ == "__main__":
    asyncio.run(main())
