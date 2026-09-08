import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.db import get_db
from app.models.enums import KnowledgeSourceType, ProcessingStatus, UserRole
from app.models.knowledge import KnowledgeChunk
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    KnowledgeDocumentOut,
    ScrapedSiteOut,
    ScrapeRequest,
)
from app.services import knowledge_service, storage_service, task_dispatch
from app.services.audit_service import log_action

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-base"])

_manage_roles = require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _get_kb_or_404(db: AsyncSession, kb_id: uuid.UUID):
    kb = await knowledge_service.get_knowledge_base(db, kb_id)
    if kb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge base not found")
    return kb


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(
    user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> list[KnowledgeBaseOut]:
    kbs = await knowledge_service.list_knowledge_bases(db)
    return [KnowledgeBaseOut.from_model(kb) for kb in kbs]


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseOut:
    kb = await knowledge_service.create_knowledge_base(
        db, name=body.name, description=body.description, source_type=body.source_type, agent_ids=body.agent_ids
    )
    await log_action(
        db, user_id=user.id, action="kb_created", resource_type="knowledge_base", resource_id=kb.id,
        ip_address=_client_ip(request), details={"name": kb.name},
    )
    await db.commit()
    await db.refresh(kb, attribute_names=["agents"])
    return KnowledgeBaseOut.from_model(kb)


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(
    kb_id: uuid.UUID, user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> KnowledgeBaseOut:
    kb = await _get_kb_or_404(db, kb_id)
    return KnowledgeBaseOut.from_model(kb)


@router.put("/{kb_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    kb_id: uuid.UUID,
    body: KnowledgeBaseUpdate,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseOut:
    kb = await _get_kb_or_404(db, kb_id)
    if body.name is not None:
        kb.name = body.name
    if body.description is not None:
        kb.description = body.description
    if body.agent_ids is not None:
        kb = await knowledge_service.set_knowledge_base_agents(db, kb, body.agent_ids)
    await db.flush()
    await log_action(
        db, user_id=user.id, action="kb_updated", resource_type="knowledge_base", resource_id=kb.id,
        ip_address=_client_ip(request),
    )
    await db.commit()
    return KnowledgeBaseOut.from_model(kb)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID, request: Request, user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> None:
    kb = await _get_kb_or_404(db, kb_id)
    await log_action(
        db, user_id=user.id, action="kb_deleted", resource_type="knowledge_base", resource_id=kb.id,
        ip_address=_client_ip(request), details={"name": kb.name},
    )
    await db.delete(kb)
    await db.commit()


@router.post("/{kb_id}/pdf", response_model=KnowledgeDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    kb_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentOut:
    kb = await _get_kb_or_404(db, kb_id)
    if kb.source_type != KnowledgeSourceType.PDF:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This knowledge base is website-type; PDFs can't be added to it")
    abs_path, filename, size_bytes = await storage_service.save_pdf(file, subdir=f"knowledge/{kb_id}/pdf")
    document = await knowledge_service.create_document_record(
        db, kb_id=kb_id, file_name=file.filename or filename, file_path=abs_path, file_size_bytes=size_bytes
    )
    await log_action(
        db, user_id=user.id, action="kb_document_uploaded", resource_type="knowledge_document",
        resource_id=document.id, ip_address=_client_ip(request), details={"file_name": document.file_name},
    )
    await db.commit()
    task_dispatch.dispatch_document_processing(document.id)
    return KnowledgeDocumentOut.model_validate(document)


@router.get("/{kb_id}/documents", response_model=list[KnowledgeDocumentOut])
async def list_documents(
    kb_id: uuid.UUID, user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> list[KnowledgeDocumentOut]:
    kb = await _get_kb_or_404(db, kb_id)
    await db.refresh(kb, attribute_names=["documents"])
    return [KnowledgeDocumentOut.model_validate(d) for d in kb.documents]


@router.post("/{kb_id}/documents/{doc_id}/reprocess", response_model=KnowledgeDocumentOut)
async def reprocess_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentOut:
    document = await knowledge_service.get_document(db, doc_id)
    if document is None or document.knowledge_base_id != kb_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    await db.execute(sa_delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id))
    document.status = ProcessingStatus.PENDING
    document.chunk_count = 0
    document.error_message = None
    await db.flush()
    await log_action(
        db, user_id=user.id, action="kb_document_reprocess", resource_type="knowledge_document",
        resource_id=doc_id, ip_address=_client_ip(request),
    )
    await db.commit()
    task_dispatch.dispatch_document_processing(document.id)
    return KnowledgeDocumentOut.model_validate(document)


@router.delete("/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> None:
    document = await knowledge_service.get_document(db, doc_id)
    if document is None or document.knowledge_base_id != kb_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    storage_service.delete_file(document.file_path)
    await log_action(
        db, user_id=user.id, action="kb_document_deleted", resource_type="knowledge_document",
        resource_id=doc_id, ip_address=_client_ip(request), details={"file_name": document.file_name},
    )
    await db.delete(document)
    await db.commit()


@router.post("/{kb_id}/scrape", response_model=ScrapedSiteOut, status_code=status.HTTP_201_CREATED)
async def create_scrape(
    kb_id: uuid.UUID,
    body: ScrapeRequest,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> ScrapedSiteOut:
    kb = await _get_kb_or_404(db, kb_id)
    if kb.source_type != KnowledgeSourceType.WEBSITE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This knowledge base is PDF-type; websites can't be added to it")
    site = await knowledge_service.create_scraped_site(
        db,
        kb_id=kb_id,
        base_url=str(body.url),
        mode=body.mode,
        max_pages=body.max_pages,
        max_depth=body.max_depth,
        include_subpages=body.include_subpages,
        exclude_urls=body.exclude_urls,
    )
    await log_action(
        db, user_id=user.id, action="kb_scrape_created", resource_type="scraped_site", resource_id=site.id,
        ip_address=_client_ip(request), details={"base_url": site.base_url},
    )
    await db.commit()
    task_dispatch.dispatch_site_processing(site.id)
    return ScrapedSiteOut.model_validate(site)


@router.get("/{kb_id}/scraped-sites", response_model=list[ScrapedSiteOut])
async def list_scraped_sites(
    kb_id: uuid.UUID, user: User = Depends(_manage_roles), db: AsyncSession = Depends(get_db)
) -> list[ScrapedSiteOut]:
    kb = await _get_kb_or_404(db, kb_id)
    await db.refresh(kb, attribute_names=["scraped_sites"])
    return [ScrapedSiteOut.model_validate(s) for s in kb.scraped_sites]


@router.post("/{kb_id}/scraped-sites/{site_id}/rescrape", response_model=ScrapedSiteOut)
async def rescrape_site(
    kb_id: uuid.UUID,
    site_id: uuid.UUID,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> ScrapedSiteOut:
    site = await knowledge_service.get_scraped_site(db, site_id)
    if site is None or site.knowledge_base_id != kb_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scraped site not found")
    await log_action(
        db, user_id=user.id, action="kb_rescrape_triggered", resource_type="scraped_site",
        resource_id=site_id, ip_address=_client_ip(request),
    )
    await db.commit()
    task_dispatch.dispatch_site_processing(site.id)
    return ScrapedSiteOut.model_validate(site)


@router.delete("/{kb_id}/scraped-sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scraped_site(
    kb_id: uuid.UUID,
    site_id: uuid.UUID,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> None:
    site = await knowledge_service.get_scraped_site(db, site_id)
    if site is None or site.knowledge_base_id != kb_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scraped site not found")
    await log_action(
        db, user_id=user.id, action="kb_scraped_site_deleted", resource_type="scraped_site",
        resource_id=site_id, ip_address=_client_ip(request), details={"base_url": site.base_url},
    )
    await db.delete(site)
    await db.commit()
