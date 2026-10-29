import asyncio
from apps.api.app.tenancy.database import AsyncSessionFactory
from sqlalchemy import text

async def main():
    async with AsyncSessionFactory() as session:
        t_res = await session.execute(text("SELECT id, name FROM tenants"))
        print("Tenants:", t_res.fetchall())
        u_res = await session.execute(text("SELECT id, email, tenant_id FROM users"))
        print("Users:", u_res.fetchall())
        p_res = await session.execute(text("SELECT tablename, policyname, qual, with_check FROM pg_policies WHERE tablename IN ('audit_events', 'capture_jobs')"))
        for row in p_res.fetchall():
            print("Policy:", row)

if __name__ == "__main__":
    asyncio.run(main())

