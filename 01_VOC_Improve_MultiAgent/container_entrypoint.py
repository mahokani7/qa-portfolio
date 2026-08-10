"""Start and supervise the VOC gRPC Agent runtime and web server in one container."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AGENT_PORTS = (6001, 6002, 6003, 6004, 6005, 6006)
STOP_REQUESTED = False


def _request_stop(_signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def _wait_for_agents(timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not STOP_REQUESTED:
        ready = 0
        for port in AGENT_PORTS:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    ready += 1
            except OSError:
                pass
        if ready == len(AGENT_PORTS):
            return True
        time.sleep(0.5)
    return False


def _start(command: list[str]) -> subprocess.Popen:
    return subprocess.Popen(command, cwd=ROOT, start_new_session=os.name != "nt")


def _stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        if os.name != "nt":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except OSError:
            pass


def main() -> int:
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, _request_stop)

    os.environ.setdefault("WEB_HOST", "0.0.0.0")
    os.environ.setdefault("WEB_PORT", "8000")
    startup_timeout = float(os.environ.get("AGENT_STARTUP_TIMEOUT", "45"))

    grpc_process: subprocess.Popen | None = None
    web_process: subprocess.Popen | None = None
    try:
        grpc_process = _start([sys.executable, "grpc_server.py"])
        if not _wait_for_agents(startup_timeout):
            if grpc_process.poll() is not None:
                print(
                    f"[container] gRPC supervisor exited with code {grpc_process.returncode}.",
                    file=sys.stderr,
                )
            else:
                print("[container] six Agents did not become ready in time.", file=sys.stderr)
            return 1

        web_process = _start([sys.executable, "web_app.py"])
        print("[container] VOC web and six gRPC Agents are ready.", flush=True)

        while not STOP_REQUESTED:
            if grpc_process.poll() is not None:
                print(
                    f"[container] gRPC supervisor exited with code {grpc_process.returncode}.",
                    file=sys.stderr,
                )
                return grpc_process.returncode or 1
            if web_process.poll() is not None:
                print(
                    f"[container] web server exited with code {web_process.returncode}.",
                    file=sys.stderr,
                )
                return web_process.returncode or 1
            time.sleep(1)
        return 0
    finally:
        _stop(web_process)
        _stop(grpc_process)


if __name__ == "__main__":
    raise SystemExit(main())
