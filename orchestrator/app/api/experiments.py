"""Create, list, read and cancel experiments."""

import hashlib
import hmac
import secrets

from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.api.deps import Deps
from app.manager import Busy, Invalid, NotFound, Unavailable
from app.models.schemas import CreatedExperiment, CreateExperimentRequest, Experiment, ExperimentSummary

router = APIRouter(prefix="/experiments")


@router.get("", response_model=list[ExperimentSummary])
async def list_experiments(deps: Deps) -> list[ExperimentSummary]:
    return deps.store.list_summaries()


def client_id(request: Request) -> str:
    """The visitor's IP. Behind Caddy -> Next.js the first X-Forwarded-For entry is the one Caddy
    set (it drops any value the client sent); without a proxy, the socket address."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    return first or (request.client.host if request.client else "")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_owner(deps: Deps, experiment_id: str, token: str | None) -> None:
    """No accounts: whoever holds the token handed out at creation owns the experiment."""
    if deps.store.get(experiment_id) is None:
        raise HTTPException(404, f"Experiment {experiment_id} not found")
    stored = deps.store.owner_hash(experiment_id)
    if not stored or not token or not hmac.compare_digest(stored, _hash(token)):
        raise HTTPException(403, "Only the browser that started this experiment can do that")


@router.post("", response_model=CreatedExperiment, status_code=201)
async def create_experiment(req: CreateExperimentRequest, deps: Deps, request: Request) -> CreatedExperiment:
    token = secrets.token_urlsafe(24)
    try:
        exp = await deps.manager.create(req, client=client_id(request), owner_hash=_hash(token))
    except Invalid as err:
        raise HTTPException(422, str(err)) from err
    except Busy as err:
        raise HTTPException(429, str(err)) from err
    except Unavailable as err:
        raise HTTPException(503, str(err)) from err
    return CreatedExperiment(**exp.model_dump(), owner_token=token)


@router.get("/{experiment_id}", response_model=Experiment)
async def get_experiment(experiment_id: str, deps: Deps) -> Experiment:
    exp = deps.store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id} not found")
    return exp


@router.post("/{experiment_id}/cancel", status_code=204)
async def cancel_experiment(
    experiment_id: str, deps: Deps, x_owner_token: str | None = Header(default=None)
) -> Response:
    require_owner(deps, experiment_id, x_owner_token)
    try:
        await deps.manager.cancel(experiment_id)
    except NotFound as err:
        raise HTTPException(404, str(err)) from err
    return Response(status_code=204)


@router.delete("/{experiment_id}", status_code=204)
async def delete_experiment(
    experiment_id: str, deps: Deps, x_owner_token: str | None = Header(default=None)
) -> Response:
    require_owner(deps, experiment_id, x_owner_token)
    await deps.manager.delete(experiment_id)
    return Response(status_code=204)
