# 자동 평가 실행 파일 만들기

import json
from pathlib import Path
from datetime import datetime

from rag_service import answer_question
from evaluator_agent import get_evaluation_from_openai

BASE_DIR = Path(__file__).resolve().parent
TEST_CASE_PATH = BASE_DIR / "test_cases.json"
REPORTS_DIR = BASE_DIR / "reports"


def load_test_cases():
    return json.loads(
        TEST_CASE_PATH.read_text(
            encoding="utf-8"
        )
    )
def save_markdown_report(report: dict, output_path: Path):
    summary = report["summary"]
    results = report["results"]

    lines = []

    lines.append("# RAG 챗봇 자동 평가 보고서")
    lines.append("")

    lines.append("## 1. 평가 요약")
    lines.append("")
    lines.append(f"- 생성 일시: {report['created_at']}")
    lines.append(f"- 전체 테스트: {summary['total_count']}건")
    lines.append(f"- 통과: {summary['pass_count']}건")
    lines.append(f"- 실패: {summary['fail_count']}건")
    lines.append(f"- 통과율: {summary['pass_rate']}%")
    lines.append(f"- 평균 정확성 점수: {summary['average_accuracy_score']}")
    lines.append(f"- 평균 근거성 점수: {summary['average_grounding_score']}")
    lines.append(f"- 환각 의심 건수: {summary['hallucination_count']}건")
    lines.append("")

    lines.append("## 2. 평가 결과 요약")
    lines.append("")
    lines.append("| TC ID | 질문 | 정확성 | 근거성 | 환각 | 판정 |")
    lines.append("|---|---|---:|---:|---|---|")

    for item in results:
        evaluation = item["evaluation"]

        case_id = item["case_id"]
        question = item["user_question"].replace("\n", " ")
        accuracy = evaluation.get("accuracy_score", "-")
        grounding = evaluation.get("grounding_score", "-")
        hallucination = evaluation.get("hallucination", "-")

        overall_pass = evaluation.get("overall_pass", False)
        result = "PASS" if overall_pass else "FAIL"

        lines.append(
            f"| {case_id} | {question} | {accuracy} | "
            f"{grounding} | {hallucination} | {result} |"
        )

    lines.append("")
    lines.append("## 3. 테스트 케이스별 상세 결과")
    lines.append("")

    for item in results:
        evaluation = item["evaluation"]

        overall_pass = evaluation.get("overall_pass", False)
        result = "PASS" if overall_pass else "FAIL"

        lines.append(f"### {item['case_id']} - {result}")
        lines.append("")
        lines.append(f"**분류**: {item['category']}")
        lines.append("")
        lines.append(f"**사용자 질문**: {item['user_question']}")
        lines.append("")
        lines.append(f"**기대 답변**: {item['expected_answer']}")
        lines.append("")
        lines.append(f"**AI 답변**: {item['ai_answer']}")
        lines.append("")
        lines.append(
            f"**검색 출처**: {', '.join(item.get('retrieved_sources', []))}"
        )
        lines.append("")
        lines.append(f"**정확성 점수**: {evaluation.get('accuracy_score', '-')}")
        lines.append("")
        lines.append(f"**근거성 점수**: {evaluation.get('grounding_score', '-')}")
        lines.append("")
        lines.append(f"**환각 여부**: {evaluation.get('hallucination', '-')}")
        lines.append("")
        lines.append(f"**출처 일치 여부**: {evaluation.get('source_match', '-')}")
        lines.append("")
        lines.append(f"**평가 의견**: {evaluation.get('reason', '-')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

def run_pipeline():
    REPORTS_DIR.mkdir(exist_ok=True)

    test_cases = load_test_cases()
    final_results = []

    print("RAG 챗봇 품질평가를 시작합니다.")

    for test_case in test_cases:
        case_id = test_case["case_id"]
        question = test_case["user_question"]

        print(f"\n[{case_id}] 평가 중")

        rag_result = answer_question(question)

        evaluation = get_evaluation_from_openai(
            user_question=question,
            ai_answer=rag_result["answer"],
            expected_answer=test_case.get("expected_answer", ""),
            expected_source=test_case.get("expected_source", ""),
            retrieved_sources=rag_result["sources"],
            retrieved_contexts=rag_result["contexts"]
        )

        record = {
            "case_id": case_id,
            "category": test_case["category"],
            "user_question": question,
            "expected_answer": test_case.get("expected_answer", ""),
            "expected_source": test_case.get("expected_source", ""),
            "ai_answer": rag_result["answer"],
            "retrieved_sources": rag_result["sources"],
            "evaluation": evaluation
        }

        final_results.append(record)

        print("AI 답변:", rag_result["answer"])
        print("평가 결과:", evaluation)

    total_count = len(final_results)

    pass_count = sum(
        1
        for item in final_results
        if item["evaluation"].get("overall_pass") is True
    )

    fail_count = total_count - pass_count

    avg_accuracy = round(
        sum(
            item["evaluation"].get("accuracy_score", 0)
            for item in final_results
        ) / total_count,
        2
    )

    avg_grounding = round(
        sum(
            item["evaluation"].get("grounding_score", 0)
            for item in final_results
        ) / total_count,
        2
    )

    hallucination_count = sum(
        1
        for item in final_results
        if item["evaluation"].get("hallucination") is True
    )

    report = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_count": total_count,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pass_rate": round(pass_count / total_count * 100, 2),
            "average_accuracy_score": avg_accuracy,
            "average_grounding_score": avg_grounding,
            "hallucination_count": hallucination_count
        },
        "results": final_results
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_path = REPORTS_DIR / f"rag_evaluation_report_{timestamp}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    markdown_report_path = REPORTS_DIR / f"rag_evaluation_report_{timestamp}.md"
    save_markdown_report(report, markdown_report_path)

    print("\n평가 완료")
    print(f"통과: {pass_count}건")
    print(f"실패: {fail_count}건")
    print(f"환각 의심: {hallucination_count}건")
    print(f"보고서 저장 위치: {report_path}")
    print(f"Markdown 보고서 저장 위치: {markdown_report_path}")


if __name__ == "__main__":
    run_pipeline()