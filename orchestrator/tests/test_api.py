import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.api.live import snapshot
from app.config import Settings
from app.main import create_app
from app.sandbox import RunResult, RunSpec
from app.sandbox.sim import SimDriver

TASK = "Fix the flaky date parsing test in utils"


class HangingDriver:
    """Never finishes on its own — like an agent stuck in a loop."""

    name = "hang"
    expected_steps = 1

    def __init__(self):
        self.cleaned_up = 0

    async def run(self, spec: RunSpec, report) -> RunResult:
        report.running()
        report.step("Start infinite loop")
        try:
            await asyncio.sleep(3600)
        finally:
            self.cleaned_up += 1  # a real driver destroys its container here
        return RunResult(outcome="pass")


def make_client(tmp_path, driver=None, **overrides) -> TestClient:
    settings = Settings(_env_file=None, db_url=f"sqlite:///{tmp_path / 'api.db'}", **overrides)
    return TestClient(create_app(settings, driver=driver or SimDriver(step_s=0)))


def create(client, runs=4, **body):
    res = client.post("/experiments", json={"repo": "demo-repo", "task": TASK, "agentId": "fake", "runs": runs, **body})
    assert res.status_code == 201, res.text
    return res.json()


def wait_for(client, exp_id, statuses, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        exp = client.get(f"/experiments/{exp_id}").json()
        if exp["status"] in statuses:
            return exp
        time.sleep(0.02)
    raise AssertionError(f"{exp_id} stuck in {exp['status']}")


def test_full_experiment_lifecycle(tmp_path):
    with make_client(tmp_path) as client:
        assert client.get("/health").json() == {"status": "ok", "sandboxDriver": "sim", "inference": "fake (offline)"}
        assert [a["id"] for a in client.get("/agents").json()] == ["fake"]

        summary = create(client, runs=5)
        assert summary["id"] == "EXP-001"
        assert summary["runCount"] == 5

        exp = wait_for(client, summary["id"], {"completed"})
        assert all(r["status"] in {"pass", "fail", "error"} for r in exp["runs"])
        assert all(r["steps"] and r["durationS"] is not None for r in exp["runs"])
        assert set(exp["scores"]) == {"reliability", "variance", "divergenceStep"}
        assert exp["insights"] is not None
        assert exp["limits"] == {"timeoutS": 300, "memoryMb": 1024, "cpus": 1.0, "network": "none"}

        overview = client.get("/stats/overview").json()
        assert overview["experiments"] == 1
        assert overview["totalRuns"] == 5
        assert overview["byAgent"][0]["agentId"] == "fake"
        assert [e["id"] for e in client.get("/experiments").json()] == ["EXP-001"]


def test_cancel_destroys_running_sandboxes(tmp_path):
    driver = HangingDriver()
    with make_client(tmp_path, driver=driver, max_parallel_sandboxes=2) as client:
        exp_id = create(client, runs=3)["id"]
        wait_for(client, exp_id, {"running"})

        assert client.post(f"/experiments/{exp_id}/cancel").status_code == 204
        exp = client.get(f"/experiments/{exp_id}").json()

        assert exp["status"] == "cancelled"
        assert [r["status"] for r in exp["runs"]] == ["cancelled"] * 3
        assert driver.cleaned_up == 2  # the two that had started; the third never got a slot
        # cancelling again is a harmless no-op
        assert client.post(f"/experiments/{exp_id}/cancel").status_code == 204


def test_runs_over_the_time_cap_are_killed(tmp_path):
    driver = HangingDriver()
    with make_client(tmp_path, driver=driver, sandbox_timeout_s=1) as client:
        exp = wait_for(client, create(client, runs=2)["id"], {"completed"})

    assert [(r["status"], r["exitReason"]) for r in exp["runs"]] == [("error", "timeout (1s cap)")] * 2
    assert exp["scores"]["reliability"] == 0
    assert exp["insights"]["patterns"] == [{"label": "Killed by sandbox: timeout (1s cap)", "runs": [1, 2]}]
    assert driver.cleaned_up == 2


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"agentId": "nope"}, "Unknown agent nope"),
        ({"runs": 11}, "runs must be between 1 and 10"),
        ({"runs": 0}, "runs: Input should be greater than or equal to 1"),
        ({"task": "too short"}, "task: String should have at least 10 characters"),
    ],
)
def test_bad_requests_get_a_readable_detail(tmp_path, body, detail):
    with make_client(tmp_path) as client:
        payload = {"repo": "demo-repo", "task": TASK, "agentId": "fake", "runs": 3, **body}
        res = client.post("/experiments", json=payload)
    assert res.status_code == 422
    assert res.json()["detail"] == detail


def test_unknown_experiment_is_404(tmp_path):
    with make_client(tmp_path) as client:
        assert client.get("/experiments/EXP-404").status_code == 404
        assert client.post("/experiments/EXP-404/cancel").status_code == 404
        assert client.get("/live/EXP-404").status_code == 404


def test_live_snapshot_reflects_current_state(tmp_path):
    with make_client(tmp_path) as client:
        exp_id = create(client, runs=2)["id"]
        wait_for(client, exp_id, {"completed"})
        exp = client.app.state.services.store.get(exp_id)

    events = [e.model_dump(by_alias=True) for e in snapshot(exp)]
    assert [e["type"] for e in events] == ["run.status", "run.status", "experiment.status"]
    assert events[-1] == {"type": "experiment.status", "status": "completed", "message": "SANDBOXES DESTROYED"}
