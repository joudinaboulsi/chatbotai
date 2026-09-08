import io

import pytest
from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import KnowledgeSourceType, ProcessingStatus
from app.models.knowledge import KnowledgeChunk
from app.services import embedding_service, knowledge_service, scraper_service

pytestmark = pytest.mark.asyncio


def _fake_embed(dim: int = 1536):
    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[0.001 * (i + 1)] * dim for i in range(len(texts))]

    return _embed


def _make_pdf_bytes(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text.split("\n"):
        pdf.multi_cell(0, 10, line)
    return bytes(pdf.output())


async def test_process_document_success(db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setattr(embedding_service, "embed_texts", _fake_embed())

    kb = await knowledge_service.create_knowledge_base(
        db_session, name="Test KB", description=None, source_type=KnowledgeSourceType.PDF, agent_ids=[]
    )
    pdf_bytes = _make_pdf_bytes("Tawasol offers SMS gateway and WhatsApp Business API services for enterprises.")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(pdf_bytes)

    document = await knowledge_service.create_document_record(
        db_session, kb_id=kb.id, file_name="sample.pdf", file_path=str(pdf_path), file_size_bytes=len(pdf_bytes)
    )

    await knowledge_service.process_document(db_session, document)

    assert document.status == ProcessingStatus.COMPLETED
    assert document.chunk_count > 0
    assert document.error_message is None

    result = await db_session.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
    chunks = result.scalars().all()
    assert len(chunks) == document.chunk_count
    assert chunks[0].source_type == KnowledgeSourceType.PDF
    assert "Tawasol" in chunks[0].content
    assert len(chunks[0].embedding) == 1536


async def test_process_document_invalid_pdf_marks_failed(db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setattr(embedding_service, "embed_texts", _fake_embed())

    kb = await knowledge_service.create_knowledge_base(
        db_session, name="KB2", description=None, source_type=KnowledgeSourceType.PDF, agent_ids=[]
    )
    bad_path = tmp_path / "not_a_pdf.pdf"
    bad_path.write_bytes(b"this is not a valid pdf file")

    document = await knowledge_service.create_document_record(
        db_session, kb_id=kb.id, file_name="not_a_pdf.pdf", file_path=str(bad_path), file_size_bytes=30
    )

    with pytest.raises(Exception):
        await knowledge_service.process_document(db_session, document)

    assert document.status == ProcessingStatus.FAILED
    assert document.error_message is not None


async def test_process_scraped_site_single_url(db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr(embedding_service, "embed_texts", _fake_embed())

    html = "<html><head><title>Tawasol</title></head><body><main><p>Tawasol provides telecom APIs.</p></main></body></html>"

    async def fake_fetch_html(url: str) -> str:
        return html

    monkeypatch.setattr(scraper_service, "fetch_html", fake_fetch_html)

    from app.models.enums import ScrapeMode

    kb = await knowledge_service.create_knowledge_base(
        db_session, name="KB3", description=None, source_type=KnowledgeSourceType.WEBSITE, agent_ids=[]
    )
    site = await knowledge_service.create_scraped_site(
        db_session,
        kb_id=kb.id,
        base_url="https://example.com",
        mode=ScrapeMode.SINGLE_URL,
        max_pages=1,
        max_depth=1,
        include_subpages=False,
        exclude_urls=[],
    )

    await knowledge_service.process_scraped_site(db_session, site)

    assert site.status == ProcessingStatus.COMPLETED
    assert site.pages_discovered == 1
    assert site.pages_processed == 1

    result = await db_session.execute(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_base_id == kb.id))
    chunks = result.scalars().all()
    assert len(chunks) > 0
    assert "Tawasol" in chunks[0].content
    assert chunks[0].source_type == KnowledgeSourceType.WEBSITE


async def test_process_scraped_site_unreachable_marks_failed(db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr(embedding_service, "embed_texts", _fake_embed())

    async def fake_fetch_html(url: str) -> str:
        raise scraper_service.ScrapeError("Could not reach host")

    monkeypatch.setattr(scraper_service, "fetch_html", fake_fetch_html)

    from app.models.enums import ScrapeMode
    kb = await knowledge_service.create_knowledge_base(
        db_session, name="KB4", description=None, source_type=KnowledgeSourceType.WEBSITE, agent_ids=[]
    )
    site = await knowledge_service.create_scraped_site(
        db_session,
        kb_id=kb.id,
        base_url="https://unreachable.example",
        mode=ScrapeMode.SINGLE_URL,
        max_pages=1,
        max_depth=1,
        include_subpages=False,
        exclude_urls=[],
    )

    with pytest.raises(Exception):
        await knowledge_service.process_scraped_site(db_session, site)

    assert site.status == ProcessingStatus.FAILED
    assert site.error_message is not None
