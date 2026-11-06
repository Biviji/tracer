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

    def validate_repo(self, repo: str) -> None:
        if "10.0.0.1" in repo:
            raise ValueError("repos can only be cloned from github.com")

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
        # every run that finished on its own reports an answer; killed runs don't
        assert all((r["answer"] is None) == (r["status"] == "error") for r in exp["runs"])
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


def test_hourly_run_cap_refuses_with_429(tmp_path):
    with make_client(tmp_path, max_runs_per_hour=5) as client:
        create(client, runs=3)
        res = client.post("/experiments", json={"repo": "demo-repo", "task": TASK, "agentId": "fake", "runs": 3})
        assert res.status_code == 429
        assert "Hourly limit" in res.json()["detail"]
        create(client, runs=2)  # still fits under the cap


def test_per_client_cap_is_per_visitor(tmp_path):
    body = {"repo": "demo-repo", "task": TASK, "agentId": "fake", "runs": 3}
    with make_client(tmp_path, max_runs_per_client_per_hour=4) as client:
        a = {"x-forwarded-for": "203.0.113.1, 172.18.0.5"}
        assert client.post("/experiments", json=body, headers=a).status_code == 201
        res = client.post("/experiments", json=body, headers=a)
        assert res.status_code == 429 and "of your 4 runs" in res.json()["detail"]
        b = {"x-forwarded-for": "203.0.113.2"}
        assert client.post("/experiments", json=body, headers=b).status_code == 201


def test_refused_repo_is_rejected_before_anything_runs(tmp_path):
    with make_client(tmp_path, driver=HangingDriver()) as client:
        res = client.post("/experiments", json={"repo": "https://10.0.0.1/x/y", "task": TASK, "agentId": "fake", "runs": 1})
        assert res.status_code == 422 and "github.com" in res.json()["detail"]
        assert client.get("/experiments").json() == []


def test_multi_model_experiment_with_check(tmp_path):
    """Two models, 4 runs each, verified by a check command: per-model table and run groups come back."""
    client = make_client(tmp_path, llm_provider="openai_compatible", llm_models="org/model-a,org/model-b", model_prices="org/model-a=1/2")
    with client:
        res = client.post(
            "/experiments",
            json={"repo": "demo", "task": TASK, "agentIds": ["org-model-a", "org-model-b"], "runs": 4, "checkCommand": "pytest -q"},
        )
        assert res.status_code == 201, res.text
        created = res.json()
        assert created["runCount"] == 8
        assert [a["name"] for a in created["agents"]] == ["model-a", "model-b"]

        exp = wait_for(client, created["id"], {"completed"})
        assert exp["checkCommand"] == "pytest -q"
        assert [r["agentName"] for r in exp["runs"]] == ["model-a"] * 4 + ["model-b"] * 4
        for r in exp["runs"]:
            if r["status"] == "pass":
                assert r["check"]["passed"] and not r["tampered"]
            if r["tampered"]:
                assert r["status"] != "pass"
            assert r["tokensIn"] and r["tokensOut"]

        models = {m["agentName"]: m for m in exp["insights"]["models"]}
        assert set(models) == {"model-a", "model-b"} and models["model-a"]["runs"] == 4
        assert (models["model-a"]["costUsd"] is not None) and models["model-b"]["costUsd"] is None
        assert sum(len(g["runs"]) for g in exp["insights"]["groups"]) == 8
        assert exp["insights"]["summary"]


def test_total_run_cap_across_models(tmp_path):
    client = make_client(tmp_path, llm_provider="openai_compatible", llm_models="a,b,c", max_total_runs=10)
    with client:
        res = client.post("/experiments", json={"repo": "demo", "task": TASK, "agentIds": ["a", "b", "c"], "runs": 4})
        assert res.status_code == 422 and "limit is 10" in res.text
        res = client.post("/experiments", json={"repo": "demo", "task": TASK, "agentIds": [], "runs": 2})
        assert res.status_code == 422
