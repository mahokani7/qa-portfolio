
import json
from pathlib import Path
import pandas as pd
import streamlit as st

from rag_service import (
    save_uploaded_files,
    rebuild_vector_db,
    answer_question,
    UPLOADS_DIR,
    DOCUMENTS_DIR
)

st.set_page_config(
    page_title="RAG 문서 챗봇",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent


def get_document_files():
    files = []

    for target_dir in [DOCUMENTS_DIR, UPLOADS_DIR]:
        if target_dir.exists():
            files.extend(
                [
                    file_path
                    for file_path in target_dir.glob("*")
                    if file_path.suffix.lower() in [".pdf", ".txt", ".md", ".docx", ".xlsx", ".xls"]
                ]
            )

    return files


if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_result" not in st.session_state:
    st.session_state.last_result = None


with st.sidebar:
    st.title("📚 RAG 관리자")
    st.caption("문서를 등록하고 벡터DB를 관리합니다.")

    st.divider()

    st.subheader("1. 문서 업로드")

    uploaded_files = st.file_uploader(
        "파일 선택 (PDF · TXT · MD · DOCX · XLSX · XLS)",
        type=["pdf", "txt", "md", "docx", "xlsx", "xls"],
        accept_multiple_files=True,
        help="업로드 후 반드시 벡터DB를 다시 만들어야 챗봇이 문서를 검색할 수 있습니다."
    )

    if uploaded_files:
        if st.button("📥 업로드 문서 저장", use_container_width=True):
            saved_files = save_uploaded_files(uploaded_files)

            st.success(f"{len(saved_files)}개 파일을 저장했습니다.")

            for file_name in saved_files:
                st.caption(f"• {file_name}")

    st.divider()

    st.subheader("2. 벡터DB 생성")

    if st.button("🔄 문서 분석 및 DB 생성", use_container_width=True):
        try:
            with st.spinner("문서를 분할하고 임베딩을 생성하고 있습니다..."):
                result = rebuild_vector_db()

            st.success("벡터DB 생성이 완료되었습니다.")
            st.info(
                f"원본 문서: {result['original_document_count']}개\n\n"
                f"문서 조각: {result['chunk_count']}개"
            )

        except Exception as error:
            st.error(f"벡터DB 생성 오류: {error}")

    st.divider()

    st.subheader("3. 대화 관리")

    if st.button("🗑️ 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_result = None
        st.rerun()

    st.divider()

    st.caption("지원 형식: PDF · TXT · MD · DOCX · XLSX · XLS")
    st.caption("업로드 후 DB 재생성이 필요합니다.")


document_files = get_document_files()

st.title("📚 문서 기반 RAG 챗봇")
st.caption("업로드한 문서를 검색하여 근거 중심으로 답변합니다.")

metric_col1, metric_col2, metric_col3 = st.columns(3)

with metric_col1:
    st.metric(
        label="등록 문서 수",
        value=f"{len(document_files)}개"
    )

with metric_col2:
    st.metric(
        label="대화 수",
        value=f"{len(st.session_state.messages) // 2}회"
    )

with metric_col3:
    search_count = 0

    if st.session_state.last_result:
        search_count = len(
            st.session_state.last_result.get("sources", [])
        )

    st.metric(
        label="최근 검색 문서",
        value=f"{search_count}개"
    )

st.divider()

tab_chat, tab_documents, tab_quality = st.tabs(
    [
        "💬 문서 챗봇",
        "📂 문서 관리",
        "🧪 품질평가 안내"
    ]
)

with tab_chat:
    st.info(
        "질문 예시: "
        "“수료하려면 출석률이 얼마나 되어야 하나요?” "
        "또는 "
        "“비전공자도 수강할 수 있나요?”"
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message.get("sources"):
                st.caption(
                    f"참고 문서: {', '.join(message['sources'])}"
                )

    question = st.chat_input(
        "업로드한 문서에 대해 질문해 보세요."
    )

    if question:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": question
            }
        )

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("관련 문서를 검색하고 답변을 만들고 있습니다..."):
                try:
                    result = answer_question(question)

                    answer = result["answer"]
                    sources = result["sources"]
                    contexts = result["contexts"]

                    st.markdown(answer)

                    if sources:
                        st.caption(
                            f"참고 문서: {', '.join(sources)}"
                        )

                    with st.expander("🔎 검색 근거 보기"):
                        if contexts:
                            for index, item in enumerate(contexts, start=1):
                                st.markdown(
                                    f"### {index}. {item['source']}"
                                )
                                st.write(item["content"])
                                st.divider()
                        else:
                            st.warning("검색된 근거 문서가 없습니다.")

                    st.session_state.last_result = result

                except Exception as error:
                    answer = f"오류가 발생했습니다: {error}"
                    sources = []

                    st.error(answer)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "sources": sources
            }
        )

with tab_documents:
    st.subheader("등록 문서 목록")

    if document_files:
        for index, file_path in enumerate(document_files, start=1):
            col1, col2, col3 = st.columns([1, 5, 2])

            with col1:
                st.write(index)

            with col2:
                st.write(f"📄 {file_path.name}")

            with col3:
                size_kb = round(file_path.stat().st_size / 1024, 1)
                st.caption(f"{size_kb} KB")

    else:
        st.warning("등록된 문서가 없습니다.")
        st.caption("왼쪽 메뉴에서 PDF, TXT, MD 파일을 업로드하세요.")

    st.divider()

    st.subheader("문서 폴더 위치")

    st.code(str(DOCUMENTS_DIR))
    st.code(str(UPLOADS_DIR))

with tab_quality:
    st.subheader("RAG 품질평가 체크 항목")

    quality_data = [
        {"항목": "검색 정확성", "점검 내용": "질문과 관련 있는 문서를 검색했는가"},
        {"항목": "답변 정확성", "점검 내용": "문서 내용과 일치하는 답변인가"},
        {"항목": "근거성",     "점검 내용": "검색된 문서에 근거하여 답변했는가"},
        {"항목": "출처 일치",  "점검 내용": "답변에 참고 문서가 표시되는가"},
        {"항목": "환각 방지",  "점검 내용": "문서에 없는 숫자·일정·이름을 만들지 않는가"},
    ]
    st.table(quality_data)

    st.divider()

    REPORTS_DIR = BASE_DIR / "reports"
    REPORTS_DIR.mkdir(exist_ok=True)

    st.subheader("자동 품질평가 실행")

    if st.button("🧪 자동 평가 실행", use_container_width=True):
        with st.spinner("테스트케이스를 평가하고 있습니다. 잠시 기다려 주세요..."):
            try:
                from run_evaluation import run_pipeline
                run_pipeline()
                st.success("평가가 완료되었습니다.")
                st.rerun()
            except Exception as eval_error:
                st.error(f"평가 오류: {eval_error}")

    st.divider()

    report_files = sorted(
        f for f in REPORTS_DIR.glob("rag_evaluation_report_2*.json")
        if "latest" not in f.name
    )

    if not report_files:
        st.info("아직 평가 결과가 없습니다. 위 버튼을 눌러 평가를 실행하세요.")
    else:
        # ── 누적 이력 테이블 & 차트 ──────────────────────────────
        st.subheader(f"📈 평가 이력 추이  ({len(report_files)}회)")

        history_rows = []
        for f in report_files:
            r = json.loads(f.read_text(encoding="utf-8"))
            s = r["summary"]
            history_rows.append({
                "일시": r["created_at"],
                "통과율(%)": s["pass_rate"],
                "평균 정확성": s["average_accuracy_score"],
                "평균 근거성": s["average_grounding_score"],
                "통과": s["pass_count"],
                "실패": s["fail_count"],
                "환각 의심": s["hallucination_count"],
            })

        history_df = pd.DataFrame(history_rows).set_index("일시")

        st.dataframe(history_df, use_container_width=True)

        st.line_chart(
            history_df[["통과율(%)", "평균 정확성", "평균 근거성"]],
            use_container_width=True,
        )

        st.divider()

        # ── 개별 이력 상세 보기 ────────────────────────────────────
        st.subheader("🔍 개별 결과 상세 보기")

        file_labels = {
            f.name: f.name.replace("rag_evaluation_report_", "").replace(".json", "").replace("_", " ")
            for f in reversed(report_files)
        }
        selected_name = st.selectbox(
            "평가 이력 선택 (최신순)",
            options=[f.name for f in reversed(report_files)],
            format_func=lambda n: f"🗂 {file_labels[n]}",
        )

        report = json.loads((REPORTS_DIR / selected_name).read_text(encoding="utf-8"))
        summary = report["summary"]
        results = report["results"]

        st.caption(f"생성 일시: {report['created_at']}")

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("전체 테스트", f"{summary['total_count']}건")
        kpi2.metric("통과", f"{summary['pass_count']}건")
        kpi3.metric("실패", f"{summary['fail_count']}건")
        kpi4.metric("통과율", f"{summary['pass_rate']}%")

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("평균 정확성", summary["average_accuracy_score"])
        col_b.metric("평균 근거성", summary["average_grounding_score"])
        col_c.metric("환각 의심", f"{summary['hallucination_count']}건")

        st.divider()
        st.subheader("테스트케이스별 결과")

        for item in results:
            ev = item["evaluation"]
            passed = ev.get("overall_pass", False)
            label = "✅ PASS" if passed else "❌ FAIL"
            final = ev.get("final_score", "-")

            with st.expander(f"{item['case_id']} {label}  —  {item['user_question']}"):
                st.markdown(f"**분류**: {item['category']}")
                st.markdown(f"**AI 답변**: {item['ai_answer']}")
                st.markdown(f"**검색 출처**: {', '.join(item.get('retrieved_sources', []))}")

                scores = ev.get("evaluation_scores", {})
                if scores:
                    score_cols = st.columns(len(scores))
                    for col, (k, v) in zip(score_cols, scores.items()):
                        col.metric(k, f"{v}점")

                st.metric("최종 점수", final)

                if ev.get("reason"):
                    st.caption(f"평가 근거: {ev['reason'][:300]}")






# import streamlit as st

# from rag_service import (
#     save_uploaded_files,
#     rebuild_vector_db,
#     answer_question,
#     UPLOADS_DIR,
#     DOCUMENTS_DIR
# )

# st.set_page_config(
#     page_title="RAG 문서 챗봇",
#     page_icon="📚",
#     layout="wide"
# )

# st.title("📚 PDF 기반 RAG 문서 챗봇")
# st.caption("PDF, TXT, MD 파일을 업로드하고 문서 기반 질문을 할 수 있습니다.")

# if "messages" not in st.session_state:
#     st.session_state.messages = []


# with st.sidebar:
#     st.header("문서 관리")

#     uploaded_files = st.file_uploader(
#         "문서 업로드",
#         type=["pdf", "txt", "md"],
#         accept_multiple_files=True
#     )

#     if uploaded_files:
#         if st.button("업로드 문서 저장"):
#             saved_files = save_uploaded_files(uploaded_files)

#             st.success(
#                 f"{len(saved_files)}개 파일이 uploads 폴더에 저장되었습니다."
#             )

#             for file_name in saved_files:
#                 st.write(f"- {file_name}")

#     if st.button("문서 벡터DB 다시 만들기"):
#         try:
#             with st.spinner("문서를 분석하고 벡터DB를 생성 중입니다..."):
#                 result = rebuild_vector_db()

#             st.success("벡터DB 생성이 완료되었습니다.")
#             st.write(f"원본 문서 수: {result['original_document_count']}")
#             st.write(f"문서 조각 수: {result['chunk_count']}")

#         except Exception as error:
#             st.error(f"벡터DB 생성 오류: {error}")

#     st.divider()

#     st.write("기본 문서 폴더")
#     st.code(str(DOCUMENTS_DIR))

#     st.write("업로드 문서 폴더")
#     st.code(str(UPLOADS_DIR))


# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

#         if message.get("sources"):
#             st.caption(
#                 f"참고 문서: {', '.join(message['sources'])}"
#             )


# question = st.chat_input("업로드한 문서에 대해 질문해 보세요.")

# if question:
#     st.session_state.messages.append(
#         {
#             "role": "user",
#             "content": question
#         }
#     )

#     with st.chat_message("user"):
#         st.markdown(question)

#     with st.chat_message("assistant"):
#         with st.spinner("관련 문서를 검색하고 있습니다..."):
#             try:
#                 result = answer_question(question)

#                 answer = result["answer"]
#                 sources = result["sources"]

#                 st.markdown(answer)

#                 if sources:
#                     st.caption(
#                         f"참고 문서: {', '.join(sources)}"
#                     )

#             except Exception as error:
#                 answer = f"오류가 발생했습니다: {error}"
#                 sources = []

#                 st.error(answer)

#     st.session_state.messages.append(
#         {
#             "role": "assistant",
#             "content": answer,
#             "sources": sources
#         }
#     )