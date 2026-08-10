"""Immutable version metadata captured when a QA experiment is executed."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Iterable


def digest_files(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    found = False
    for path in paths:
        value = Path(path)
        if not value.is_file():
            continue
        found = True
        digest.update(value.name.encode("utf-8"))
        digest.update(value.read_bytes())
    return digest.hexdigest()[:12] if found else "unknown"


def git_revision(root: Path) -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=root,
            text=True, encoding="utf-8", capture_output=True, check=False, timeout=5,
        )
        if commit.returncode != 0:
            return "unknown"
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root,
            text=True, encoding="utf-8", capture_output=True, check=False, timeout=5,
        )
        suffix = "-dirty" if dirty.returncode == 0 and dirty.stdout.strip() else ""
        return commit.stdout.strip() + suffix
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def capture_experiment(
    *,
    root: Path,
    dataset_files: Iterable[Path],
    prompt_files: Iterable[Path],
    models: dict[str, Any],
    deployment_threshold: float,
    concurrency: int,
) -> dict[str, Any]:
    return {
        "git_commit": git_revision(root),
        "dataset_version": digest_files(dataset_files),
        "prompt_version": digest_files(prompt_files),
        "models": {str(key): str(value) for key, value in models.items()},
        "deployment_threshold": float(deployment_threshold),
        "concurrency": int(concurrency),
    }


__all__ = ["capture_experiment", "digest_files", "git_revision"]
