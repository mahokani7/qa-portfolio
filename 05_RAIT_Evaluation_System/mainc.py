import sys
import os

# 모듈 참조 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_loader import load_policy
from src.runner.llm_judge import LLMJudge
from src.engine.calculator import RaiTCalculator
from src.engine.filter import RaiTFilter

def run_pipeline(policy_name="default_pilot", mode="hybrid"):
    print(f"=== RaiT 파일럿 시스템 평가 시작 [정책: {policy_name} / 모드: {mode}] ===")
    
    # 1. 정책 가이드 로드
    policy = load_policy(policy_name)
    
    # 2. LLM 응답 채점 수집 (여기서는 파일럿 Mock 데이터 사용)
    judge = LLMJudge(use_mock=True)
    scores = judge.evaluate_response(prompt="Test Sample", agent_responses=[])
    print(f"-> 수집된 지표 점수: {scores}")

    # 3. 점수 계산
    if mode in ['simple', 'cutoff']:
        final_score = RaiTCalculator.calculate_simple_average(scores)
    else:
        final_score = RaiTCalculator.calculate_weighted_average(scores, policy["weights"])

    # 4. 종합 판정
    result = RaiTFilter.check_pass_fail(
        final_score=final_score,
        target_score=policy["target_score"],
        scores=scores,
        cutoffs=policy["cutoffs"],
        mode=mode
    )
    
    print("\n=== 최종 평가 결과 ===")
    print(f"최종 계산 점수: {result['final_score']} (목표 기준점: {policy['target_score']})")
    print(f"과락 여부 통과: {result['pass_cutoff']} (과락 리스트: {result['cutoff_fails']})")
    print(f"최종 판정 결과: 【 {result['status']} 】")
    
    # CI/CD 자동화를 위한 종료 코드 처리 (Fail 시 프로세스 에러 발생)
    if result['status'] == "Fail":
        print("❌ 품질 기준 미달로 배포를 거부합니다.")
        return False
    else:
        print("🎉 품질 검증 완료. 배포가 가능합니다.")
        return True

if __name__ == "__main__":
    # 고위험 금융 도메인 하이브리드 방식으로 모의 테스트 실행
    success = run_pipeline("high_risk_finance", "hybrid")
    if not success:
        sys.exit(1) # 배포 중단 신호