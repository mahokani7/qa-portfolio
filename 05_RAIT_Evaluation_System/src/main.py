import sys
import os
import json
import logging

# 모듈 참조 경로 추가
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from src.utils.config_loader import load_policy
from src.runner.llm_judge import LLMJudge
from src.engine.calculator import RaiTCalculator
from src.engine.filter import RaiTFilter


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

logger = logging.getLogger(__name__)


def load_test_cases():
    test_case_path = os.path.join(BASE_DIR, "data", "test_cases.json")

    with open(test_case_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_pipeline(policy_name="default_pilot", mode="hybrid"):
    logger.info(f"=== RaiT 파일럿 시스템 평가 시작 [정책: {policy_name} / 모드: {mode}] ===")

    # 1. 정책 가이드 로드
    policy = load_policy(policy_name)

    # 2. 테스트 케이스 로드
    test_cases = load_test_cases()

    # 3. LLM Judge 준비
    judge = LLMJudge(use_mock=True)

    all_results = []
    has_fail = False

    for case in test_cases:
        case_id = case["case_id"]
        prompt = case["prompt"]
        expected_keywords = case.get("expected_keywords", [])

        logger.info(f"\n--- 테스트 케이스 실행: {case_id} ---")
        logger.info(f"프롬프트: {prompt}")
        logger.info(f"기대 키워드: {expected_keywords}")

        # 4. LLM 응답 채점 수집
        scores = judge.evaluate_response(
            prompt=prompt,
            agent_responses=[],
        )

        logger.info(f"수집된 지표 점수: {scores}")

        # 5. 점수 계산
        if mode in ["simple", "cutoff"]:
            final_score = RaiTCalculator.calculate_simple_average(scores)
        else:
            final_score = RaiTCalculator.calculate_weighted_average(
                scores,
                policy["weights"]
            )

        # 6. 종합 판정
        result = RaiTFilter.check_pass_fail(
            final_score=final_score,
            target_score=policy["target_score"],
            scores=scores,
            cutoffs=policy["cutoffs"],
            mode=mode
        )

        result_summary = {
            "case_id": case_id,
            "prompt": prompt,
            "expected_keywords": expected_keywords,
            "scores": scores,
            "final_score": result["final_score"],
            "pass_cutoff": result["pass_cutoff"],
            "cutoff_fails": result["cutoff_fails"],
            "status": result["status"]
        }

        all_results.append(result_summary)

        logger.info(f"최종 계산 점수: {result['final_score']} / 목표 기준점: {policy['target_score']}")
        logger.info(f"과락 통과 여부: {result['pass_cutoff']}")
        logger.info(f"과락 실패 지표: {result['cutoff_fails']}")
        logger.info(f"최종 판정 결과: {result['status']}")

        if result["status"] == "Fail":
            has_fail = True

    logger.info("\n=== 전체 테스트 결과 요약 ===")

    for item in all_results:
        logger.info(
            f"{item['case_id']} | 점수: {item['final_score']} | 판정: {item['status']}"
        )

    if has_fail:
        logger.info("\n❌ 하나 이상의 테스트 케이스가 품질 기준 미달입니다. 배포를 거부합니다.")
        return False

    logger.info("\n🎉 모든 테스트 케이스가 품질 기준을 통과했습니다. 배포가 가능합니다.")
    return True


if __name__ == "__main__":
    success = run_pipeline("high_risk_finance", "hybrid")

    if not success:
        sys.exit(1)