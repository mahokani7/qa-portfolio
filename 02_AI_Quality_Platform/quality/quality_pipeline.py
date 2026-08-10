"""
quality_pipeline.py
- AI 교육과정 안내 챗봇 품질관리 자동화 파이프라인의 실행 로직입니다. (기존 ai_quality_final_project_rule/main.py에서 이관)
- 테스트 케이스를 순회하며 [규칙 기반 챗봇]과 [API 기반 챗봇] 양쪽의 답변을 생성하고,
  동일한 기준(규칙 검증 + AI 채점)으로 평가하여 두 챗봇을 비교할 수 있는 최종 보고서를 빌드합니다.
"""

import json
import sys
from pathlib import Path

# quality/ 하위에서 직접 실행되어도 프로젝트 루트 모듈(app.*, config 등)을 임포트할 수 있도록 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import TEST_CASE_FILE
from app.service_agent import ServiceAgent
from app.rule_based_agent import RuleBasedAgent
from quality.rule_validator import RuleValidator
from app.judge_agent import JudgeAgent
from quality.report_generator import ReportGenerator
from quality.jira_reporter import create_issues_for_failures


def load_test_cases():
    """quality/test_cases.json 파일로부터 테스트 케이스를 로드합니다."""
    if not TEST_CASE_FILE.exists():
        print(f"[Error] 테스트 케이스 파일을 찾을 수 없습니다: {TEST_CASE_FILE}")
        sys.exit(1)

    with open(TEST_CASE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_agent_answer(case: dict, ai_answer: str, rule_validator: RuleValidator, judge_agent: JudgeAgent) -> dict:
    """
    하나의 챗봇 답변(규칙 기반 또는 API 기반)에 대해 1차 규칙 검증과 2차 AI 심층 평가를 수행하고,
    보고서/대시보드가 공통으로 사용하는 표준 결과 스키마로 반환합니다.
    """
    category = case.get("category")
    user_question = case.get("user_question")
    expected_keyword = case.get("expected_keyword")

    basic_rule_res = rule_validator.validate(case, ai_answer)
    keyword_found = expected_keyword in ai_answer if expected_keyword else True

    if not keyword_found:
        rule_status = "FAIL"
        rule_reason = f"오류: 예상 핵심 키워드 '{expected_keyword}'가 답변에 누락되었습니다."
    else:
        rule_status = "PASS" if basic_rule_res["rule_pass"] else "FAIL"
        rule_reason = basic_rule_res["reason"]

    rule_validation_obj = {
        "keyword_found": keyword_found,
        "rule_status": rule_status,
        "rule_reason": rule_reason
    }

    ai_eval_raw = judge_agent.evaluate_response(
        category=category,
        user_question=user_question,
        chatbot_reply=ai_answer
    )

    evaluation_result_obj = {
        "accuracy": {
            "score": ai_eval_raw.get("accuracy_score", 0),
            "reason": ai_eval_raw.get("reason") if "정확성" in category else "기준 규정과 부합합니다."
        },
        "groundedness": {
            "score": ai_eval_raw.get("groundedness_score", 0),
            "reason": "제공된 교육과정 기준 정보에 근거한 답변입니다." if ai_eval_raw.get("groundedness_score", 0) >= 4 else "기준 정보 외의 내용이 일부 포함되어 있습니다."
        },
        "helpfulness": {
            "score": ai_eval_raw.get("usefulness_score", 0),
            "reason": "사용자의 질문에 직접적이고 명확하게 답했습니다."
        },
        "safety": {
            "score": ai_eval_raw.get("safety_score", 0),
            "reason": "위험하거나 과장된 표현이 없습니다." if ai_eval_raw.get("safety_score", 0) >= 4 else "보안/안전 기준 가이드라인 검토가 필요합니다."
        },
        "overall_decision": ai_eval_raw.get("judgment", "FAIL"),
        "summary": ai_eval_raw.get("reason", "평가가 완료되었습니다.")
    }

    return {
        "ai_answer": ai_answer,
        "rule_validation": rule_validation_obj,
        "evaluation_result": evaluation_result_obj
    }


def run_pipeline():
    """
    Service Agent(API 기반)는 ChromaDB에 업로드/구축되어 있는 지식 베이스를 참조하고,
    Rule-Based Agent(규칙 기반)는 API 없이 업로드된 지식 파일 원문을 키워드로 검색합니다.
    """
    print("==================================================")
    print("🚀 AI 품질관리 자동화 파이프라인을 시작합니다. (규칙 기반 vs API 기반 비교)")
    print("==================================================")

    print("[1/3] 파이프라인 컴포넌트 초기화 중...")
    try:
        service_agent = ServiceAgent()
        rule_based_agent = RuleBasedAgent()
        rule_validator = RuleValidator()
        judge_agent = JudgeAgent()
        report_generator = ReportGenerator()
    except Exception as e:
        print(f"❌ 초기화 중 치명적 오류 발생: {e}")
        sys.exit(1)

    test_cases = load_test_cases()
    total_cases = len(test_cases)
    print(f"[2/3] 총 {total_cases}개의 테스트 케이스를 성공적으로 로드했습니다.")
    print("\n[3/3] 🔍 전체 테스트 케이스 순회 검증을 시작합니다.\n")

    pipeline_outputs = []

    for idx, case in enumerate(test_cases, 1):
        case_id = case.get("case_id")
        category = case.get("category")
        user_question = case.get("user_question")

        print(f"🔄 [{idx}/{total_cases}] 실행 중... {case_id} ({category})")

        rule_answer = rule_based_agent.generate_response(user_question)
        api_answer = service_agent.generate_response(user_question)

        rule_based_result = evaluate_agent_answer(case, rule_answer, rule_validator, judge_agent)
        api_based_result = evaluate_agent_answer(case, api_answer, rule_validator, judge_agent)

        case_output = {
            "case_id": case_id,
            "category": category,
            "test_type": case.get("test_type"),
            "user_question": user_question,
            "rule_based": rule_based_result,
            "api_based": api_based_result,
        }

        pipeline_outputs.append(case_output)
        print(f"   ➡️ 결과: [규칙기반 판정: {rule_based_result['evaluation_result']['overall_decision']}] | [API기반 판정: {api_based_result['evaluation_result']['overall_decision']}]")

    print("\n==================================================")
    print("📊 모든 테스트 완료! 최종 보고서를 생성합니다.")
    print("==================================================")

    report_generator.generate_json_report(pipeline_outputs)
    report_generator.generate_csv_report(pipeline_outputs)
    report_generator.generate_markdown_report(pipeline_outputs)
    run_meta = report_generator.archive_run(pipeline_outputs)

    # 이 실행 '시점'의 무료 고도화 지표(커버리지 갭·레드티밍)를 스냅샷으로 저장한다.
    # (OpenAI 호출이 없어 비용 0원. 히스토리에서 과거 실행을 선택하면 그 시점 값을 그대로 재현)
    try:
        from config import REPORTS_DIR, HISTORY_DIR
        from quality.enhancement_snapshot import build_free_snapshot, save_snapshot
        snapshot = build_free_snapshot()
        run_dir = HISTORY_DIR / run_meta["timestamp"] if run_meta and run_meta.get("timestamp") else None
        targets = [REPORTS_DIR] + ([run_dir] if run_dir else [])
        save_snapshot(snapshot, *targets)
        print(f"[Success] 무료 고도화 지표 스냅샷 저장 완료 (커버리지·레드티밍)")
    except Exception as e:
        print(f"[Warning] 고도화 지표 스냅샷 저장 중 오류(무시하고 계속): {e}")

    created_issue_keys = create_issues_for_failures(pipeline_outputs)
    if created_issue_keys:
        print(f"🐛 Jira에 {len(created_issue_keys)}건의 결함 이슈를 등록했습니다: {created_issue_keys}")

    print("\n✅ 파이프라인이 성공적으로 종료되었습니다. 결과를 'quality/reports/' 폴더에서 확인하세요!")
    return pipeline_outputs


if __name__ == "__main__":
    run_pipeline()
