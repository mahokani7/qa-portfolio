"""In-memory background job manager for long-running browser QA operations."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable


ProgressCallback = Callable[..., None]
JobRunner = Callable[[ProgressCallback], Awaitable[dict[str, Any]]]


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class AsyncJobManager:
    def __init__(self, max_history: int = 100) -> None:
        self.max_history = max(10, max_history)
        self._jobs: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _public(job: dict[str, Any]) -> dict[str, Any]:
        value = {
            key: value for key, value in job.items()
            if key not in {"runner"}
        }
        if job.get("started_at") and job.get("status") == "running":
            try:
                started = datetime.fromisoformat(str(job["started_at"]))
                elapsed = max(0.0, (datetime.now().astimezone() - started).total_seconds())
            except (TypeError, ValueError):
                elapsed = 0.0
            progress = max(1, int(job.get("progress") or 1))
            value["elapsed_seconds"] = round(elapsed, 1)
            value["eta_seconds"] = round(max(0.0, elapsed * (100 - progress) / progress), 1)
        else:
            value["elapsed_seconds"] = value.get("elapsed_seconds", 0)
            value["eta_seconds"] = 0
        return value

    async def create(self, operation: str, label: str, runner: JobRunner) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "operation": operation,
            "label": label,
            "status": "queued",
            "progress": 0,
            "phase": "실행 대기 중",
            "current_item": "",
            "processed_items": 0,
            "total_items": 0,
            "cancel_requested": False,
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
        }
        async with self._lock:
            self._jobs[job_id] = job
            self._tasks[job_id] = asyncio.create_task(self._execute(job_id, runner))
            self._prune_locked()
        return self._public(job)

    async def _execute(self, job_id: str, runner: JobRunner) -> None:
        job = self._jobs[job_id]
        job.update(status="running", progress=1, phase="실행 시작", started_at=_now())

        def update(
            progress: int,
            phase: str,
            current_item: str = "",
            processed_items: int | None = None,
            total_items: int | None = None,
        ) -> None:
            current = self._jobs.get(job_id)
            if current is None or current["status"] not in {"queued", "running"}:
                return
            current["progress"] = max(current["progress"], min(99, max(0, int(progress))))
            current["phase"] = str(phase or current["phase"])
            if current_item:
                current["current_item"] = str(current_item)[:300]
            if processed_items is not None:
                current["processed_items"] = max(0, int(processed_items))
            if total_items is not None:
                current["total_items"] = max(0, int(total_items))

        try:
            result = runner(update)
            if inspect.isawaitable(result):
                result = await result
            job.update(
                status="completed",
                progress=100,
                phase="완료",
                result=result,
                finished_at=_now(),
            )
        except asyncio.CancelledError:
            job.update(
                status="cancelled",
                phase="사용자 취소",
                cancel_requested=True,
                finished_at=_now(),
            )
        except Exception as exc:
            job.update(
                status="failed",
                phase="실행 실패",
                error={"type": type(exc).__name__, "message": str(exc)[-4000:]},
                finished_at=_now(),
            )
        finally:
            self._tasks.pop(job_id, None)

    def _prune_locked(self) -> None:
        if len(self._jobs) <= self.max_history:
            return
        finished = [
            job for job in self._jobs.values()
            if job["status"] in {"completed", "failed", "cancelled"}
        ]
        finished.sort(key=lambda value: value["created_at"])
        for job in finished[: max(0, len(self._jobs) - self.max_history)]:
            self._jobs.pop(job["job_id"], None)

    async def get(self, job_id: str) -> dict[str, Any] | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            return self._public(job) if job else None

    async def list(self, limit: int = 50) -> list[dict[str, Any]]:
        async with self._lock:
            jobs = sorted(
                self._jobs.values(), key=lambda value: value["created_at"], reverse=True
            )[: max(1, min(limit, 100))]
            return [self._public(job) for job in jobs]

    async def cancel(self, job_id: str) -> dict[str, Any] | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job["status"] in {"completed", "failed", "cancelled"}:
                return self._public(job)
            job["cancel_requested"] = True
            job["phase"] = "취소 처리 중"
            task = self._tasks.get(job_id)
            if task:
                task.cancel()
            return self._public(job)


__all__ = ["AsyncJobManager"]
