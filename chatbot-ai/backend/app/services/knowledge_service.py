import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent
from app.models.enums import KnowledgeSourceType, NotificationType, ProcessingStatus, ScrapeMode
from app.models.knowledge import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    ScrapedPage,
    ScrapedSite,
)
from app.services import embedding_service, pdf_service, scraper_service
from app.services.notification_service import notify

_EMBED_BATCH_SIZE = 100


async def create_knowledge_base(
    db: AsyncSession,
    *,
    name: str,
    description: str | None,
    source_type: KnowledgeSourceType,
    agent_ids: list[uuid.UUID],
) -> KnowledgeBase:
    kb = KnowledgeBase(name=name, description=description, source_type=source_type)
    if agent_ids:
        result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        kb.agents = list(result.scalars().all())
    db.add(kb)
    await db.flush()
    return kb


async def list_knowledge_bases(db: AsyncSession) -> list[KnowledgeBase]:
    result = await db.execute(
        select(KnowledgeBase).options(selectinload(KnowledgeBase.agents)).order_by(KnowledgeBase.created_at.desc())
    )
    return list(result.scalars().all())


async def get_knowledge_base(db: AsyncSession, kb_id: uuid.UUID) -> KnowledgeBase | None:
    result = await db.execute(
        select(KnowledgeBase).options(selectinload(KnowledgeBase.agents)).where(KnowledgeBase.id == kb_id)
    )
    return result.scalar_one_or_none()


async def set_knowledge_base_agents(db: AsyncSession, kb: KnowledgeBase, agent_ids: list[uuid.UUID]) -> KnowledgeBase:
    result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
    kb.agents = list(result.scalars().all())
    await db.flush()
    return kb


# ---------------------------------------------------------------------------
# PDF documents
# ---------------------------------------------------------------------------


async def create_document_record(
    db: AsyncSession, *, kb_id: uuid.UUID, file_name: str, file_path: str, file_size_bytes: int
) -> KnowledgeDocument:
    doc = KnowledgeDocument(
        knowledge_base_id=kb_id,
        file_name=file_name,
        file_path=file_path,
        file_size_bytes=file_size_bytes,
        status=ProcessingStatus.PENDING,
    )
    db.add(doc)
    await db.flush()
    return doc


async def get_document(db: AsyncSession, doc_id: uuid.UUID) -> KnowledgeDocument | None:
    result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
    return result.scalar_one_or_none()


async def process_document(db: AsyncSession, document: KnowledgeDocument) -> None:
    """Extract, chunk, embed, and store a PDF document's content. Any of
    validate/extract/chunk/embed failing marks the document FAILED with a
    stored error message and fires a kb_processing_failed notification,
    instead of leaving it stuck in PROCESSING."""

    document.status = ProcessingStatus.PROCESSING
    document.error_message = None
    await db.flush()

    try:
        raw_text = pdf_service.extract_text(document.file_path)
        cleaned = pdf_service.clean_text(raw_text)
        chunks = pdf_service.chunk_text(cleaned)
        if not chunks:
            raise pdf_service.PdfExtractionError("No content chunks produced from PDF")

        await _embed_and_store_chunks(
            db,
            knowledge_base_id=document.knowledge_base_id,
            document_id=document.id,
            scraped_page_id=None,
            source_type=KnowledgeSourceType.PDF,
            texts=chunks,
        )

        document.status = ProcessingStatus.COMPLETED
        document.chunk_count = len(chunks)
        document.processed_at = datetime.now(timezone.utc)
        await db.flush()
    except Exception as exc:
        document.status = ProcessingStatus.FAILED
        document.error_message = str(exc)[:2000]
        await db.flush()
        await notify(
            db,
            type=NotificationType.KB_PROCESSING_FAILED,
            title=f"PDF processing failed: {document.file_name}",
            body=str(exc)[:500],
            resource_type="knowledge_document",
            resource_id=document.id,
        )
        raise


# ---------------------------------------------------------------------------
# Website scraping
# ---------------------------------------------------------------------------


async def create_scraped_site(
    db: AsyncSession,
    *,
    kb_id: uuid.UUID,
    base_url: str,
    mode: ScrapeMode,
    max_pages: int,
    max_depth: int,
    include_subpages: bool,
    exclude_urls: list[str],
) -> ScrapedSite:
    site = ScrapedSite(
        knowledge_base_id=kb_id,
        base_url=base_url,
        mode=mode,
        max_pages=max_pages,
        max_depth=max_depth,
        include_subpages=include_subpages,
        exclude_urls=exclude_urls,
        status=ProcessingStatus.PENDING,
    )
    db.add(site)
    await db.flush()
    return site


async def get_scraped_site(db: AsyncSession, site_id: uuid.UUID) -> ScrapedSite | None:
    result = await db.execute(select(ScrapedSite).where(ScrapedSite.id == site_id))
    return result.scalar_one_or_none()


async def process_scraped_site(db: AsyncSession, site: ScrapedSite) -> None:
    site.status = ProcessingStatus.PROCESSING
    site.error_message = None
    site.pages_discovered = 0
    site.pages_processed = 0
    await db.flush()

    try:
        urls = await scraper_service.crawl(
            site.base_url,
            single_url_only=(site.mode == ScrapeMode.SINGLE_URL),
            max_pages=site.max_pages,
            max_depth=site.max_depth,
            include_subpages=site.include_subpages,
            exclude_patterns=site.exclude_urls,
        )
        site.pages_discovered = len(urls)
        await db.flush()

        any_success = False
        for url in urls:
            page = ScrapedPage(scraped_site_id=site.id, url=url, status=ProcessingStatus.PENDING)
            db.add(page)
            await db.flush()

            try:
                html = await scraper_service.fetch_html(url)
                _, text = scraper_service.extract_text(html)
                if not text.strip():
                    raise scraper_service.ScrapeError("No extractable text on page")

                chunks = pdf_service.chunk_text(text)
                await _embed_and_store_chunks(
                    db,
                    knowledge_base_id=site.knowledge_base_id,
                    document_id=None,
                    scraped_page_id=page.id,
                    source_type=KnowledgeSourceType.WEBSITE,
                    texts=chunks,
                )
                page.status = ProcessingStatus.COMPLETED
                any_success = True
                site.pages_processed += 1
            except Exception as page_exc:
                page.status = ProcessingStatus.FAILED
                page.error_message = str(page_exc)[:2000]
            await db.flush()

        if not any_success:
            raise scraper_service.ScrapeError("No pages could be scraped successfully")

        site.status = ProcessingStatus.COMPLETED
        site.last_scraped_at = datetime.now(timezone.utc)
        await db.flush()
    except Exception as exc:
        site.status = ProcessingStatus.FAILED
        site.error_message = str(exc)[:2000]
        await db.flush()
        await notify(
            db,
            type=NotificationType.KB_PROCESSING_FAILED,
            title=f"Website scraping failed: {site.base_url}",
            body=str(exc)[:500],
            resource_type="scraped_site",
            resource_id=site.id,
        )
        raise


# ---------------------------------------------------------------------------
# Shared chunk embedding/storage
# ---------------------------------------------------------------------------


async def _embed_and_store_chunks(
    db: AsyncSession,
    *,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID | None,
    scraped_page_id: uuid.UUID | None,
    source_type: KnowledgeSourceType,
    texts: list[str],
) -> None:
    for batch_start in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[batch_start : batch_start + _EMBED_BATCH_SIZE]
        vectors = await embedding_service.embed_texts(batch)
        for i, (text, vector) in enumerate(zip(batch, vectors)):
            db.add(
                KnowledgeChunk(
                    knowledge_base_id=knowledge_base_id,
                    document_id=document_id,
                    scraped_page_id=scraped_page_id,
                    source_type=source_type,
                    chunk_index=batch_start + i,
                    content=text,
                    token_count=pdf_service.estimate_token_count(text),
                    embedding=vector,
                )
            )
        await db.flush()
