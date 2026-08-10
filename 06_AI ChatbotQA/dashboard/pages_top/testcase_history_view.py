import streamlit as st
import pandas as pd

from core.paths import LEGACY_TESTCASE_HISTORY_FILE, TESTCASE_HISTORY_FILE
from core.storage import load_json_file, save_testcase_history
from components.report_visuals import render_agent_visual_summary, show_execution_detail_dialog
from testcase.helpers import build_execution_detail, get_execution_detail

def render_testcase_history_page():
    st.markdown(
        """
        <div class="section-card">
            <p class="section-desc">실행 완료된 테스트 내역을 확인하고 선택한 이력을 삭제할 수 있습니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.testcase_history_flash_message:
        st.success(st.session_state.testcase_history_flash_message)
        st.session_state.testcase_history_flash_message = ""

    if not st.session_state.testcase_execution_history:
        st.info("아직 테스트 수행 이력이 없습니다.")
        return

    history_rows = []
    for index, item in enumerate(st.session_state.testcase_execution_history, start=1):
        history_rows.append(
            {
                "NO": index,
                "실행ID": item["id"],
                "실행일시": item["executed_at"],
                "대상파일": item["target_files"],
                "파일 수": item["file_count"],
                "총 건수": item["total_count"],
                "성공": item["passed_count"],
                "실패": item["failed_count"],
                "소요시간(초)": item["duration_seconds"],
                "상태": item["status"],
                "_id": item["id"],
            }
        )

    history_list = pd.DataFrame(history_rows)
    history_event = st.dataframe(
        history_list.drop(columns=["_id"]),
        key="testcase_history_table",
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "NO": st.column_config.NumberColumn("NO", width="small"),
            "실행ID": st.column_config.TextColumn("실행ID", width="medium"),
            "실행일시": st.column_config.TextColumn("실행일시", width="medium"),
            "대상파일": st.column_config.TextColumn("대상파일", width="large"),
            "파일 수": st.column_config.NumberColumn("파일 수", width="small"),
            "총 건수": st.column_config.NumberColumn("총 건수", width="small"),
            "성공": st.column_config.NumberColumn("성공", width="small"),
            "실패": st.column_config.NumberColumn("실패", width="small"),
            "소요시간(초)": st.column_config.NumberColumn("소요시간(초)", width="small"),
            "상태": st.column_config.TextColumn("상태", width="small"),
        },
    )

    selected_rows = history_event.selection.rows
    selected_history_ids = []
    if selected_rows:
        selected_index = selected_rows[0]
        if 0 <= selected_index < len(history_list):
            selected_history_ids = [history_list.iloc[selected_index]["_id"]]
            selected_item = st.session_state.testcase_execution_history[selected_index]
            if st.session_state.history_detail_open_id != selected_item["id"]:
                st.session_state.history_detail_open_id = selected_item["id"]
                show_execution_detail_dialog(selected_item)
        else:
            st.session_state.history_detail_open_id = None
    else:
        st.session_state.history_detail_open_id = None

    bottom_cols = st.columns([1, 1, 5])
    with bottom_cols[0]:
        if st.button(
            "선택 삭제",
            use_container_width=True,
            disabled=not selected_history_ids,
        ):
            st.session_state.testcase_execution_history = [
                item
                for item in st.session_state.testcase_execution_history
                if item["id"] not in selected_history_ids
            ]
            st.session_state.history_detail_open_id = None
            save_testcase_history()
            st.session_state.testcase_history_flash_message = (
                f"선택한 테스트 수행 이력 {len(selected_history_ids)}건을 삭제했습니다."
            )
            st.rerun()
    with bottom_cols[1]:
        if st.button("전체 삭제", use_container_width=True):
            st.session_state.testcase_execution_history = []
            st.session_state.history_detail_open_id = None
            save_testcase_history()
            st.session_state.testcase_history_flash_message = "테스트 수행 이력을 모두 삭제했습니다."
            st.rerun()

    st.markdown(
        f'<div class="table-summary">총 {len(st.session_state.testcase_execution_history)}건</div>',
        unsafe_allow_html=True,
    )


