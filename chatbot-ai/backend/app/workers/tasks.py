"""Celery task wrappers. Each task owns its own DB session and event loop —
Celery workers are separate sync processes, so async SQLAlchemy work has to
be driven explicitly with asyncio.run() rather than sharing the FastAPI
process's loop/session."""

import asyncio
import uuid

from app.core.celery_app import celery_app
from app.core.db import AsyncSessionLocal, engine
from app.services import knowledge_service


async def _process_document_async(document_id: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            document = await knowledge_service.get_document(db, uuid.UUID(document_id))
            if document is None:
                return
            try:
                await knowledge_service.process_document(db, document)
            except Exception:
                pass  # already recorded on the document row; nothing more to do here
            await db.commit()
    finally:
        # Each task runs its own asyncio.run() loop, but the engine's connection
        # pool is a module-level singleton — pooled asyncpg connections are bound
        # to the loop that created them and blow up ("attached to a different
        # loop") if reused from the next task's loop. Dispose so every task
        # starts with a clean pool.
        await engine.dispose()


@celery_app.task(name="knowledge.process_document")
def process_document_task(document_id: str) -> None:
    asyncio.run(_process_document_async(document_id))


async def _process_scraped_site_async(site_id: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            site = await knowledge_service.get_scraped_site(db, uuid.UUID(site_id))
            if site is None:
                return
            try:
                await knowledge_service.process_scraped_site(db, site)
            except Exception:
                pass
            await db.commit()
    finally:
        await engine.dispose()


@celery_app.task(name="knowledge.process_scraped_site")
def process_scraped_site_task(site_id: str) -> None:
    asyncio.run(_process_scraped_site_async(site_id))
