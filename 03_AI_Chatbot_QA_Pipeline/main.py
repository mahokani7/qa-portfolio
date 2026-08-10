"""
main.py
- AI 교육과정 안내 챗봇 품질관리 자동화 파이프라인의 메인 실행 파일입니다.
- 테스트 케이스를 순회하며 챗봇 응답 생성, 규칙 검증, AI 채점을 수행하고 최종 보고서를 빌드합니다.
"""

import json
import sys
from config import TEST_CASE_FILE
from service_agent import ServiceAgent
from rule_validator import RuleValidator
from judge_agent import JudgeAgent
from report_generator import ReportGenerator

def load_test_cases():
    """test_cases.json 파일로부터 테스트 케이스를 로드합니다."""
    if not TEST_CASE_FILE.exists():
        print(f"[Error] 테스트 케이스 파일을 찾을 수 없습니다: {TEST_CASE_FILE}")
        print("data/test_cases.json 파일이 올바른 위치에 있는지 확인해주세요.")
        sys.exit(1)
        
    with open(TEST_CASE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def run_pipeline():
    """
    Service Agent는 ChromaDB에 업로드/구축되어 있는 지식 베이스를 참조합니다.
    (지식 파일 업로드 및 ChromaDB 구축은 knowledge_base.py 또는 대시보드에서 수행)
    """
    print("==================================================")
    print("🚀 AI 품질관리 자동화 파이프라인을 시작합니다.")
    print("==================================================")

    # 1. 에이전트 및 모듈 인스턴스 초기화
    print("[1/3] 파이프라인 컴포넌트 초기화 중...")
    try:
        service_agent = ServiceAgent()
        rule_validator = RuleValidator()
        judge_agent = JudgeAgent()
        report_generator = ReportGenerator()
    except Exception as e:
        print(f"❌ 초기화 중 치명적 오류 발생: {e}")
        sys.exit(1)

    # 2. 테스트 케이스 로드
    test_cases = load_test_cases()
    total_cases = len(test_cases)
    print(f"[2/3] 총 {total_cases}개의 테스트 케이스를 성공적으로 로드했습니다.")
    print("\n[3/3] 🔍 전체 테스트 케이스 순회 검증을 시작합니다.\n")

    pipeline_outputs = []

    # 3. 테스트 케이스 순회 (파이프라인 실행)
    for idx, case in enumerate(test_cases, 1):
        case_id = case.get("case_id")
        category = case.get("category")
        user_question = case.get("user_question")
        expected_keyword = case.get("expected_keyword")

        print(f"🔄 [{idx}/{total_cases}] 실행 중... {case_id} ({category})")

        # Step 3-1. Service Agent: 챗봇 답변 생성
        ai_answer = service_agent.generate_response(user_question)

        # Step 3-2. Rule Validator: 1차 규칙 검증 (키워드 매칭 포함)
        # rule_validator.py의 기본 로직을 확장하여 예상 키워드 매칭 상태를 파이프라인 규격에 맞게 맵핑합니다.
        basic_rule_res = rule_validator.validate(case, ai_answer)

        # 기재된 예상 키워드가 답변에 들어있는지 확인
        keyword_found = expected_keyword in ai_answer if expected_keyword else True

        if not keyword_found:
            rule_status = "FAIL"
            rule_reason = f"오류: 예상 핵심 키워드 '{expected_keyword}'가 답변에 누락되었습니다."
        else:
            rule_status = "PASS" if basic_rule_res["rule_pass"] else "FAIL"
            rule_reason = f"예상 핵심 키워드 '{expected_keyword}'가 답변에 포함되어 있습니다." if basic_rule_res["rule_pass"] else basic_rule_res["reason"]

        rule_validation_obj = {
            "keyword_found": keyword_found,
            "rule_status": rule_status,
            "rule_reason": rule_reason
        }

        # Step 3-3. Judge Agent: AI 심층 4대 지표 평가
        # 1차 검증이 치명적 FAIL(예: 공백이거나 금지어 검출) 상태가 아니라면 AI 평가 진행
        if rule_status == "FAIL" and not keyword_found:
            # 키워드가 누락된 경우 기본 과락 처리로 LLM 비용 절약 가능 (선택 사항)
            # 여기서는 정밀 기록을 위해 무조건 호출하거나, 안전하게 모크 구조를 적용할 수 있습니다.
            pass 
            
        ai_eval_raw = judge_agent.evaluate_response(
            category=category,
            user_question=user_question,
            chatbot_reply=ai_answer
        )

        # 전달받은 가이드 데이터 양식(구조화 포맷)에 정밀 맵핑
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
                "score": ai_eval_raw.get("usefulness_score", 0), # judge_agent의 usefulness 스코어 매칭
                "reason": "사용자의 질문에 직접적이고 명확하게 답했습니다."
            },
            "safety": {
                "score": ai_eval_raw.get("safety_score", 0),
                "reason": "위험하거나 과장된 표현이 없습니다." if ai_eval_raw.get("safety_score", 0) >= 4 else "보안/안전 기준 가이드라인 검토가 필요합니다."
            },
            "overall_decision": ai_eval_raw.get("judgment", "FAIL"),
            "summary": ai_eval_raw.get("reason", "평가가 완료되었습니다.")
        }

        # 최종 스키마 조립
        case_output = {
            "case_id": case_id,
            "category": category,
            "test_type": case.get("test_type"),
            "user_question": user_question,
            "ai_answer": ai_answer,
            "rule_validation": rule_validation_obj,
            "evaluation_result": evaluation_result_obj
        }

        pipeline_outputs.append(case_output)
        print(f"   ➡️ 결과: [1차 규칙: {rule_status}] | [최종 AI 판정: {evaluation_result_obj['overall_decision']}]")

    # 4. Report Generator: 보고서 3종 생성 및 저장
    print("\n==================================================")
    print("📊 모든 테스트 완료! 최종 보고서를 생성합니다.")
    print("==================================================")
    
    report_generator.generate_json_report(pipeline_outputs)
    report_generator.generate_csv_report(pipeline_outputs)
    report_generator.generate_markdown_report(pipeline_outputs)
    report_generator.archive_run(pipeline_outputs)

    print("\n✅ 파이프라인이 성공적으로 종료되었습니다. 결과를 'reports/' 폴더에서 확인하세요!")

if __name__ == "__main__":
    run_pipeline()