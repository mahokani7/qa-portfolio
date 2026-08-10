"""기존 JSONL 18건과 장애 2건으로 교수님 기준 20건 카탈로그를 생성합니다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUALITY_ROOT = Path(__file__).resolve().parent


def _scenario_type(case_id: str) -> str:
    number = int(case_id.split("-")[-1])
    if number <= 8:
        return "normal"
    if number <= 11:
        return "ambiguous"
    if number <= 14:
        return "compound"
    if number <= 16:
        return "no_data"
    return "typo"


def build_catalog() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    with (ROOT / "test_cases.txt").open(encoding="utf-8") as stream:
        cases = [
            json.loads(line) for line in stream
            if line.strip() and not line.lstrip().startswith("#")
        ]
    for case in cases:
        case["scenario_type"] = _scenario_type(str(case["case_id"]))
    cases.extend([
        {
            "case_id": "TC-19",
            "scenario_type": "fault",
            "question": "Retriever 서버가 중단된 상태에서 결제 VOC를 분석합니다.",
            "fault": "retriever_shutdown",
            "expected_status": "error",
            "expected_error_code": "GRPC_UNAVAILABLE",
            "required_output": ["검색 불가 오류 안내", "실패 상태"],
            "prohibited_output": ["성공으로 표시", "근거 없는 분석 결과"],
        },
        {
            "case_id": "TC-20",
            "scenario_type": "fault",
            "question": "존재하지 않는 VOC CSV 파일로 분석합니다.",
            "fault": "missing_csv",
            "expected_status": "error",
            "expected_error_code": "CSV_NOT_FOUND",
            "required_output": ["CSV 파일 오류 안내", "실패 상태"],
            "prohibited_output": ["성공으로 표시", "근거 없는 분석 결과"],
        },
    ])
    expected_fields = (
        "expected_intent", "expected_keywords", "required_output", "prohibited_output",
        "expected_status", "expected_error_code",
    )
    expected = {
        str(case["case_id"]): {
            key: case[key] for key in expected_fields if key in case
        }
        for case in cases
    }
    return cases, expected


def main() -> None:
    cases, expected = build_catalog()
    (QUALITY_ROOT / "test_cases.json").write_text(
        json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (QUALITY_ROOT / "expected_results.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"20개 카탈로그 생성 완료: 기능 {len(cases) - 2}건 + 장애 2건")


if __name__ == "__main__":
    main()
