"""CloudShell 업로드용 ZIP 2개를 만듭니다.

  aws_upload/qa_evidence.zip     — S3에 보관할 QA 증적 7종
  aws_upload/voc_qa_program.zip  — CloudShell에서 실행·재검증할 최소 프로그램 소스

.env, .venv, reports, __pycache__, .git 은 절대 포함하지 않습니다.

사용:
  .venv/Scripts/python.exe scripts/pack_for_cloudshell.py
"""

from __future__ import annotations

import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD = PROJECT_ROOT / "aws_upload"
EVIDENCE = UPLOAD / "qa_evidence"

# CloudShell에서 pytest 32건을 재현하는 데 필요한 최소 구성
PROGRAM_DIRS = ["agents", "llm_wrappers", "utils", "quality_diagnosis"]
PROGRAM_FILES = [
    "pyproject.toml", "README.md", "voc.csv", "voc.proto",
    "voc_pb2.py", "voc_pb2_grpc.py", "grpc_server.py", "main.py",
    "run_all.py", "e2e_runner.py", "test_cases.txt", "test_cases_insurance.jsonl",
]
PROGRAM_EXTRA_DIRS = ["data"]

# 비밀정보·용량·재현 불필요 항목
EXCLUDE_PARTS = {
    ".env", ".venv", ".git", "__pycache__", ".pytest_cache", "reports",
    ".tmp", "node_modules", "test_results",
}
EXCLUDE_SUFFIX = {".pyc", ".db", ".log", ".zip"}


def is_excluded(path: Path) -> bool:
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIX:
        return True
    return path.name.startswith(".env")


def add_tree(archive: zipfile.ZipFile, root: Path, base: Path) -> int:
    count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or is_excluded(path.relative_to(base)):
            continue
        archive.write(path, path.relative_to(base).as_posix())
        count += 1
    return count


def build_evidence_zip() -> Path:
    target = UPLOAD / "qa_evidence.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EVIDENCE.iterdir()):
            if path.is_file():
                archive.write(path, f"qa_evidence/{path.name}")
    return target


def build_program_zip() -> Path:
    target = UPLOAD / "voc_qa_program.zip"
    total = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in PROGRAM_DIRS + PROGRAM_EXTRA_DIRS:
            directory = PROJECT_ROOT / name
            if directory.is_dir():
                total += add_tree(archive, directory, PROJECT_ROOT)
        for name in PROGRAM_FILES:
            path = PROJECT_ROOT / name
            if path.is_file():
                archive.write(path, name)
                total += 1
    print(f"  프로그램 파일 {total}개 포함")
    return target


def verify_no_secrets(target: Path) -> None:
    """업로드 전 비밀정보 파일이 섞이지 않았는지 확인합니다."""
    with zipfile.ZipFile(target) as archive:
        leaked = [n for n in archive.namelist()
                  if ".env" in n or n.endswith(".pem") or "credentials" in n.lower()]
    if leaked:
        raise SystemExit(f"[중단] 비밀정보 의심 파일 포함: {leaked}")


def main() -> None:
    if not EVIDENCE.is_dir():
        raise SystemExit("증적 폴더가 없습니다. scripts/build_aws_evidence.py 를 먼저 실행하세요.")
    UPLOAD.mkdir(parents=True, exist_ok=True)
    for target in (build_evidence_zip(), build_program_zip()):
        verify_no_secrets(target)
        print(f"{target.name:24} {target.stat().st_size:>10,} byte  (비밀정보 검사 통과)")
    print("\nCloudShell → Actions → Upload file 로 위 2개 ZIP을 올리세요.")


if __name__ == "__main__":
    main()
