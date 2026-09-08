import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_agent_access, require_roles
from app.core.config import settings
from app.core.db import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.agent import BrandingOut, BrandingUpdate
from app.services import agent_service, storage_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/agents/{agent_id}/branding", tags=["branding"])

_manage_roles = require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)



async def _get_branding_or_404(db: AsyncSession, agent_id: uuid.UUID):
    branding = await agent_service.get_branding(db, agent_id)
    if branding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return branding

def _delete_public_file(public_url: str | None) -> None:
    if not public_url or not public_url.startswith("/media/"):
        return
    abs_path = os.path.join(settings.STORAGE_LOCAL_PATH, public_url.removeprefix("/media/"))
    storage_service.delete_file(abs_path)


@router.get("", response_model=BrandingOut)
async def get_branding(
    agent_id: uuid.UUID,
    user: User = Depends(require_agent_access),
    db: AsyncSession = Depends(get_db),
) -> BrandingOut:
    branding = await _get_branding_or_404(db, agent_id)
    return BrandingOut.model_validate(branding)


@router.put("", response_model=BrandingOut)
async def update_branding(
    agent_id: uuid.UUID,
    body: BrandingUpdate,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> BrandingOut:
    branding = await _get_branding_or_404(db, agent_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(branding, field, value)
    await db.flush()
    await log_action(
        db,
        user_id=user.id,
        action="branding_changed",
        resource_type="agent",
        resource_id=agent_id,
        ip_address=request.client.host if request.client else None,
        details=body.model_dump(exclude_unset=True),
    )
    await db.commit()
    return BrandingOut.model_validate(branding)


@router.post("/logo", response_model=BrandingOut)
async def upload_logo(
    agent_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> BrandingOut:
    branding = await _get_branding_or_404(db, agent_id)
    old_url = branding.logo_url

    abs_path, public_url = await storage_service.save_image(file, subdir=f"agents/{agent_id}/logo")
    branding.logo_url = public_url
    _delete_public_file(old_url)
    await db.flush()
    await log_action(
        db, user_id=user.id, action="branding_changed", resource_type="agent", resource_id=agent_id,
        ip_address=request.client.host if request.client else None, details={"field": "logo_url"},
    )
    await db.commit()
    return BrandingOut.model_validate(branding)


@router.delete("/logo", response_model=BrandingOut)
async def delete_logo(
    agent_id: uuid.UUID,
    request: Request,
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> BrandingOut:
    branding = await _get_branding_or_404(db, agent_id)
    _delete_public_file(branding.logo_url)
    branding.logo_url = None
    await db.flush()
    await log_action(
        db, user_id=user.id, action="branding_changed", resource_type="agent", resource_id=agent_id,
        ip_address=request.client.host if request.client else None, details={"field": "logo_url", "action": "removed"},
    )
    await db.commit()
    return BrandingOut.model_validate(branding)


@router.post("/avatar", response_model=BrandingOut)
async def upload_avatar(
    agent_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(_manage_roles),
    db: AsyncSession = Depends(get_db),
) -> BrandingOut:
    branding = await _get_branding_or_404(db, agent_id)
    old_url = branding.avatar_url
    abs_path, public_url = await storage_service.save_image(file, subdir=f"agents/{agent_id}/avatar")
    branding.avatar_url = public_url
    _delete_public_file(old_url)
    await db.flush()
    await log_action(
        db, user_id=user.id, action="branding_changed", resource_type="agent", resource_id=agent_id,
        ip_address=request.client.host if request.client else None, details={"field": "avatar_url"},
    )
    await db.commit()
    return BrandingOut.model_validate(branding)
