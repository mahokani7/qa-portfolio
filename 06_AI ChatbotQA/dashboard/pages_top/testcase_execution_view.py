import streamlit as st
from datetime import datetime
import traceback

from core.paths import TESTCASE_RUNS_DIR
from core.storage import save_json_file, save_testcase_history
from components.report_visuals import render_report_visual_summary, summarize_pipeline_outputs
from services.dashboard_snapshot import build_dashboard_snapshot, save_dashboard_snapshot
from services.pipeline_runner import copy_run_input_artifacts, run_rule_pipeline_for_cases
from testcase.helpers import build_upload_table_rows, extract_test_cases_from_uploads


def write_execution_log(log_path, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")

def render_testcase_execution_page():
    st.markdown(
        """
        <div class="section-card">
            <p class="section-desc">업로드된 테스트케이스 파일 중 실행 대상을 선택하고 테스트를 수행합니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.testcase_uploads:
        st.warning("실행할 테스트케이스가 없습니다. 먼저 테스트케이스 파일을 업로드해 주세요.")
        return

    st.markdown("#### 실행 대상 선택")
    target_list = build_upload_table_rows(include_selection=True)
    edited_targets = st.data_editor(
        target_list.drop(columns=["_id"]),
        key="testcase_execution_target_table",
        hide_index=True,
        use_container_width=True,
        disabled=["NO", "파일명", "형식", "테스트케이스 수", "컬럼 수", "업로드일시", "상태"],
        column_config={
            "선택": st.column_config.CheckboxColumn("선택", help="실행할 테스트케이스를 선택하세요."),
            "NO": st.column_config.NumberColumn("NO", width="small"),
            "파일명": st.column_config.TextColumn("파일명", width="large"),
            "형식": st.column_config.TextColumn("형식", width="small"),
            "테스트케이스 수": st.column_config.NumberColumn("테스트케이스 수", width="medium"),
            "컬럼 수": st.column_config.NumberColumn("컬럼 수", width="small"),
            "업로드일시": st.column_config.TextColumn("업로드일시", width="medium"),
            "상태": st.column_config.TextColumn("상태", width="small"),
        },
    )

    selected_ids = [
        target_list.iloc[index]["_id"]
        for index, selected in enumerate(edited_targets["선택"].tolist())
        if selected
    ]
    selected_items = [
        item for item in st.session_state.testcase_uploads if item["id"] in selected_ids
    ]

    selected_case_count = sum(item["row_count"] for item in selected_items)
    executable_cases = extract_test_cases_from_uploads(selected_items)
    summary_cols = st.columns(3)
    summary_cols[0].metric("선택 파일", f"{len(selected_items)}개")
    summary_cols[1].metric("실행 테스트케이스", f"{len(executable_cases)}건")
    summary_cols[2].metric("실행 방식", "규칙/API 병행 평가")

    run_clicked = st.button(
        "선택 테스트 실행",
        type="primary",
        use_container_width=False,
        disabled=not selected_items,
    )

    if run_clicked:
        if not executable_cases:
            st.error("선택한 파일에서 user_question 또는 질문 컬럼을 가진 테스트케이스를 찾을 수 없습니다.")
            return

        started_at = datetime.now()
        execution_id = f"RUN-{started_at.strftime('%Y%m%d%H%M%S')}"
        run_dir = TESTCASE_RUNS_DIR / execution_id
        reports_dir = run_dir / "reports"
        inputs_dir = run_dir / "inputs"
        log_path = run_dir / "execution.log"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        write_execution_log(log_path, f"테스트 실행 시작 - execution_id={execution_id}")
        write_execution_log(log_path, f"선택 파일 수={len(selected_items)}, 실행 테스트케이스 수={len(executable_cases)}")
        for item in selected_items:
            write_execution_log(log_path, f"선택 파일 - {item.get('filename', '-')}, upload_id={item.get('id', '-')}")
        save_json_file(inputs_dir / "test_cases.json", executable_cases)
        selected_upload_manifest = copy_run_input_artifacts(selected_items, run_dir)
        write_execution_log(log_path, f"입력 아티팩트 저장 완료 - inputs_dir={inputs_dir}")

        progress_bar = st.progress(0, text="테스트 실행 준비 중...")
        status_area = st.empty()

        def update_progress(case_index, total_cases, case_id, step_name):
            step_ratio = (case_index - 1) / max(total_cases, 1)
            progress = min(step_ratio + (1 / max(total_cases, 1)) * 0.5, 0.98)
            progress_bar.progress(
                progress,
                text=f"{case_id} 실행 중... ({case_index}/{total_cases})",
            )
            status_area.info(f"현재 단계: {step_name}")
            write_execution_log(log_path, f"{case_id} - {step_name} ({case_index}/{total_cases})")

        try:
            run_result = run_rule_pipeline_for_cases(
                executable_cases,
                update_progress,
                report_output_dir=reports_dir,
                log_callback=lambda message: write_execution_log(log_path, message),
            )
        except Exception as exc:
            write_execution_log(log_path, f"테스트 실행 실패 - {exc}")
            write_execution_log(log_path, traceback.format_exc())
            progress_bar.progress(1.0, text="테스트 실행 실패")
            status_area.error(f"테스트 실행 중 오류가 발생했습니다: {exc}")
            return

        pipeline_outputs = run_result["pipeline_outputs"]
        summary = summarize_pipeline_outputs(pipeline_outputs)
        ended_at = datetime.now()
        duration_seconds = round((ended_at - started_at).total_seconds(), 2)
        passed_count = min(summary["rule_passed_count"], summary["api_passed_count"])
        failed_count = summary["failed_count"]
        write_execution_log(
            log_path,
            f"테스트 실행 완료 - duration_seconds={duration_seconds}, "
            f"total={summary['total_count']}, rule_passed={summary['rule_passed_count']}, "
            f"api_passed={summary['api_passed_count']}, failed={failed_count}",
        )
        dashboard_snapshot = build_dashboard_snapshot(
            pipeline_outputs,
            execution_id,
            started_at=started_at,
            ended_at=ended_at,
            reports_dir=reports_dir,
        )
        dashboard_snapshot_path = save_dashboard_snapshot(run_dir, dashboard_snapshot)
        run_manifest = {
            "id": execution_id,
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "ended_at": ended_at.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": duration_seconds,
            "selected_uploads": selected_upload_manifest,
            "test_case_count": summary["total_count"],
            "reports": run_result["reports"],
            "dashboard_snapshot": dashboard_snapshot_path,
            "log": str(log_path),
            "rag_off_results": run_result.get("rag_off_results", []),
        }
        save_json_file(run_dir / "run_manifest.json", run_manifest)
        write_execution_log(log_path, f"실행 매니페스트 저장 완료 - {run_dir / 'run_manifest.json'}")

        st.session_state.testcase_execution_history.insert(
            0,
            {
                "id": execution_id,
                "executed_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
                "target_files": ", ".join(item["filename"] for item in selected_items),
                "file_count": len(selected_items),
                "total_count": summary["total_count"],
                "passed_count": passed_count,
                "failed_count": failed_count,
                "duration_seconds": duration_seconds,
                "status": "완료",
                "run_dir": str(run_dir),
                "detail": {
                    "rule_passed_count": summary["rule_passed_count"],
                    "api_passed_count": summary["api_passed_count"],
                    "matched_count": summary["matched_count"],
                    "file_results": summary["file_results"],
                    "pipeline_outputs": pipeline_outputs,
                    "reports": run_result["reports"],
                    "dashboard_snapshot": dashboard_snapshot_path,
                    "log": str(log_path),
                    "rag_off_results": run_result.get("rag_off_results", []),
                    "inputs": {
                        "test_cases": str(inputs_dir / "test_cases.json"),
                        "selected_uploads": str(inputs_dir / "selected_uploads.json"),
                    },
                },
            },
        )
        save_testcase_history()

        progress_bar.progress(1.0, text="테스트 실행 완료")
        status_area.success(
            f"테스트 실행이 완료되었습니다. 총 {summary['total_count']}건 / "
            f"규칙기반 PASS {summary['rule_passed_count']}건, API기반 PASS {summary['api_passed_count']}건"
        )


