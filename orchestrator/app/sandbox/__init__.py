from app.config import Settings
from app.sandbox.base import RunReporter, RunResult, RunSpec, SandboxDriver
from app.sandbox.sim import SimDriver

__all__ = ["RunReporter", "RunResult", "RunSpec", "SandboxDriver", "build_driver"]


def build_driver(settings: Settings) -> SandboxDriver:
    if settings.sandbox_driver == "sim":
        return SimDriver(step_s=settings.sim_step_s)
    raise NotImplementedError("SANDBOX_DRIVER=docker lands with the runner image; use 'sim' for now")
