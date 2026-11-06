"""Real-container test. Skipped unless Docker is running and trace-sandbox:latest is built."""

import asyncio
import json
import shutil

import pytest

from app.config import Settings
from app.models.schemas import SandboxLimits
from app.sandbox.base import RunSpec

docker = pytest.importorskip("docker")

try:
    _client = docker.from_env()
    _client.ping()
    _client.images.get("trace-sandbox:latest")
except Exception:  # noqa: BLE001
    pytest.skip("Docker or trace-sandbox image not available", allow_module_level=True)

from app.sandbox import docker_driver  # noqa: E402
from app.sandbox.docker_driver import LABEL, DockerDriver  # noqa: E402


def call(name, call_id, **args):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class ScriptedLLM:
    name = "scripted"

    def __init__(self, replies):
        self.replies = list(replies)
        self.tool_results = []

    async def chat(self, model, messages, *, tools=None, temperature=None):
        if messages[-1]["role"] == "tool":
            self.tool_results.append(messages[-1]["content"])
        return self.replies.pop(0)


class Reporter:
    def __init__(self):
        self.steps, self.logs, self.started = [], [], False

    def running(self):
        self.started = True

    def log(self, line, level="info"):
        self.logs.append(line)

    def step(self, label, detail=None):
        self.steps.append(label)


@pytest.fixture
def local_repo(tmp_path, monkeypatch):
    """Serve a tiny local git repo instead of cloning from the internet."""
    src = tmp_path / "src"
    (src / "auth").mkdir(parents=True)
    (src / "auth" / "jwt.py").write_text("SECRET = 'dev'\n")

    def fake_clone(url, dest, timeout_s, max_mb):
        shutil.copytree(src, dest)
        import subprocess

        for cmd in (["git", "init", "-q"], ["git", "add", "."], ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
            subprocess.run(cmd, cwd=dest, check=True)

    monkeypatch.setattr(docker_driver, "_clone", fake_clone)


def test_real_sandbox_run(local_repo):
    llm = ScriptedLLM(
        [
            {"role": "assistant", "tool_calls": [call("read_file", "c1", path="auth/jwt.py")]},
            {"role": "assistant", "tool_calls": [call("run_command", "c2", command="curl -sS https://example.com || python -c \"import urllib.request as u; u.urlopen('https://example.com', timeout=3)\"")]},
            {"role": "assistant", "tool_calls": [call("run_command", "c3", command="id -u; env | grep -ci groq || true")]},
            {"role": "assistant", "tool_calls": [call("write_file", "c4", path="auth/jwt.py", content="import os\nSECRET = os.environ['JWT_SECRET']\n")]},
            {"role": "assistant", "tool_calls": [call("read_file", "c5", path="../../etc/passwd")]},
            {"role": "assistant", "content": "Secret was hard-coded; now read from the environment."},
        ]
    )
    settings = Settings(_env_file=None, sandbox_driver="docker", agent_max_steps=10, command_timeout_s=20)
    driver = DockerDriver(settings, llm)
    spec = RunSpec("EXP-TEST", 1, "https://github.com/x/y", "Check JWT", "m", SandboxLimits(timeout_s=120, memory_mb=256, cpus=0.5, network="none"))
    rep = Reporter()

    result = asyncio.run(driver.run(spec, rep))

    assert rep.started
    assert result.outcome == "pass"
    assert result.answer.startswith("Secret was hard-coded")
    read, net, ident, _write, escape = llm.tool_results
    assert "SECRET = 'dev'" in read
    assert "exit code 0" not in net  # no network inside the sandbox
    assert ident.splitlines()[1:3] == ["1000", "0"]  # unprivileged, and no GROQ/secret env vars
    assert escape.startswith("ERROR: path must stay inside")
    assert [d.file for d in result.diff] == ["auth/jwt.py"]
    assert ("+", "SECRET = os.environ['JWT_SECRET']") in [(l.op, l.text) for l in result.diff[0].lines]
    # destroyed afterwards
    assert _client.containers.list(all=True, filters={"label": LABEL}) == []
    assert _client.volumes.list(filters={"label": LABEL}) == []


def test_cancelled_run_still_destroys_its_container(local_repo):
    class SlowLLM(ScriptedLLM):
        async def chat(self, *a, **k):
            await asyncio.sleep(3600)

    settings = Settings(_env_file=None, sandbox_driver="docker")
    driver = DockerDriver(settings, SlowLLM([]))
    spec = RunSpec("EXP-TEST", 2, "https://github.com/x/y", "t", "m", SandboxLimits(timeout_s=60, memory_mb=256, cpus=0.5, network="none"))

    async def go():
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(driver.run(spec, Reporter()), timeout=8)

    asyncio.run(go())
    assert _client.containers.list(all=True, filters={"label": LABEL}) == []
    assert _client.volumes.list(filters={"label": LABEL}) == []


def test_demo_repo_installs_deps_offline_agent_can_use_them():
    """Setup container installs requirements.txt with internet; the agent's box has none but can import them."""
    llm = ScriptedLLM(
        [
            {"role": "assistant", "tool_calls": [call("run_command", "c1", command="python -c 'import dateutil; print(\"dateutil\", dateutil.__version__)'")]},
            {"role": "assistant", "tool_calls": [call("run_command", "c2", command="pip download six -q -d /tmp/x 2>&1 | tail -1; echo net=$?")]},
            {"role": "assistant", "tool_calls": [call("run_command", "c3", command="pytest -q 2>&1 | tail -1")]},
            {"role": "assistant", "content": "Looked around."},
        ]
    )
    settings = Settings(_env_file=None, sandbox_driver="docker", command_timeout_s=60, setup_timeout_s=120)
    driver = DockerDriver(settings, llm)
    spec = RunSpec("EXP-TEST", 3, "demo", "t", "m", SandboxLimits(timeout_s=240, memory_mb=512, cpus=1, network="none"))
    rep = Reporter()

    result = asyncio.run(driver.run(spec, rep))

    assert result.outcome == "pass", rep.logs
    deps, net, tests = llm.tool_results
    assert "dateutil 2.9.0" in deps
    assert "dateutil" not in net and ("error" in net.lower() or "fail" in net.lower())  # still no network
    assert "failed" in tests and "passed" in tests  # the demo suite runs (and fails on purpose)
    assert rep.steps[0] == "Install dependencies"
    assert result.diff == []  # .venv is not part of the diff
    assert _client.containers.list(all=True, filters={"label": LABEL}) == []
    assert _client.volumes.list(filters={"label": LABEL}) == []


@pytest.fixture
def buggy_repo(tmp_path, monkeypatch):
    """A tiny repo with one bug and a test that catches it."""
    src = tmp_path / "buggy"
    (src / "tests").mkdir(parents=True)
    (src / "calc.py").write_bytes(b"def add(a, b):\n    return a - b\n")
    (src / "tests" / "test_calc.py").write_bytes(b"from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    (src / "pytest.ini").write_bytes(b"[pytest]\npythonpath = .\n")

    def fake_clone(url, dest, timeout_s, max_mb):
        shutil.copytree(src, dest)
        import subprocess

        # LF files and no autocrlf, like a Linux checkout; otherwise git in the sandbox sees every file as changed
        for cmd in (["init", "-q"], ["add", "."], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
            subprocess.run(["git", "-c", "core.autocrlf=false", *cmd], cwd=dest, check=True)

    monkeypatch.setattr(docker_driver, "_clone", fake_clone)


def _check_spec(index):
    return RunSpec("EXP-TEST", index, "https://github.com/x/y", "Fix add", "m", SandboxLimits(timeout_s=180, memory_mb=256, cpus=0.5, network="none"), "python -m pytest -q")


def test_check_decides_pass_and_counts_tests(buggy_repo):
    llm = ScriptedLLM(
        [
            {"role": "assistant", "tool_calls": [call("write_file", "c1", path="calc.py", content="def add(a, b):\n    return a + b\n")], "usage": {"prompt_tokens": 120, "completion_tokens": 30}},
            {"role": "assistant", "content": "Fixed the sign.", "usage": {"prompt_tokens": 200, "completion_tokens": 10}},
        ]
    )
    driver = DockerDriver(Settings(_env_file=None, sandbox_driver="docker", check_timeout_s=60), llm)
    rep = Reporter()

    result = asyncio.run(driver.run(_check_spec(4), rep))

    assert result.outcome == "pass", rep.logs
    assert result.check.passed and (result.check.tests_passed, result.check.tests_total) == (1, 1)
    assert result.tampered == []
    assert (result.tokens_in, result.tokens_out, result.llm_calls) == (320, 40, 2)
    assert rep.steps[-1] == "Verify: python -m pytest -q"
    assert _client.containers.list(all=True, filters={"label": LABEL}) == []


def test_editing_the_tests_is_caught_and_undone_for_the_check(buggy_repo):
    """The agent 'fixes' the failure by changing the test. Flagged, never a pass, and the check runs the original test."""
    llm = ScriptedLLM(
        [
            {"role": "assistant", "tool_calls": [call("write_file", "c1", path="tests/test_calc.py", content="def test_add():\n    assert True\n")]},
            {"role": "assistant", "tool_calls": [call("run_command", "c2", command="git add -A && git -c user.email=a@a -c user.name=a commit -qm hide")]},
            {"role": "assistant", "content": "Updated the test; suite passes."},
        ]
    )
    driver = DockerDriver(Settings(_env_file=None, sandbox_driver="docker", check_timeout_s=60), llm)
    rep = Reporter()

    result = asyncio.run(driver.run(_check_spec(5), rep))

    assert result.outcome == "fail" and result.exit_reason == "tampered"
    assert result.tampered == ["tests/test_calc.py"]  # seen even though the agent committed it
    assert not result.check.passed and (result.check.tests_passed, result.check.tests_total) == (0, 1)
    assert _client.containers.list(all=True, filters={"label": LABEL}) == []
    assert _client.volumes.list(filters={"label": LABEL}) == []
