import asyncio
import json

import pytest

from app.agent.loop import run_agent, step_label
from app.sandbox.docker_driver import CloneError, _ContainerWorkspace, normalize_repo_url, parse_git_diff


class ScriptedLLM:
    """Replays a fixed list of assistant replies and records what it was sent."""

    name = "scripted"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def chat(self, model, messages, *, tools=None, temperature=None):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        return self.replies.pop(0)


def tool_call(name, call_id="c1", **args):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class FakeWorkspace:
    def __init__(self):
        self.files = {"auth/jwt.py": "SECRET = 'dev'\n"}
        self.commands = []

    async def list_files(self, path):
        return "\n".join(self.files)

    async def read_file(self, path):
        return self.files.get(path, f"ERROR: no such file {path}")

    async def write_file(self, path, content):
        self.files[path] = content
        return f"wrote {path}"

    async def run_command(self, command):
        self.commands.append(command)
        return "exit code 0\nok"


class Reporter:
    def __init__(self):
        self.steps, self.logs = [], []

    def running(self):
        pass

    def log(self, line, level="info"):
        self.logs.append((line, level))

    def step(self, label, detail=None):
        self.steps.append(label)


def test_agent_uses_tools_then_answers():
    llm = ScriptedLLM(
        [
            {"role": "assistant", "content": None, "tool_calls": [tool_call("read_file", path="auth/jwt.py")]},
            {"role": "assistant", "content": None, "tool_calls": [tool_call("run_command", "c2", command="grep -r SECRET .")]},
            {"role": "assistant", "content": "The JWT secret is hard-coded.", "reasoning": "provider extra"},
        ]
    )
    ws, rep = FakeWorkspace(), Reporter()

    result = asyncio.run(run_agent(llm, "m", "Check JWT security", ws, rep, max_steps=10))

    assert result.finished and result.answer == "The JWT secret is hard-coded."
    assert rep.steps == ["read_file auth/jwt.py", "run_command grep -r SECRET ."]
    assert ws.commands == ["grep -r SECRET ."]
    # the file content went back to the model as the tool result
    second_call = llm.calls[1]["messages"]
    assert second_call[-1] == {"role": "tool", "tool_call_id": "c1", "content": "SECRET = 'dev'\n"}
    # provider-only fields are not echoed back
    assert all("reasoning" not in m for m in llm.calls[-1]["messages"])


def test_step_limit_forces_a_final_answer_without_tools():
    looping = {"role": "assistant", "content": None, "tool_calls": [tool_call("list_files", path=".")]}
    llm = ScriptedLLM([looping, looping, {"role": "assistant", "content": "Ran out of steps; partial review."}])

    result = asyncio.run(run_agent(llm, "m", "task", FakeWorkspace(), Reporter(), max_steps=2))

    assert not result.finished
    assert result.answer == "Ran out of steps; partial review."
    assert llm.calls[-1]["tools"] is None


def test_agent_is_told_its_budget_and_warned_near_the_end():
    looping = {"role": "assistant", "content": None, "tool_calls": [tool_call("list_files", path=".")]}
    llm = ScriptedLLM([looping] * 6 + [{"role": "assistant", "content": "done"}])

    asyncio.run(run_agent(llm, "m", "task", FakeWorkspace(), Reporter(), max_steps=8))

    assert "budget of 8 tool calls" in llm.calls[0]["messages"][0]["content"]
    tool_results = [m["content"] for m in llm.calls[-1]["messages"] if m["role"] == "tool"]
    assert "[budget" not in tool_results[1]  # 6 left: no reminder yet
    assert "[budget: 5 tool calls left" in tool_results[2]
    assert "[budget: 2 tool calls left" in tool_results[5]


def test_bad_tool_arguments_are_reported_back_not_crashing():
    bad = {"id": "c1", "type": "function", "function": {"name": "read_file", "arguments": "{not json"}}
    llm = ScriptedLLM([{"role": "assistant", "tool_calls": [bad]}, {"role": "assistant", "content": "done"}])
    rep = Reporter()

    result = asyncio.run(run_agent(llm, "m", "task", FakeWorkspace(), rep, max_steps=5))

    assert result.answer == "done"
    assert llm.calls[1]["messages"][-1]["content"].startswith("ERROR: could not parse arguments")


def test_compact_shrinks_oldest_tool_outputs_first():
    from app.agent.loop import ELIDED, compact

    msgs = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "task"},
        {"role": "tool", "tool_call_id": "1", "content": "a" * 1000},
        {"role": "tool", "tool_call_id": "2", "content": "b" * 1000},
        {"role": "tool", "tool_call_id": "3", "content": "c" * 1000},
    ]
    out = compact(msgs, budget_chars=2200)
    assert [m["content"][:1] for m in out[2:]] == [ELIDED[:1], "b", "c"]
    assert out[1]["content"] == "task"
    assert msgs[2]["content"] == "a" * 1000  # original untouched
    assert compact(msgs, budget_chars=10) [-1]["content"] == "c" * 1000  # newest always kept


def test_request_too_large_is_compacted_and_retried():
    from app.llm import LLMError

    class TooLargeOnce(ScriptedLLM):
        async def chat(self, model, messages, **kw):
            if not getattr(self, "failed", False):
                self.failed = True
                raise LLMError("too large", status=413)
            return await super().chat(model, messages, **kw)

    llm = TooLargeOnce([{"role": "assistant", "content": "answer"}])
    result = asyncio.run(run_agent(llm, "m", "task", FakeWorkspace(), Reporter(), max_steps=3))
    assert result.answer == "answer"


def test_step_labels_are_comparable():
    assert step_label("run_command", {"command": "grep   -r  x ."}) == "run_command grep -r x ."
    assert step_label("list_files", {}) == "list_files ."
    assert len(step_label("read_file", {"path": "a/" * 100})) <= len("read_file ") + 70


@pytest.mark.parametrize(
    ("repo", "expected"),
    [
        ("github.com/Biviji/booking-system-practice", "https://github.com/Biviji/booking-system-practice"),
        ("https://gitlab.com/group/sub/project.git", "https://gitlab.com/group/sub/project.git"),
    ],
)
def test_repo_urls_accepted(repo, expected):
    assert normalize_repo_url(repo) == expected


@pytest.mark.parametrize("repo", ["file:///etc", "/etc/passwd", "git@github.com:x/y.git", "https://host/x; rm -rf /", "ext::sh"])
def test_repo_urls_refused(repo):
    with pytest.raises(CloneError):
        normalize_repo_url(repo)


@pytest.mark.parametrize(
    ("path", "inside"),
    [("src/a.java", "/workspace/src/a.java"), ("/src/../b", "/workspace/b"), (".", "/workspace")],
)
def test_paths_resolve_inside_workspace(path, inside):
    assert _ContainerWorkspace._inside(path) == inside


def test_paths_cannot_escape_workspace():
    with pytest.raises(ValueError):
        _ContainerWorkspace._inside("../../etc/passwd")


def test_parse_git_diff():
    text = """diff --git a/src/Jwt.java b/src/Jwt.java
index 1..2 100644
--- a/src/Jwt.java
+++ b/src/Jwt.java
@@ -1,2 +1,2 @@
-String secret = "dev";
+String secret = System.getenv("JWT_SECRET");
 unchanged
diff --git a/NEW.md b/NEW.md
+++ b/NEW.md
+hello
"""
    files = parse_git_diff(text)
    assert [f.file for f in files] == ["src/Jwt.java", "NEW.md"]
    assert [(l.op, l.text) for l in files[0].lines] == [
        ("-", 'String secret = "dev";'),
        ("+", 'String secret = System.getenv("JWT_SECRET");'),
    ]
    assert files[1].lines[0].text == "hello"
