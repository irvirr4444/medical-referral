"""Small process helpers for the local referral pipeline launcher."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


class LaunchError(RuntimeError):
    """Operator-facing startup failure with a short corrective message."""


def npm_executable() -> str:
    names = ("npm.cmd", "npm") if sys.platform == "win32" else ("npm",)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    raise LaunchError(
        "startup: error: npm was not found. Install Node.js, then run npm install in frontend/."
    )


def frontend_dependencies_present(frontend_dir: Path) -> bool:
    return (frontend_dir / "node_modules").is_dir()


def port_is_occupied(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def occupied_port_message(service: str, host: str, port: int, flag: str) -> str:
    return (
        f"startup: error: {service} port {port} on {host} is already in use. "
        f"Stop the other process or pass {flag}."
    )


def wait_for_http(
    url: str,
    *,
    timeout_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    opener: urllib.request.OpenerDirector | None = None,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    http = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_error = "timed out"
    while time.monotonic() < deadline:
        try:
            with http.open(url, timeout=1.5) as response:
                status = getattr(response, "status", 200)
                if status < 400:
                    return
                last_error = f"HTTP {status}"
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = str(error.reason) if isinstance(error, urllib.error.URLError) else str(error)
            last_error = last_error or type(error).__name__
        sleep(0.25)
    raise LaunchError(f"startup: error: {url} did not become ready. Last error: {last_error}")


def spawn_child(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[Any]:
    kwargs: dict[str, Any] = {
        "args": list(command),
        "cwd": None if cwd is None else str(cwd),
        "env": env,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(**kwargs)


def terminate_process_tree(proc: subprocess.Popen[Any] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            proc.kill()
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass


def stop_children(children: Sequence[subprocess.Popen[Any] | None]) -> None:
    for proc in children:
        terminate_process_tree(proc)


def supervise_children(
    named: Sequence[tuple[str, subprocess.Popen[Any]]],
    *,
    sleep: Callable[[float], None] | None = None,
) -> int:
    sleeper = time.sleep if sleep is None else sleep
    children = [proc for _, proc in named]
    try:
        while True:
            for name, proc in named:
                code = proc.poll()
                if code is not None:
                    print(
                        f"startup: error: {name} exited unexpectedly (code {code}).",
                        file=sys.stderr,
                    )
                    stop_children(children)
                    return 1
            sleeper(0.4)
    except KeyboardInterrupt:
        stop_children(children)
        return 0
