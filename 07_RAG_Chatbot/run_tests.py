import json
import logging
from datetime import datetime
from pathlib import Path

from evaluator_agent import get_evaluation_from_openai
from rag_service import answer_question


BASE_DIR = Path(__file__).resolve().parent
TEST_CASE_PATH = BASE_DIR / "test_cases.json"
REPORT_DIR = BASE_DIR / "reports"


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)


def load_test_cases() -> list:
    """test_cases.json 파일을 읽어 테스트 목록을 반환합니다."""

    return json.loads(
        TEST_CASE_PATH.read_text(
            encoding="utf-8"
        )
    )


def save_json_report(results: list, timestamp: str) -> Path:
    """평가 결과를 JSON 파일로 저장합니다."""

    json_path = REPORT_DIR / f"rag_evaluation_{timestamp}.json"

    json_path.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return json_path


def score_to_text(value) -> str:
    """점수 값이 없을 때도 오류 없이 표시합니다."""

    if value is None:
        return "-"

    return str(value)


def save_markdown_report(results: list, timestamp: str) -> Path:
    """평가 결과를 Markdown 보고서 파일로 저장합니다."""

    md_path = REPORT_DIR / f"rag_evaluation_{timestamp}.md"

    lines = []

    lines.append("# RAG 챗봇 품질평가 보고서")
    lines.append("")
    lines.append(f"- 평가 일시: {timestamp}")
    lines.append(f"- 총 테스트 건수: {len(results)}")
    lines.append("")

    valid_scores = []

    for result in results:
        evaluation = result.get("evaluation", {})
        score = evaluation.get("final_score")

        if isinstance(score, (int, float)):
            valid_scores.append(score)

    if valid_scores:
        average_score = sum(valid_scores) / len(valid_scores)
        lines.append(f"- 평균 최종 점수: **{average_score:.2f} / 5.00**")
    else:
        lines.append("- 평균 최종 점수: 계산 불가")

    lines.append("")
    lines.append("---")
    lines.append("")

    rubric_labels = {
        "understanding": "이해도",
        "accuracy": "정확성",
        "relevance": "관련성",
        "expression": "표현성"
    }

    for result in results:
        case_id = result.get("case_id", "CASE-ID 없음")
        category = result.get("category", "분류 없음")
        question = result.get("user_question", "")
        ai_answer = result.get("ai_answer", "")
        sources = result.get("retrieved_sources", [])
        evaluation = result.get("evaluation", {})
        error = result.get("error")

        lines.append(f"## {case_id} - {category}")
        lines.append("")

        lines.append("### 사용자 질문")
        lines.append(question)
        lines.append("")

        if error:
            lines.append("### 실행 오류")
            lines.append("```text")
            lines.append(error)
            lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        lines.append("### RAG 챗봇 답변")
        lines.append(ai_answer)
        lines.append("")

        lines.append("### 검색 출처")

        if sources:
            for source in sources:
                lines.append(f"- {source}")
        else:
            lines.append("- 검색 출처 없음")

        lines.append("")

        rubric = evaluation.get("rubric_evaluation", {})
        deductions = evaluation.get("deductions", {})
        final_scores = evaluation.get("final_scores", {})

        lines.append("### 1단계: 루브릭 평가")
        lines.append("")
        lines.append("| 평가 항목 | 점수 | 평가 근거 |")
        lines.append("|---|---:|---|")

        for key, label in rubric_labels.items():
            item = rubric.get(key, {})

            lines.append(
                f"| {label} | "
                f"{score_to_text(item.get('score'))} | "
                f"{item.get('reason', '-')} |"
            )

        lines.append("")

        lines.append("### 2단계: 감점 평가")
        lines.append("")
        lines.append("| 평가 항목 | 감점 | 감점 사유 |")
        lines.append("|---|---:|---|")

        for key, label in rubric_labels.items():
            item = deductions.get(key, {})

            lines.append(
                f"| {label} | "
                f"{score_to_text(item.get('deduction'))} | "
                f"{item.get('reason', '-')} |"
            )

        lines.append("")

        lines.append("### 3단계: 최종 항목 점수")
        lines.append("")
        lines.append("| 이해도 | 정확성 | 관련성 | 표현성 |")
        lines.append("|---:|---:|---:|---:|")

        lines.append(
            "| "
            f"{score_to_text(final_scores.get('understanding'))} | "
            f"{score_to_text(final_scores.get('accuracy'))} | "
            f"{score_to_text(final_scores.get('relevance'))} | "
            f"{score_to_text(final_scores.get('expression'))} |"
        )

        lines.append("")

        lines.append(
            f"### 최종 점수: "
            f"**{score_to_text(evaluation.get('final_score'))} / 5.00**"
        )

        lines.append("")

        lines.append("### 종합 의견")
        lines.append(
            evaluation.get(
                "overall_comment",
                "종합 의견이 생성되지 않았습니다."
            )
        )

        lines.append("")
        lines.append("---")
        lines.append("")

    md_path.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    return md_path


def run_pipeline() -> list:
    """RAG 답변 생성 → Judge 평가 → JSON/MD 보고서 저장을 실행합니다."""

    test_cases = load_test_cases()
    final_results = []

    logging.info("RAG 챗봇 품질 평가를 시작합니다.")

    for test_case in test_cases:
        case_id = test_case.get("case_id", "CASE-ID 없음")
        category = test_case.get("category", "분류 없음")
        question = test_case.get("user_question", "")

        logging.info(f"[{case_id}] 평가 중")

        try:
            rag_result = answer_question(question)

            ai_answer = rag_result.get(
                "answer",
                "답변을 생성하지 못했습니다."
            )

            retrieved_sources = rag_result.get(
                "sources",
                []
            )

            evaluation = get_evaluation_from_openai(
                user_question=question,
                ai_answer=ai_answer,
                retrieved_sources=retrieved_sources
            )

            final_results.append(
                {
                    "case_id": case_id,
                    "category": category,
                    "user_question": question,
                    "ai_answer": ai_answer,
                    "retrieved_sources": retrieved_sources,
                    "evaluation": evaluation
                }
            )

        except Exception as error:
            logging.exception(
                f"[{case_id}] 실행 중 오류가 발생했습니다."
            )

            final_results.append(
                {
                    "case_id": case_id,
                    "category": category,
                    "user_question": question,
                    "error": str(error)
                }
            )

    REPORT_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_report_path = save_json_report(
        results=final_results,
        timestamp=timestamp
    )

    markdown_report_path = save_markdown_report(
        results=final_results,
        timestamp=timestamp
    )

    logging.info("모든 평가가 완료되었습니다.")
    logging.info(f"JSON 보고서 저장 위치: {json_report_path}")
    logging.info(f"Markdown 보고서 저장 위치: {markdown_report_path}")

    return final_results


if __name__ == "__main__":
    run_pipeline()