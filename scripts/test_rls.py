import asyncio
import uuid
from apps.api.app.tenancy.database import AsyncSessionFactory
from sqlalchemy import text

async def main():
    async with AsyncSessionFactory() as session:
        tid = "00000000-0000-0000-0000-000000000001"
        try:
            await session.execute(
                text("""
                    INSERT INTO capture_jobs (
                        id, tenant_id, filename, status, document_type,
                        classification_confidence, ocr_engine, mean_confidence,
                        processing_time_ms, raw_text, created_at, updated_at
                    ) VALUES (
                        :id, :tenant_id, 'test.png', 'completed', 'invoice',
                        0.9, 'tesseract', 0.9, 100.0, 'test', now(), now()
                    )
                """),
                {"id": uuid.uuid4(), "tenant_id": tid}
            )
            await session.commit()
            print("Insert without set_config succeeded!")
        except Exception as e:
            print("Insert without set_config failed as expected:", type(e), e)
            await session.rollback()

        # Now with set_config
        try:
            await session.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": tid})
            jid = uuid.uuid4()
            await session.execute(
                text("""
                    INSERT INTO capture_jobs (
                        id, tenant_id, filename, status, document_type,
                        classification_confidence, ocr_engine, mean_confidence,
                        processing_time_ms, raw_text, created_at, updated_at
                    ) VALUES (
                        :id, :tenant_id, 'test.png', 'completed', 'invoice',
                        0.9, 'tesseract', 0.9, 100.0, 'test', now(), now()
                    )
                """),
                {"id": jid, "tenant_id": tid}
            )
            await session.commit()
            print("Insert WITH set_config succeeded! Job ID:", jid)
        except Exception as e:
            print("Insert WITH set_config failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
