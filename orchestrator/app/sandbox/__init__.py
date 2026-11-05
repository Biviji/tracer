import logging

from app.config import Settings
from app.llm import LLMClient
from app.sandbox.base import RunReporter, RunResult, RunSpec, SandboxDriver
from app.sandbox.sim import SimDriver

__all__ = ["RunReporter", "RunResult", "RunSpec", "SandboxDriver", "build_driver"]

log = logging.getLogger(__name__)


class SandboxUnavailable(RuntimeError):
    pass


def build_driver(settings: Settings, llm: LLMClient) -> SandboxDriver:
    if settings.sandbox_driver == "sim":
        return SimDriver(step_s=settings.sim_step_s)

    from docker.errors import DockerException, ImageNotFound

    from app.sandbox.docker_driver import DockerDriver

    try:
        driver = DockerDriver(settings, llm)
        driver.check()
    except ImageNotFound as err:
        raise SandboxUnavailable(
            f"sandbox image '{settings.sandbox_image}' not found; build it: docker build -t {settings.sandbox_image} runner/"
        ) from err
    except DockerException as err:
        raise SandboxUnavailable(f"SANDBOX_DRIVER=docker but Docker is not reachable: {err}") from err
    if removed := driver.remove_orphans():
        log.warning("removed %d sandbox container(s) left over from a previous run", removed)
    return driver
