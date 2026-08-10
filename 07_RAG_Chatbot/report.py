from pathlib import Path
from datetime import datetime


def save_markdown_report(final_report: dict, output_path: str):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    results = final_report.get("results", [])

    total_count = len(results)
    pass_count = sum(
        1 for item in results
        if item.get("evaluation", {}).get("overall_pass") is True
    )
    fail_count = total_count - pass_count

    lines = []

    lines.append("# RAG 챗봇 자동 평가 보고서")
    lines.append("")
    lines.append(f"- 생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 전체 테스트: {total_count}건")
    lines.append(f"- 통과: {pass_count}건")
    lines.append(f"- 실패: {fail_count}건")
    lines.append("")

    lines.append("## 평가 결과 요약")
    lines.append("")
    lines.append("| TC ID | 사용자 질문 | 정확성 | 근거성 | 환각 | 최종 판정 |")
    lines.append("|---|---|---:|---:|---|---|")

    for item in results:
        evaluation = item.get("evaluation", {})

        case_id = item.get("case_id", "-")
        question = item.get("user_question", "-").replace("\n", " ")
        accuracy = evaluation.get("accuracy_score", "-")
        grounding = evaluation.get("grounding_score", "-")
        hallucination = evaluation.get("hallucination", "-")
        overall_pass = evaluation.get("overall_pass", "-")

        result_text = "PASS" if overall_pass is True else "FAIL"

        lines.append(
            f"| {case_id} | {question} | {accuracy} | "
            f"{grounding} | {hallucination} | {result_text} |"
        )

    lines.append("")
    lines.append("## 상세 평가 결과")
    lines.append("")

    for item in results:
        evaluation = item.get("evaluation", {})

        lines.append(f"### {item.get('case_id', '-')}")
        lines.append("")
        lines.append(f"**사용자 질문**: {item.get('user_question', '-')}")
        lines.append("")
        lines.append(f"**기대 답변**: {item.get('expected_answer', '-')}")
        lines.append("")
        lines.append(f"**AI 답변**: {item.get('ai_answer', '-')}")
        lines.append("")
        lines.append(
            f"**검색 문서**: {', '.join(item.get('retrieved_sources', []))}"
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
        lines.append(f"**최종 판정**: {evaluation.get('overall_pass', '-')}")
        lines.append("")
        lines.append(f"**평가 의견**: {evaluation.get('reason', '-')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")