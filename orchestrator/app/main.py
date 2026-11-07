"""FastAPI entry point:  uvicorn app.main:app --port 8000"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import experiments, live, meta, replay
from app.api.deps import Services
from app.config import Settings, get_settings
from app.events import EventBus
from app.llm import CircuitBreaker, LLMClient, build_llm
from app.manager import ExperimentManager
from app.sandbox import SandboxDriver, build_driver
from app.store import Store

log = logging.getLogger("trace")

#: How often finished experiments past RETENTION_DAYS are deleted.
PURGE_EVERY_S = 3600.0


async def _purge_loop(manager: ExperimentManager) -> None:
    while True:
        try:
            if deleted := manager.purge_expired():
                log.info("retention: deleted %d experiment(s): %s", len(deleted), deleted)
        except Exception:
            log.exception("retention purge failed")
        await asyncio.sleep(PURGE_EVERY_S)


def create_app(
    settings: Settings | None = None,
    *,
    driver: SandboxDriver | None = None,
    llm: LLMClient | None = None,
) -> FastAPI:
    """Build the app. Tests pass their own settings / driver / llm."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(settings.db_url)
        store.init()
        if interrupted := store.fail_interrupted():
            log.warning("marked %d interrupted experiment(s) as failed: %s", len(interrupted), interrupted)

        bus = EventBus()
        # Every model call goes through the breaker, so a provider outage stops runs fast.
        model = CircuitBreaker(llm or build_llm(settings))
        sandbox = driver or build_driver(settings, model)
        manager = ExperimentManager(settings, store, bus, sandbox, breaker=model)
        app.state.services = Services(settings, store, bus, sandbox, model, manager)
        log.info("orchestrator up: sandbox=%s inference=%s", sandbox.name, model.name)
        purge = asyncio.create_task(_purge_loop(manager), name="retention")
        try:
            yield
        finally:
            purge.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await purge
            await manager.shutdown()
            await model.aclose()
            store.dispose()

    app = FastAPI(title="TRACE orchestrator", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # The frontend shows `detail` as-is, so flatten Pydantic's list into one readable line.
        parts = []
        for err in exc.errors():
            field = ".".join(str(p) for p in err["loc"] if p != "body")
            parts.append(f"{field}: {err['msg']}" if field else err["msg"])
        return JSONResponse(status_code=422, content={"detail": "; ".join(parts)})

    app.include_router(meta.router)
    app.include_router(experiments.router)
    app.include_router(live.router)
    app.include_router(replay.router)
    return app


app = create_app()
