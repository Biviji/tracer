"""Create, list, read and cancel experiments."""

from fastapi import APIRouter, HTTPException, Request, Response

from app.api.deps import Deps
from app.manager import Busy, Invalid, NotFound
from app.models.schemas import CreateExperimentRequest, Experiment, ExperimentSummary

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


@router.post("", response_model=ExperimentSummary, status_code=201)
async def create_experiment(req: CreateExperimentRequest, deps: Deps, request: Request) -> ExperimentSummary:
    try:
        return await deps.manager.create(req, client=client_id(request))
    except Invalid as err:
        raise HTTPException(422, str(err)) from err
    except Busy as err:
        raise HTTPException(429, str(err)) from err


@router.get("/{experiment_id}", response_model=Experiment)
async def get_experiment(experiment_id: str, deps: Deps) -> Experiment:
    exp = deps.store.get(experiment_id)
    if exp is None:
        raise HTTPException(404, f"Experiment {experiment_id} not found")
    return exp


@router.post("/{experiment_id}/cancel", status_code=204)
async def cancel_experiment(experiment_id: str, deps: Deps) -> Response:
    try:
        await deps.manager.cancel(experiment_id)
    except NotFound as err:
        raise HTTPException(404, str(err)) from err
    return Response(status_code=204)
