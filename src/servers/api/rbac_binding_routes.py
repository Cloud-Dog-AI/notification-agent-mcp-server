#!/usr/bin/env python3
"""DB-backed RBAC binding routes (/idam/v1/rbac/bindings) — W28A-744 / IDAM-B2 §2.4.

The notification-native, persistent source of truth for the group->channel cascade
(the ``rbac_bindings`` table). Mounted BEFORE the shared cloud_dog_idam in-memory
reference router so these DB-backed handlers are authoritative. Writes are admin-
gated; create/delete invalidate the affected subject's resolver cache so the
cascade lands live (no restart). Module-state is injected from api_server exactly
like channel_routes/admin_routes.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from . import api_server as _api

globals().update({name: value for name, value in vars(_api).items() if not name.startswith("__")})
router = APIRouter(prefix="/idam/v1")


@router.get("/rbac/bindings", dependencies=[Depends(verify_api_key)])
async def list_rbac_bindings(
    subject_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    project: Optional[str] = None,
):
    """List RBAC bindings with optional subject/project filter."""
    rows = get_binding_store().list_bindings()
    out = []
    for b in rows:
        if subject_type and b.subject_type != subject_type:
            continue
        if subject_id and b.subject_id != subject_id:
            continue
        if project and b.project != project:
            continue
        out.append(b.to_dict())
    return out


@router.post("/rbac/bindings", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
async def create_rbac_binding(payload: dict):
    """Create a group/user -> resource binding (admin-gated). Drives the cascade."""
    record = get_binding_store().create_binding(payload or {})
    _invalidate_binding_subject(record.subject_type, record.subject_id)
    return record.to_dict()


@router.get("/rbac/bindings/{binding_id}", dependencies=[Depends(verify_api_key)])
async def get_rbac_binding(binding_id: str):
    """Return a single binding by id."""
    record = get_binding_store().get_binding(binding_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return record.to_dict()


@router.delete("/rbac/bindings/{binding_id}", dependencies=[Depends(verify_admin)])
async def delete_rbac_binding(binding_id: str):
    """Delete (revoke) a binding by id (admin-gated). Revokes the cascade live."""
    store = get_binding_store()
    record = store.get_binding(binding_id)
    existed = store.delete_binding(binding_id)
    if record is not None:
        _invalidate_binding_subject(record.subject_type, record.subject_id)
    return {"ok": existed}
