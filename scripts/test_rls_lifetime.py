import asyncio
from apps.api.app.tenancy.database import AsyncSessionFactory
from sqlalchemy import text

async def main():
    async with AsyncSessionFactory() as db:
        # statement 1: set_config with true
        await db.execute(text("SELECT set_config('app.current_tenant_id', '11111111-1111-1111-1111-111111111111', true)"))
        # statement 2: commit or rollback or next statement
        res1 = await db.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        print("Statement 2 after true:", res1.scalar())

        # Now commit the transaction (simulating a commit or what happens between requests)
        await db.commit()
        res2 = await db.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        print("After commit (with true):", res2.scalar())

        # Now test with false (session-level)
        await db.execute(text("SELECT set_config('app.current_tenant_id', '11111111-1111-1111-1111-111111111111', false)"))
        await db.commit()
        res3 = await db.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        print("After commit (with false):", res3.scalar())

if __name__ == "__main__":
    asyncio.run(main())

