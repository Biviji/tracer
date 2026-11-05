"""The agent loop: model ⇄ tools until the model gives a final answer.

Runs in the orchestrator. The model never touches the sandbox directly: it
asks for one of four tools, and the `Workspace` executes that single action
inside the sandbox. The model's API key stays here; the sandbox has no network.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from app.llm import LLMClient, LLMError, Message
from app.sandbox.base import RunReporter

log = logging.getLogger(__name__)

#: What the model sees of one tool result; the rest is cut (it can read in parts).
MAX_TOOL_OUTPUT = 8000

SYSTEM_PROMPT = """You are a software engineering agent working on a repository.

The repository is checked out at /workspace inside an isolated sandbox:
- there is NO network access (installing packages or downloading will fail);
- you can inspect and change files and run commands with the tools provided;
- work step by step: look around before you change anything.

When you are done, reply WITHOUT calling a tool. That reply is your final answer:
state clearly what you found and what (if anything) you changed and why."""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and folders under a path in the repository (recursive, up to 3 levels).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Folder, relative to the repo root. Default '.'"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from the repository.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path relative to the repo root."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file in the repository with the given full content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to the repo root."},
                    "content": {"type": "string", "description": "The complete new file content."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the repository root (e.g. grep, tests). No network.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


class Workspace(Protocol):
    """Executes one tool action inside the sandbox and returns its text output."""

    async def list_files(self, path: str) -> str: ...
    async def read_file(self, path: str) -> str: ...
    async def write_file(self, path: str, content: str) -> str: ...
    async def run_command(self, command: str) -> str: ...


@dataclass
class AgentResult:
    answer: str | None
    #: False when the step limit was hit before the agent finished on its own.
    finished: bool
    tool_calls: int


def _clip(text: str, limit: int = MAX_TOOL_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n... [truncated {len(text) - limit} characters]"


def step_label(name: str, args: dict[str, Any]) -> str:
    """Short, comparable label: runs that did the same thing get the same label."""
    if name == "run_command":
        arg = " ".join(str(args.get("command", "")).split())
    else:
        arg = str(args.get("path", ".")).strip() or "."
    arg = arg if len(arg) <= 70 else arg[:67] + "..."
    return f"{name} {arg}"


async def _dispatch(ws: Workspace, name: str, args: dict[str, Any]) -> str:
    try:
        if name == "list_files":
            return await ws.list_files(str(args.get("path") or "."))
        if name == "read_file":
            return await ws.read_file(str(args["path"]))
        if name == "write_file":
            return await ws.write_file(str(args["path"]), str(args.get("content", "")))
        if name == "run_command":
            return await ws.run_command(str(args["command"]))
        return f"ERROR: unknown tool '{name}'. Use one of: list_files, read_file, write_file, run_command."
    except KeyError as missing:
        return f"ERROR: missing argument {missing} for {name}."


ELIDED = "[older tool output removed to save space; call the tool again if you need it]"


def _size(messages: list[Message]) -> int:
    return sum(len(str(m.get("content") or "")) + len(json.dumps(m.get("tool_calls") or "")) for m in messages)


def compact(messages: list[Message], budget_chars: int) -> list[Message]:
    """Keep the conversation under a size budget by shrinking the OLDEST tool outputs first.

    The task, the agent's own reasoning and the latest tool result are never removed,
    so the agent keeps its plan and can always re-read what it needs.
    """
    if _size(messages) <= budget_chars:
        return messages
    out = [dict(m) for m in messages]
    tool_idx = [i for i, m in enumerate(out) if m["role"] == "tool"][:-1]  # keep the newest intact
    for i in tool_idx:
        if _size(out) <= budget_chars:
            break
        if out[i]["content"] != ELIDED:
            out[i]["content"] = ELIDED
    return out


async def _chat(llm: LLMClient, model: str, messages: list[Message], budget: int, **kw: Any) -> Message:
    """Chat with compaction; if the provider still says "too large" (413), halve the budget and retry."""
    for _ in range(4):
        try:
            return await llm.chat(model, compact(messages, budget), **kw)
        except LLMError as err:
            if err.status != 413:
                raise
            budget //= 2
            log.info("request too large for %s, compacting context to %d chars", model, budget)
    return await llm.chat(model, compact(messages, budget), **kw)


def _assistant_message(reply: Message) -> Message:
    """Keep only standard fields: some providers add extras they reject on the way back."""
    msg: Message = {"role": "assistant", "content": reply.get("content")}
    if reply.get("tool_calls"):
        msg["tool_calls"] = reply["tool_calls"]
    return msg


async def run_agent(
    llm: LLMClient,
    model: str,
    task: str,
    ws: Workspace,
    report: RunReporter,
    *,
    max_steps: int,
    context_budget_chars: int = 40_000,
) -> AgentResult:
    messages: list[Message] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    calls_made = 0

    while calls_made < max_steps:
        reply = await _chat(llm, model, messages, context_budget_chars, tools=TOOLS)
        messages.append(_assistant_message(reply))
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            answer = (reply.get("content") or "").strip()
            return AgentResult(answer=answer or None, finished=True, tool_calls=calls_made)

        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments must be an object")
            except ValueError as err:
                output = f"ERROR: could not parse arguments as JSON: {err}"
                report.step(f"{name} (bad arguments)")
            else:
                report.step(step_label(name, args))
                output = await _dispatch(ws, name, args)
            calls_made += 1
            first_line = output.strip().splitlines()[0] if output.strip() else "(no output)"
            report.log(f"  {first_line[:120]}", "error" if output.startswith("ERROR") else "info")
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": _clip(output)})

    # Out of steps: ask for a final answer with tools disabled.
    messages.append(
        {"role": "user", "content": "Step limit reached. Stop using tools and give your final answer now."}
    )
    reply = await _chat(llm, model, messages, context_budget_chars)
    answer = (reply.get("content") or "").strip()
    return AgentResult(answer=answer or None, finished=False, tool_calls=calls_made)
