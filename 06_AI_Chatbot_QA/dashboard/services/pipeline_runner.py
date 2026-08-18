import importlib
import csv
import json
import shutil
import sys
from pathlib import Path

from core.paths import REPORTS_DIR, RULE_PROJECT_DIR
from core.storage import save_json_file

def import_rule_pipeline_modules():
    if not RULE_PROJECT_DIR.exists():
        raise FileNotFoundError(f"규칙 기반 프로젝트 폴더를 찾을 수 없습니다: {RULE_PROJECT_DIR}")

    rule_project_path = str(RULE_PROJECT_DIR)
    if rule_project_path not in sys.path:
        sys.path.insert(0, rule_project_path)

    modules = {}
    for module_name in (
        "service_agent",
        "rule_validator",
        "judge_agent",
        "report_generator",
    ):
        modules[module_name] = importlib.import_module(module_name)
    return modules


def _metric(score, reason):
    return {"score": score, "reason": reason}


def _decision_from_scores(scores):
    if min(scores) >= 4:
        return "PASS"
    if min(scores) >= 2:
        return "REVIEW"
    return "FAIL"


def _build_rule_based_result(answer, rule_validation):
    passed = bool(rule_validation.get("passed"))
    score = 5 if passed else 1
    reason = rule_validation.get("reason", "")
    return {
        "ai_answer": answer,
        "rule_validation": rule_validation,
        "evaluation_result": {
            "overall_decision": "PASS" if passed else "FAIL",
            "accuracy": _metric(score, reason),
            "groundedness": _metric(score, reason),
            "helpfulness": _metric(score, reason),
            "safety": _metric(5, "규칙 검증 단계에서 안전성 위반은 감지되지 않았습니다."),
            "comment": reason,
        },
    }


def _build_api_based_result(answer, rule_validation, judge_result):
    scores = [
        int(judge_result.get("accuracy", 0) or 0),
        int(judge_result.get("groundedness", 0) or 0),
        int(judge_result.get("helpfulness", 0) or 0),
        int(judge_result.get("safety", 0) or 0),
    ]
    comment = judge_result.get("comment", "")
    return {
        "ai_answer": answer,
        "rule_validation": rule_validation,
        "evaluation_result": {
            "overall_decision": _decision_from_scores(scores),
            "accuracy": _metric(scores[0], comment),
            "groundedness": _metric(scores[1], comment),
            "helpfulness": _metric(scores[2], comment),
            "safety": _metric(scores[3], comment),
            "comment": comment,
        },
    }


def _flatten_for_report(pipeline_outputs):
    rows = []
    for item in pipeline_outputs:
        api_eval = item.get("api_based", {}).get("evaluation_result", {})
        rule_validation = item.get("api_based", {}).get("rule_validation", {})
        rows.append(
            {
                "case_id": item.get("case_id", ""),
                "category": item.get("category", ""),
                "test_type": item.get("test_type", ""),
                "user_question": item.get("user_question", ""),
                "response": item.get("api_based", {}).get("ai_answer", ""),
                "rule_passed": rule_validation.get("passed", False),
                "rule_reason": rule_validation.get("reason", ""),
                "accuracy": api_eval.get("accuracy", {}).get("score", 0),
                "groundedness": api_eval.get("groundedness", {}).get("score", 0),
                "helpfulness": api_eval.get("helpfulness", {}).get("score", 0),
                "safety": api_eval.get("safety", {}).get("score", 0),
                "comment": api_eval.get("comment", ""),
            }
        )
    return rows


def _flatten_agent_for_report(pipeline_outputs, agent_key):
    rows = []
    for item in pipeline_outputs:
        agent = item.get(agent_key, {})
        eval_result = agent.get("evaluation_result", {})
        rule_validation = agent.get("rule_validation", {})
        rows.append(
            {
                "case_id": item.get("case_id", ""),
                "category": item.get("category", ""),
                "test_type": item.get("test_type", ""),
                "user_question": item.get("user_question", ""),
                "response": agent.get("ai_answer", ""),
                "rule_passed": rule_validation.get("passed", False),
                "rule_reason": rule_validation.get("reason", ""),
                "accuracy": eval_result.get("accuracy", {}).get("score", 0),
                "groundedness": eval_result.get("groundedness", {}).get("score", 0),
                "helpfulness": eval_result.get("helpfulness", {}).get("score", 0),
                "safety": eval_result.get("safety", {}).get("score", 0),
                "comment": eval_result.get("comment", ""),
                "overall_decision": eval_result.get("overall_decision", "FAIL"),
            }
        )
    return rows


def _write_json(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return ""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def copy_run_input_artifacts(selected_items, run_dir):
    inputs_dir = run_dir / "inputs"
    uploads_dir = inputs_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    upload_manifest = []
    for item in selected_items:
        copied_source = ""
        source_path = item.get("source_path")
        if source_path and Path(source_path).exists():
            target_dir = uploads_dir / item["id"]
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / Path(source_path).name
            shutil.copy2(source_path, target_path)
            copied_source = str(target_path)

        upload_manifest.append(
            {
                "id": item["id"],
                "filename": item["filename"],
                "file_type": item.get("file_type", ""),
                "row_count": item.get("row_count", 0),
                "uploaded_at": item.get("uploaded_at", ""),
                "source_path": item.get("source_path", ""),
                "run_source_path": copied_source,
            }
        )

    save_json_file(inputs_dir / "selected_uploads.json", upload_manifest)
    return upload_manifest


def run_rule_pipeline_for_cases(
    test_cases,
    progress_callback=None,
    report_output_dir=None,
    log_callback=None,
):
    modules = import_rule_pipeline_modules()
    get_response = modules["service_agent"].get_response
    validate = modules["rule_validator"].validate
    evaluate = modules["judge_agent"].evaluate
    generate_all = modules["report_generator"].generate_all

    pipeline_outputs = []
    total_cases = len(test_cases)
    if log_callback:
        log_callback(f"테스트 파이프라인 시작: 총 {total_cases}건")

    for index, case in enumerate(test_cases, start=1):
        case_id = case.get("case_id", f"TC-{index:03d}")
        category = case.get("category", "")
        user_question = case.get("user_question", "")
        expected_keyword = case.get("expected_keyword", "")
        expected_policy = case.get("expected_policy", "")
        if log_callback:
            log_callback(f"[{case_id}] 시작 - category={category}, question={user_question}")

        if progress_callback:
            progress_callback(index, total_cases, case_id, "챗봇 답변 생성")
        answer = get_response(user_question, use_knowledge_search=True)
        if log_callback:
            log_callback(f"[{case_id}] RAG ON 답변 생성 완료 - answer_length={len(answer or '')}")

        rag_off_answer = get_response(user_question, use_knowledge_search=False)
        if log_callback:
            log_callback(f"[{case_id}] RAG OFF 답변 생성 완료 - answer_length={len(rag_off_answer or '')}")

        if progress_callback:
            progress_callback(index, total_cases, case_id, "규칙 검증")
        rule_validation = validate(answer, expected_keyword)
        rag_off_rule_validation = validate(rag_off_answer, expected_keyword)
        if log_callback:
            log_callback(
                f"[{case_id}] RAG ON 규칙 검증 완료 - passed={rule_validation.get('passed')}, "
                f"reason={rule_validation.get('reason', '')}"
            )
            log_callback(
                f"[{case_id}] RAG OFF 규칙 검증 완료 - passed={rag_off_rule_validation.get('passed')}, "
                f"reason={rag_off_rule_validation.get('reason', '')}"
            )

        if progress_callback:
            progress_callback(index, total_cases, case_id, "AI 평가")
        judge_result = evaluate(user_question, answer, expected_policy)
        rag_off_judge_result = evaluate(user_question, rag_off_answer, expected_policy)
        rule_based_result = _build_rule_based_result(answer, rule_validation)
        api_based_result = _build_api_based_result(answer, rule_validation, judge_result)
        rag_off_result = _build_api_based_result(rag_off_answer, rag_off_rule_validation, rag_off_judge_result)
        if log_callback:
            log_callback(
                f"[{case_id}] RAG ON AI 평가 완료 - "
                f"decision={api_based_result['evaluation_result']['overall_decision']}, "
                f"accuracy={api_based_result['evaluation_result']['accuracy']['score']}, "
                f"groundedness={api_based_result['evaluation_result']['groundedness']['score']}, "
                f"helpfulness={api_based_result['evaluation_result']['helpfulness']['score']}, "
                f"safety={api_based_result['evaluation_result']['safety']['score']}"
            )
            log_callback(
                f"[{case_id}] RAG OFF AI 평가 완료 - "
                f"decision={rag_off_result['evaluation_result']['overall_decision']}, "
                f"accuracy={rag_off_result['evaluation_result']['accuracy']['score']}, "
                f"groundedness={rag_off_result['evaluation_result']['groundedness']['score']}, "
                f"helpfulness={rag_off_result['evaluation_result']['helpfulness']['score']}, "
                f"safety={rag_off_result['evaluation_result']['safety']['score']}"
            )

        pipeline_outputs.append(
            {
                "case_id": case_id,
                "category": category,
                "test_type": case.get("test_type"),
                "user_question": user_question,
                "rule_based": rule_based_result,
                "api_based": api_based_result,
                "rag_off": rag_off_result,
            }
        )
        if log_callback:
            log_callback(f"[{case_id}] 완료")

    output_dir = Path(report_output_dir) if report_output_dir else None
    if log_callback:
        log_callback("결과 보고서 생성 시작")
    report_paths = generate_all(_flatten_for_report(pipeline_outputs), output_dir=output_dir)
    structured_reports = report_paths.get("structured", {})
    rag_off_rows = _flatten_agent_for_report(pipeline_outputs, "rag_off")
    rag_off_json = _write_json(output_dir / "rag_off_evaluation_result.json", rag_off_rows) if output_dir else ""
    rag_off_csv = _write_csv(output_dir / "rag_off_evaluation_result.csv", rag_off_rows) if output_dir else ""
    _write_json(REPORTS_DIR / "rag_off_evaluation_result.json", rag_off_rows)
    _write_csv(REPORTS_DIR / "rag_off_evaluation_result.csv", rag_off_rows)
    if log_callback:
        log_callback(
            "결과 보고서 생성 완료 - "
            f"json={structured_reports.get('json', '')}, "
            f"csv={structured_reports.get('csv', '')}, "
            f"markdown={structured_reports.get('markdown', '')}, "
            f"rag_off_csv={rag_off_csv}"
        )

    return {
        "pipeline_outputs": pipeline_outputs,
        "reports": {
            "json": structured_reports.get("json", ""),
            "csv": structured_reports.get("csv", ""),
            "markdown": structured_reports.get("markdown", ""),
            "rag_off_json": rag_off_json,
            "rag_off_csv": rag_off_csv,
            "archive": "",
        },
        "rag_off_results": rag_off_rows,
    }


