"""Real sandboxes: locked-down Docker containers, fresh for every run.

Per run:
  1. clone the repo on the orchestrator side (only from allowed hosts), or copy the demo repo
  2. if the repo declares dependencies: a short-lived *setup* container on an isolated bridge
     network installs them into /workspace (.venv / node_modules), then is destroyed.
     The model is not involved in this step.
  3. the *agent* container starts on the same per-run volume with NO network, no
     capabilities, no-new-privileges, memory / CPU / process caps, an unprivileged user,
     no secrets in its env, and optionally gVisor; each agent tool call = one `docker exec`
  4. collect `git diff` (against the starting commit) and the agent's answer; flag changed
     test files / test config as tampering
  5. with a check command: destroy the agent container, start a fresh *verify* container on
     the same volume (no network), put test files back as they were, make sure installed
     dependencies weren't altered, then run the check — its result decides pass / fail
  6. destroy the containers and the volume — always, including on timeout, cancel and crash

So the model never shares a box with the internet.
Docker SDK calls block, so they run in worker threads.
"""

import asyncio
import io
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path, PurePosixPath

import docker
from docker.errors import DockerException, NotFound
from docker.models.containers import Container

from app.agent import run_agent
from app.agent.loop import Usage
from app.config import Settings
from app.llm import LLMClient, LLMError
from app.models.schemas import RunCheck
from app.replay import export_tree, open_history
from app.sandbox.base import PROVIDER_DOWN, RunReporter, RunResult, RunSpec
from app.sandbox.gitrepo import (
    SAFE_GIT_CONFIG,
    CloneError,
    is_demo,
    normalize_repo_url,
    parse_git_diff,
    snapshot,
)
from app.sandbox.verify import parse_test_counts, protected_files, restore_script, tail

log = logging.getLogger(__name__)

WORKDIR = "/workspace"
AGENT_UID = 1000
LABEL = "trace.sandbox"
#: Setup containers use Docker's default bridge (docker0) with public DNS servers: user-defined
#: networks force Docker's embedded DNS, which gVisor can't use. Nothing else of TRACE runs on
#: docker0 (compose has its own network); on a server, deploy/README.md turns off
#: container-to-container traffic there and deploy/sandbox-egress.sh blocks private ranges
#: and cloud metadata from it.
SETUP_NETWORK = "bridge"
SETUP_DNS = ["1.1.1.1", "8.8.8.8"]
#: Installed dependencies and test-run leftovers must not show up in the agent's diff.
_DEP_DIRS = (".venv/", "node_modules/", "__pycache__/", "*.pyc", ".pytest_cache/")


def _clone(url: str, dest: Path, timeout_s: int, max_mb: int) -> None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo"}  # private repos fail fast
    argv = [
        "git",
        # https only, and no redirects: a redirect could lead away from the allowed host.
        *SAFE_GIT_CONFIG,
        "clone", "--depth", "1", "--single-branch", "--no-tags", "--", url, str(dest),
    ]  # fmt: skip
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s, env=env)
    except subprocess.TimeoutExpired as err:
        raise CloneError(f"clone timed out after {timeout_s}s") from err
    if proc.returncode != 0:
        msg = (proc.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise CloneError(f"clone failed: {msg[:200]}")
    size_mb = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / 1e6
    if size_mb > max_mb:
        raise CloneError(f"repo is {size_mb:.0f}MB, over the {max_mb}MB cap")


def _copy_demo(src: Path, dest: Path) -> None:
    """The built-in demo project, as a fresh one-commit git repo."""
    if not (src / "README.md").is_file():
        raise CloneError(f"demo repo not found at {src}")
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"))
    snapshot(dest, "demo repo")


def _head_sha(repo: Path) -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


#: Fingerprint of installed dependencies (bytecode caches excluded: running tests rewrites them).
#: If it changes during the run, the agent edited the tools the check relies on.
DEPS_FINGERPRINT = (
    "for d in .venv node_modules; do [ -d \"$d\" ] && find \"$d\" -type f ! -name '*.pyc' "
    "! -path '*/.cache/*' -print0; done | sort -z | xargs -0 -r sha256sum | sha256sum | cut -c1-16"
)
DEPS_TAMPERED = "installed dependencies (.venv / node_modules)"


def _exclude_dep_dirs(repo: Path) -> None:
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8", newline="\n") as f:
        f.write("\n# installed by TRACE setup\n" + "\n".join(_DEP_DIRS) + "\n")


def install_command(repo: Path) -> str | None:
    """Shell command installing the repo's declared dependencies, or None if it declares none.
    npm lifecycle scripts are skipped; pip may still build packages (setup.py), which happens
    in the setup container — the model never touches it."""
    steps: list[str] = []
    reqs = [r for r in ("requirements.txt", "requirements-dev.txt", "requirements-test.txt") if (repo / r).is_file()]
    pyproject = repo / "pyproject.toml"
    packaged = (repo / "setup.py").is_file() or (
        pyproject.is_file() and ("[project]" in (text := pyproject.read_text(errors="replace")) or "[build-system]" in text)
    )
    if reqs or packaged:
        pip = ".venv/bin/pip install -q --disable-pip-version-check"
        steps.append("python -m venv --system-site-packages .venv")
        # `pytest` from the image runs on the system python; point it at the venv instead.
        steps.append(
            r"""printf '#!/bin/sh\nexec /workspace/.venv/bin/python -m pytest "$@"\n' > .venv/bin/pytest"""
            " && chmod +x .venv/bin/pytest"
        )
        steps += [f"{pip} -r {r}" for r in reqs]
        if packaged:
            steps.append(f"({pip} -e . || echo 'note: the package itself was not installed')")
    if (repo / "package.json").is_file():
        npm = "npm ci" if (repo / "package-lock.json").is_file() else "npm install"
        steps.append(f"{npm} --ignore-scripts --no-audit --no-fund --loglevel=error")
    return " && ".join(steps) or None


def _force_remove(func, path, _exc) -> None:
    """rmtree helper: git marks pack files read-only, which blocks deletion on Windows."""
    try:
        os.chmod(path, 0o700)
        func(path)
    except OSError:
        log.warning("could not delete temp file %s", path)


def _tar_dir(src: Path) -> bytes:
    """Tar the checkout, owned by the sandbox user so the agent can edit it."""

    def own(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = AGENT_UID
        info.uname = info.gname = "agent"
        return info

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for child in sorted(src.iterdir()):
            tar.add(child, arcname=child.name, filter=own)
    return buf.getvalue()


def _tar_files(files: dict[str, str]) -> bytes:
    """Several files (repo-relative paths) with their folders, owned by the sandbox user."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        dirs = sorted({str(p) for path in files for p in PurePosixPath(path).parents if str(p) != "."})
        for d in dirs:
            info = tarfile.TarInfo(d)
            info.type, info.mode = tarfile.DIRTYPE, 0o755
            info.uid = info.gid = AGENT_UID
            tar.addfile(info)
        for path, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(path)
            info.size, info.mode = len(data), 0o644
            info.uid = info.gid = AGENT_UID
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _case_tree(repo: str, sha: str, dest: Path, settings: Settings) -> None:
    """Replay: the code just before the fix, as a fresh repo without history."""
    with open_history(repo, settings) as git_dir:
        export_tree(git_dir, sha, dest)


def _tar_file(name: str, content: str) -> bytes:
    data = content.encode()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.uid = info.gid = AGENT_UID
    info.uname = info.gname = "agent"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class _ContainerWorkspace:
    """The agent's tools, each executed as one command inside the container."""

    def __init__(self, container: Container, command_timeout_s: int):
        self._c = container
        self._timeout = command_timeout_s

    async def _exec(self, argv: list[str]) -> tuple[int, str]:
        def run() -> tuple[int, str]:
            res = self._c.exec_run(argv, workdir=WORKDIR, user="agent", demux=True)
            out, err = res.output if isinstance(res.output, tuple) else (res.output, None)
            text = (out or b"").decode(errors="replace") + (err or b"").decode(errors="replace")
            return res.exit_code or 0, text

        return await asyncio.to_thread(run)

    @staticmethod
    def _inside(path: str) -> str:
        """Resolve a repo-relative path; refuse to leave /workspace."""
        p = PurePosixPath(WORKDIR, path.lstrip("/"))
        parts: list[str] = []
        for part in p.parts[1:]:
            if part == "..":
                if parts:
                    parts.pop()
            elif part != ".":
                parts.append(part)
        resolved = PurePosixPath("/", *parts)
        if resolved != PurePosixPath(WORKDIR) and PurePosixPath(WORKDIR) not in resolved.parents:
            raise ValueError("path must stay inside the repository")
        return str(resolved)

    async def list_files(self, path: str) -> str:
        try:
            target = self._inside(path)
        except ValueError as err:
            return f"ERROR: {err}"
        prune = []
        for d in (".git", ".venv", "node_modules"):
            prune += ["-not", "-path", f"*/{d}", "-not", "-path", f"*/{d}/*"]
        code, out = await self._exec(["find", target, "-maxdepth", "3", *prune])
        lines = [line.removeprefix(WORKDIR + "/") for line in out.splitlines()][:400]
        return "\n".join(lines) if code == 0 else f"ERROR: {out.strip()}"

    async def read_file(self, path: str) -> str:
        try:
            target = self._inside(path)
        except ValueError as err:
            return f"ERROR: {err}"
        code, out = await self._exec(["head", "-c", "60000", target])
        return out if code == 0 else f"ERROR: {out.strip()}"

    async def write_file(self, path: str, content: str) -> str:
        try:
            target = PurePosixPath(self._inside(path))
        except ValueError as err:
            return f"ERROR: {err}"
        await self._exec(["mkdir", "-p", str(target.parent)])
        ok = await asyncio.to_thread(self._c.put_archive, str(target.parent), _tar_file(target.name, content))
        return f"wrote {len(content)} characters to {target.relative_to(WORKDIR)}" if ok else "ERROR: write failed"

    async def run_command(self, command: str) -> str:
        code, out = await self._exec(["timeout", "-s", "KILL", str(self._timeout), "bash", "-lc", command])
        if code == 137:
            out += f"\n[killed: exceeded {self._timeout}s or the memory limit]"
        return f"exit code {code}\n{out}" if out.strip() else f"exit code {code}"


class _Quiet:
    """Reporter for work that belongs to no run (case validation)."""

    closed = False

    def running(self) -> None:
        pass

    def log(self, line: str, level: str = "info") -> None:
        pass

    def step(self, label: str, detail: str | None = None) -> None:
        pass


class DockerDriver:
    name = "docker"
    expected_steps = 10

    def __init__(self, settings: Settings, llm: LLMClient):
        self._s = settings
        self._llm = llm
        self._client = docker.from_env()
        if settings.sandbox_runtime:
            self.name = f"docker+{self.runtime_label.lower()}"  # shown in /health

    # ---- lifecycle helpers ----

    def validate_repo(self, repo: str) -> None:
        if not is_demo(repo):
            try:
                normalize_repo_url(repo, self._s.repo_hosts)
            except CloneError as err:
                raise ValueError(str(err)) from err

    def check(self) -> None:
        """Fail fast at startup if Docker, the sandbox image or the runtime is missing."""
        self._client.ping()
        self._client.images.get(self._s.sandbox_image)
        runtime = self._s.sandbox_runtime
        if runtime and runtime not in (self._client.info().get("Runtimes") or {}):
            raise RuntimeError(f"Docker has no runtime '{runtime}' (SANDBOX_RUNTIME); see deploy/README.md")

    @property
    def runtime_label(self) -> str:
        r = self._s.sandbox_runtime
        return "gVisor" if r == "runsc" else r or "runc"

    def remove_orphans(self) -> int:
        """Containers / volumes left by a crash or restart: they must not outlive their run."""
        orphans = self._client.containers.list(all=True, filters={"label": LABEL})
        for c in orphans:
            c.remove(force=True)
        for v in self._client.volumes.list(filters={"label": LABEL}):
            v.remove(force=True)
        return len(orphans)

    def _start(self, spec: RunSpec, volume: str, *, role: str, network: str = "none") -> Container:
        lim = spec.limits
        return self._client.containers.run(
            self._s.sandbox_image,
            detach=True,
            name=f"trace-{spec.experiment_id.lower()}-r{spec.run_index}-{role}-{uuid.uuid4().hex[:6]}",
            labels={LABEL: "1", "trace.experiment": spec.experiment_id, "trace.role": role},
            network_mode=network,
            dns=SETUP_DNS if network != "none" else None,
            volumes={volume: {"bind": WORKDIR, "mode": "rw"}},
            runtime=self._s.sandbox_runtime or None,
            mem_limit=f"{lim.memory_mb}m",
            memswap_limit=f"{lim.memory_mb}m",  # no swap: the memory cap is real
            nano_cpus=int(lim.cpus * 1e9),
            pids_limit=256,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            user="agent",
            environment={},  # nothing from the orchestrator's env, so no secrets
        )

    # ---- one run ----

    async def run(self, spec: RunSpec, report: RunReporter) -> RunResult:
        demo = is_demo(spec.repo)
        url = ""
        if not demo:
            try:
                url = normalize_repo_url(spec.repo, self._s.repo_hosts)
            except CloneError as err:
                report.log(f"✗ {err}", "error")
                return RunResult.killed("bad_repo_url")

        tmp = Path(tempfile.mkdtemp(prefix="trace-clone-"))
        repo = tmp / "repo"
        containers: list[Container] = []
        volume = None
        try:
            try:
                if spec.case:
                    report.log(f"$ git checkout {spec.case.parent[:10]}  (the code just before fix {spec.case.id})")
                    await asyncio.to_thread(_case_tree, spec.repo, spec.case.parent, repo, self._s)
                elif demo:
                    report.log("$ using the built-in demo repo")
                    await asyncio.to_thread(_copy_demo, self._s.demo_repo_dir, repo)
                else:
                    report.log(f"$ git clone {url}")
                    await asyncio.to_thread(_clone, url, repo, self._s.clone_timeout_s, self._s.max_repo_mb)
            except CloneError as err:
                report.log(f"✗ {err}", "error")
                return RunResult.killed("clone_failed")
            await asyncio.to_thread(_exclude_dep_dirs, repo)
            base = await asyncio.to_thread(_head_sha, repo)
            archive = await asyncio.to_thread(_tar_dir, repo)
            install = install_command(repo) if self._s.sandbox_install_deps else None

            volume = await asyncio.to_thread(self._client.volumes.create, labels={LABEL: "1"})
            report.running()
            if install:
                await self._setup(spec, volume.name, archive, install, report, containers)

            container = await asyncio.to_thread(self._start, spec, volume.name, role="agent")
            containers.append(container)
            if not install:
                await asyncio.to_thread(container.put_archive, WORKDIR, archive)
            report.log(
                f"sandbox up · {spec.limits.memory_mb}MB · {spec.limits.cpus:g} CPU · no network · {self.runtime_label}"
            )

            ws = _ContainerWorkspace(container, self._s.command_timeout_s)
            deps_before = (await ws._exec(["bash", "-c", DEPS_FINGERPRINT]))[1].strip() if spec.check_command else ""
            usage = Usage()

            def spent(res: RunResult) -> RunResult:
                res.tokens_in, res.tokens_out, res.llm_calls = usage.tokens_in, usage.tokens_out, usage.calls
                return res

            try:
                result = await run_agent(
                    self._llm,
                    spec.model,
                    spec.task,
                    ws,
                    report,
                    max_steps=self._s.agent_max_steps,
                    context_budget_chars=self._s.agent_context_chars,
                    usage=usage,
                )
            except LLMError as err:
                log.warning("run %s#%d: model error: %s", spec.experiment_id, spec.run_index, err)
                report.log(f"✗ model error: {str(err)[:160]}", "error")
                if err.provider_down:
                    return spent(RunResult.killed(f"{PROVIDER_DOWN} ({err.status or 'network'})"))
                return spent(RunResult.killed(f"model_error ({err.status or 'network'})"))

            # Diff against the starting commit, so changes the agent committed still show.
            code, diff_text = await ws._exec(["bash", "-lc", f"git add -A -N . && git diff --no-color {base}"])
            _, names = await ws._exec(["bash", "-lc", f"git diff --name-only {base}"])
            diff = parse_git_diff(diff_text)
            tampered = protected_files(names.splitlines()) if code == 0 else [".git"]
            if tampered:
                report.log(f"⚠ changed test files / test setup: {', '.join(tampered)[:160]}", "error")

            check = None
            if spec.check_command:
                # The agent's container goes first: nothing it started keeps running during the check.
                await asyncio.to_thread(self._destroy, container)
                check, deps_changed = await self._verify(spec, volume.name, base, tampered, deps_before, report, containers)
                if deps_changed:
                    tampered = [*tampered, DEPS_TAMPERED]

            res = RunResult(outcome="fail", diff=diff, answer=result.answer, check=check, tampered=tampered)
            if not result.finished:
                res.exit_reason = "step_limit"
            if tampered:
                res.exit_reason = "tampered"
            elif check is not None:
                res.outcome = "pass" if check.passed else "fail"
                if not check.passed:
                    res.exit_reason = "check_failed"
                res.tests_passed, res.tests_total = check.tests_passed, check.tests_total
            elif result.finished:
                res.outcome = "pass"  # no check command: we can only trust the agent
            return spent(res)
        finally:
            shutil.rmtree(tmp, onexc=_force_remove)
            # Shielded: a cancelled run still waits for its sandbox to be gone.
            await asyncio.shield(asyncio.to_thread(self._destroy_all, containers, volume))

    async def _verify(
        self,
        spec: RunSpec,
        volume: str,
        base: str,
        tampered: list[str],
        deps_before: str,
        report: RunReporter,
        containers: list[Container],
    ) -> tuple[RunCheck, bool]:
        """Run the check in a fresh container: test files restored, no network. Returns (check, deps_changed)."""
        cmd = spec.check_command or ""
        verify = await asyncio.to_thread(self._start, spec, volume, role="verify")
        containers.append(verify)
        ws = _ContainerWorkspace(verify, self._s.check_timeout_s)
        report.log(f"$ verifying in a fresh sandbox: {cmd}")
        if tampered:
            await ws._exec(["bash", "-c", restore_script(tampered, base)])
            report.log("  test files restored to their original version before checking")
        if spec.case:
            await asyncio.to_thread(verify.put_archive, WORKDIR, _tar_files(spec.case.hidden_tests))
            report.log(f"  hidden tests from the real fix added: {', '.join(spec.case.test_files)[:160]}")
        deps_after = (await ws._exec(["bash", "-c", DEPS_FINGERPRINT]))[1].strip()
        deps_changed = bool(deps_before) and deps_after != deps_before
        if deps_changed:
            report.log("⚠ installed dependencies were modified during the run", "error")

        t = self._s.check_timeout_s
        code, out = await ws._exec(["timeout", "-s", "KILL", str(t), "bash", "-lc", cmd])
        passed_n, total_n = parse_test_counts(out)
        ok = code == 0
        counts = f" · {passed_n}/{total_n} tests" if total_n is not None else ""
        report.step(f"Verify: {cmd}", detail=tail(out, 600))
        report.log(f"{'✓' if ok else '✗'} check {'passed' if ok else f'failed (exit {code})'}{counts}", "ok" if ok else "error")
        check = RunCheck(
            command=cmd,
            exit_code=code,
            passed=ok,
            tests_passed=passed_n,
            tests_total=total_n,
            output=tail(out) + (f"\n[killed: exceeded {t}s]" if code == 137 else ""),
        )
        return check, deps_changed

    async def validate_case(self, spec: RunSpec) -> tuple[bool, str | None]:
        """A past bug is a fair exam only if its tests fail on the code before the fix and pass
        with the engineer's fix. Runs both in a sandbox (no model involved)."""
        case = spec.case
        assert case is not None and spec.check_command
        tmp = Path(tempfile.mkdtemp(prefix="trace-validate-"))
        repo = tmp / "repo"
        containers: list[Container] = []
        volume = None
        quiet = _Quiet()
        try:
            try:
                await asyncio.to_thread(_case_tree, spec.repo, case.parent, repo, self._s)
            except CloneError as err:
                return False, str(err)
            await asyncio.to_thread(_exclude_dep_dirs, repo)
            archive = await asyncio.to_thread(_tar_dir, repo)
            install = install_command(repo) if self._s.sandbox_install_deps else None
            volume = await asyncio.to_thread(self._client.volumes.create, labels={LABEL: "1"})
            if install:
                await self._setup(spec, volume.name, archive, install, quiet, containers)
            box = await asyncio.to_thread(self._start, spec, volume.name, role=f"validate-{case.id[:7]}")
            containers.append(box)
            if not install:
                await asyncio.to_thread(box.put_archive, WORKDIR, archive)
            ws = _ContainerWorkspace(box, self._s.check_timeout_s)
            t = str(self._s.check_timeout_s)
            check = ["timeout", "-s", "KILL", t, "bash", "-lc", spec.check_command]

            await asyncio.to_thread(box.put_archive, WORKDIR, _tar_files(case.hidden_tests))
            code, out = await ws._exec(check)
            if code == 0:
                return False, "its test already passes on the code before the fix"
            fixed = {p: c for p, c in case.fix_files.items() if c is not None}
            if fixed:
                await asyncio.to_thread(box.put_archive, WORKDIR, _tar_files(fixed))
            for p in (p for p, c in case.fix_files.items() if c is None):
                await ws._exec(["rm", "-f", "--", p])
            code, out = await ws._exec(check)
            if code != 0:
                passed, total = parse_test_counts(out)
                counts = f", {passed}/{total} tests pass" if total is not None else ""
                return False, f"the tests fail even with the engineer's fix (exit {code}{counts})"
            return True, None
        finally:
            shutil.rmtree(tmp, onexc=_force_remove)
            await asyncio.shield(asyncio.to_thread(self._destroy_all, containers, volume))

    async def _setup(
        self,
        spec: RunSpec,
        volume: str,
        archive: bytes,
        install: str,
        report: RunReporter,
        containers: list[Container],
    ) -> None:
        """Install dependencies in a throwaway container that has internet; no model involved.
        A failed install is reported and the agent still runs (just without those packages)."""
        setup = await asyncio.to_thread(self._start, spec, volume, role="setup", network=SETUP_NETWORK)
        containers.append(setup)
        await asyncio.to_thread(setup.put_archive, WORKDIR, archive)
        report.log("$ installing dependencies (setup container: internet on, no model)")
        t = self._s.setup_timeout_s
        code, out = await _ContainerWorkspace(setup, t)._exec(["timeout", "-s", "KILL", str(t), "bash", "-lc", install])
        if code == 0:
            report.step("Install dependencies", detail=install)
            report.log("✓ dependencies installed · setup container destroyed · agent starts offline", "ok")
        else:
            reason = f"timed out after {t}s" if code == 137 else f"exit code {code}"
            tail = "\n".join(out.strip().splitlines()[-6:])
            report.step("Install dependencies (failed)", detail=f"{install}\n{reason}\n{tail}")
            report.log(f"✗ dependency install failed ({reason}); continuing without them", "error")
        await asyncio.to_thread(self._destroy, setup)
        containers.remove(setup)

    def _destroy_all(self, containers: list[Container], volume) -> None:
        for c in containers:
            self._destroy(c)
        if volume is not None:
            try:
                volume.remove(force=True)
            except NotFound:
                pass
            except DockerException:
                log.exception("could not remove sandbox volume %s", volume.name)

    @staticmethod
    def _destroy(container: Container) -> None:
        try:
            container.remove(force=True)
        except NotFound:
            pass
        except DockerException:
            log.exception("could not remove sandbox %s", container.name)


__all__ = ["CloneError", "DockerDriver", "install_command", "is_demo", "normalize_repo_url", "parse_git_diff"]
