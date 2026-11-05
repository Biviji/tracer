from app.models.schemas import Agent, DiffLine, FileDiff, SandboxLimits, TraceStep
from app.store import Store, derive_title, parse_id

AGENT = Agent(id="a", name="Agent A", model="model-a", description="")
LIMITS = SandboxLimits(timeout_s=60, memory_mb=512, cpus=1, network="none")


def make_store(tmp_path) -> Store:
    store = Store(f"sqlite:///{tmp_path / 'test.db'}")
    store.init()
    return store


def test_create_and_read_back(tmp_path):
    store = make_store(tmp_path)
    exp = store.create(repo="r", task="Fix the flaky loader test", agent=AGENT, runs=3, limits=LIMITS)

    assert exp.id == "EXP-001"
    assert exp.title == "Fix the flaky loader test"
    assert [r.status for r in exp.runs] == ["queued"] * 3
    assert store.model_for(exp.id) == "model-a"

    store.append_step(exp.id, 1, TraceStep(index=1, label="clone"))
    store.update_run(exp.id, 1, status="pass", diff=[FileDiff(file="x.py", lines=[DiffLine(op="+", text="y")])])

    again = store.get(exp.id)
    assert again.runs[0].status == "pass"
    assert again.runs[0].steps[0].label == "clone"
    assert again.runs[0].diff[0].file == "x.py"
    assert [e.id for e in store.list_summaries()] == ["EXP-001"]


def test_unknown_ids(tmp_path):
    store = make_store(tmp_path)
    assert store.get("EXP-999") is None
    assert store.get("nope") is None
    assert parse_id("EXP-abc") is None


def test_restart_fails_interrupted_experiments(tmp_path):
    store = make_store(tmp_path)
    exp = store.create(repo="r", task="Fix the flaky loader test", agent=AGENT, runs=2, limits=LIMITS)
    store.set_status(exp.id, "running")
    store.update_run(exp.id, 1, status="pass")

    assert store.fail_interrupted() == [exp.id]
    after = store.get(exp.id)
    assert after.status == "failed"
    assert [(r.status, r.exit_reason) for r in after.runs] == [("pass", None), ("error", "orchestrator_restarted")]


def test_derive_title_cuts_on_word_boundary():
    assert derive_title("Make the payment retry logic idempotent and safe.") == "Make the payment retry logic"
