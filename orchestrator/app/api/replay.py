"""POST /replay/scan: find a repo's past bug fixes, to pick which ones to re-do."""

from fastapi import APIRouter, HTTPException

from app.api.deps import Deps
from app.manager import Invalid
from app.models.schemas import ScanRequest, ScanResult

router = APIRouter(prefix="/replay")


@router.post("/scan", response_model=ScanResult)
async def scan(req: ScanRequest, deps: Deps) -> ScanResult:
    try:
        return await deps.manager.scan(req.repo)
    except Invalid as err:
        raise HTTPException(422, str(err)) from err
