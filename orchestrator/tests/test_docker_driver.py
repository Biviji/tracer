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
    spec = RunSpec("EXP-TEST", 1, "https://example.com/x/y", "Check JWT", "m", SandboxLimits(timeout_s=120, memory_mb=256, cpus=0.5, network="none"))
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


def test_cancelled_run_still_destroys_its_container(local_repo):
    class SlowLLM(ScriptedLLM):
        async def chat(self, *a, **k):
            await asyncio.sleep(3600)

    settings = Settings(_env_file=None, sandbox_driver="docker")
    driver = DockerDriver(settings, SlowLLM([]))
    spec = RunSpec("EXP-TEST", 2, "https://example.com/x/y", "t", "m", SandboxLimits(timeout_s=60, memory_mb=256, cpus=0.5, network="none"))

    async def go():
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(driver.run(spec, Reporter()), timeout=8)

    asyncio.run(go())
    assert _client.containers.list(all=True, filters={"label": LABEL}) == []
