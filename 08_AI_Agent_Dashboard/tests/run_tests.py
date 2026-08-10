import json
from pathlib import Path

import requests


BASE_URL = "http://127.0.0.1:8001"
TEST_CASE_PATH = Path(__file__).parent / "test_cases.json"
RESULT_PATH = Path(__file__).parent / "test_result.json"


def load_test_cases() -> list:
    return json.loads(
        TEST_CASE_PATH.read_text(encoding="utf-8")
    )


def run_test_case(test_case: dict) -> dict:
    response = requests.get(
        f"{BASE_URL}/ask",
        params={"question": test_case["question"]},
        timeout=15
    )

    response_text = response.text

    status_pass = response.status_code == test_case["expected_status"]
    keyword_pass = test_case["expected_keyword"] in response_text

    return {
        "case_id": test_case["case_id"],
        "category": test_case["category"],
        "question": test_case["question"],
        "expected_status": test_case["expected_status"],
        "actual_status": response.status_code,
        "expected_keyword": test_case["expected_keyword"],
        "status_pass": status_pass,
        "keyword_pass": keyword_pass,
        "final_result": "PASS" if status_pass and keyword_pass else "FAIL"
    }


def run_all_tests() -> list:
    test_cases = load_test_cases()

    results = []

    for test_case in test_cases:
        result = run_test_case(test_case)
        results.append(result)

    RESULT_PATH.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return results


if __name__ == "__main__":
    run_all_tests()