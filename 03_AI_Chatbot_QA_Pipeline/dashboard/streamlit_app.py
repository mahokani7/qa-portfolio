import sys
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
from pathlib import Path

# dashboard/ 하위에서 실행되어도 프로젝트 루트 모듈(config, main 등)을 임포트할 수 있도록 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import KNOWLEDGE_UPLOAD_DIR, TEST_CASE_FILE, REPORTS_DIR
from knowledge_base import (
    add_file_to_chroma,
    list_uploaded_knowledge_files,
    remove_knowledge_file,
    rebuild_chroma_index,
)
from formal_report_generator import (
    generate_docx_report,
    generate_pdf_report,
    METRIC_LABELS,
    METRIC_PASS_SCORE,
    ITEM_PASS_THRESHOLD,
)
from report_generator import list_archived_runs

# 1. 페이지 설정
st.set_page_config(
    page_title="AI Chatbot QA Analysis Dashboard",
    page_icon="📊",
    layout="wide"
)

# 스타일 커스텀 (전문적인 느낌을 위해 UI 개선 + 상단 탭 시인성 강화)
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eef2f6; }
    .report-card { background-color: #ffffff; padding: 25px; border-radius: 15px; border-left: 5px solid #4f46e5; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 2px solid #eef2f6; }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        padding: 0 20px;
        background-color: #ffffff;
        border-radius: 10px 10px 0 0;
        font-size: 16px;
        font-weight: 600;
        color: #64748b;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4f46e5;
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] h1 {
        margin-top: 0rem;
        margin-bottom: 0.2rem;
        padding-top: 0.5rem;
        padding-bottom: 0rem;
    }
    section[data-testid="stSidebar"] hr {
        margin-top: 0.3rem;
        margin-bottom: 0.6rem;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 로드 함수 (히스토리에서 선택한 실행 결과의 CSV를 로드)
@st.cache_data
def load_run_csv(csv_path: str):
    path = Path(csv_path)
    if path.exists():
        return pd.read_csv(path)
    return None

# 3. 사이드바 구성 (지식 베이스/테스트 케이스 관리 전용)
st.sidebar.title("QA Pipeline")
st.sidebar.markdown("---")

# 3-1. 지식 베이스(RAG) 파일 업로드 (다중 파일, 드래그 앤 드롭 지원)
st.sidebar.subheader("📚 지식 베이스(RAG) 파일 업로드")
uploaded_knowledge_files = st.sidebar.file_uploader(
    "기준정보 파일을 이 영역에 끌어다 놓거나 클릭해서 선택하세요 (여러 개 선택 가능)",
    type=["txt", "md", "docx", "pdf"],
    accept_multiple_files=True,
    help="Service Agent가 RAG 검색에 사용할 기준정보 문서입니다. 업로드 즉시 ChromaDB에 추가됩니다.",
)

# 같은 파일이 재실행마다 중복으로 재임베딩되지 않도록 처리 완료된 업로드를 추적
processed_uploads = st.session_state.setdefault("processed_knowledge_uploads", set())
for kf in uploaded_knowledge_files or []:
    upload_key = f"{kf.name}:{kf.size}"
    if upload_key in processed_uploads:
        continue
    save_path = KNOWLEDGE_UPLOAD_DIR / kf.name
    save_path.write_bytes(kf.getvalue())
    try:
        n_chunks = add_file_to_chroma(save_path)
        st.sidebar.success(f"✅ {kf.name} ({n_chunks}개 청크) ChromaDB에 추가 완료")
        processed_uploads.add(upload_key)
    except Exception as e:
        st.sidebar.error(f"❌ {kf.name} 처리 중 오류: {e}")

# 3-2. 업로드된 지식 파일 목록 및 삭제
# 파일이 많아져도 사이드바 전체가 밀려 아래 메뉴가 가려지지 않도록, 목록만 고정 높이의
# 별도 스크롤 영역(container)에 담습니다.
knowledge_files = list_uploaded_knowledge_files()
st.sidebar.caption(f"📂 업로드된 지식 파일 ({len(knowledge_files)}개)")
if knowledge_files:
    deleted_any = False
    file_list_box = st.sidebar.container(height=130)
    for kf_path in knowledge_files:
        col_name, col_del = file_list_box.columns([4, 1])
        col_name.write(f"📄 {kf_path.name}")
        if col_del.button("🗑️", key=f"del_{kf_path.name}", help=f"{kf_path.name} 삭제"):
            remove_knowledge_file(kf_path.name)
            deleted_any = True
    if deleted_any:
        st.session_state["knowledge_needs_rebuild"] = True
        st.rerun()
else:
    st.sidebar.caption("아직 업로드된 지식 파일이 없습니다.")

if st.session_state.get("knowledge_needs_rebuild"):
    st.sidebar.warning("⚠️ 파일이 삭제되었습니다. 재생성 버튼을 눌러 ChromaDB에 반영하세요.")

if st.sidebar.button("🔄 크로마 DB 재생성", use_container_width=True):
    with st.spinner("ChromaDB를 초기화하고 현재 업로드된 파일들로 다시 구축 중입니다..."):
        try:
            result = rebuild_chroma_index()
            st.session_state["knowledge_needs_rebuild"] = False
            if result:
                st.sidebar.success(f"✅ 재생성 완료: {len(result)}개 파일, 총 {sum(result.values())}개 청크")
            else:
                st.sidebar.warning("⚠️ 업로드된 파일이 없어 빈 컬렉션으로 초기화되었습니다.")
        except Exception as e:
            st.sidebar.error(f"❌ 재생성 중 오류: {e}")

st.sidebar.markdown("---")

# 3-3. 테스트 케이스 업로드 (한 번에 1개 파일만)
st.sidebar.subheader("🧪 테스트 케이스 업로드")
uploaded_test_case = st.sidebar.file_uploader(
    "테스트 케이스 JSON 파일을 업로드하세요 (1개만 가능)",
    type=["json"],
    accept_multiple_files=False,
    key="test_case_uploader",
    help="업로드 시 기존 test_cases.json을 대체합니다.",
)

if uploaded_test_case is not None:
    upload_key = f"{uploaded_test_case.name}:{uploaded_test_case.size}"
    if st.session_state.get("processed_test_case_upload") != upload_key:
        try:
            parsed_cases = json.loads(uploaded_test_case.getvalue().decode("utf-8"))
            if not isinstance(parsed_cases, list):
                raise ValueError("테스트 케이스 파일은 케이스 객체의 리스트(JSON 배열)여야 합니다.")
            TEST_CASE_FILE.write_text(
                json.dumps(parsed_cases, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            st.sidebar.success(f"✅ 테스트 케이스 {len(parsed_cases)}건 업로드 완료 (기존 파일 대체됨)")
            st.session_state["processed_test_case_upload"] = upload_key
        except Exception as e:
            st.sidebar.error(f"❌ 테스트 케이스 파일 처리 중 오류: {e}")

if TEST_CASE_FILE.exists():
    st.sidebar.caption(f"현재 테스트 케이스 파일: `{TEST_CASE_FILE.name}`")

if st.sidebar.button("▶️ 파이프라인 재실행", use_container_width=True):
    if not TEST_CASE_FILE.exists():
        st.sidebar.error(f"❌ 테스트 케이스 파일을 찾을 수 없습니다: {TEST_CASE_FILE}")
    else:
        with st.spinner("전체 파이프라인을 실행 중입니다... (수 분 소요될 수 있습니다)"):
            try:
                from main import run_pipeline
                run_pipeline()
                st.cache_data.clear()
                st.sidebar.success("✅ 파이프라인 실행 완료! 대시보드를 새로고침합니다.")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"❌ 파이프라인 실행 중 오류가 발생했습니다: {e}")

st.sidebar.markdown("---")
st.sidebar.caption("© 2024 AI Quality Pipeline Project Dashboard")

# 4. 프로젝트 발표자료 (요구사항정의서 / 업무분장·WBS / WBS 상세)
# 프로젝트 산출물이 아닌 참고 자료이므로, 화면 우측 상단 버튼을 눌러야만 진입할 수 있게 분리합니다.
PRESENTATION_DIR = Path(__file__).resolve().parent / "docs"
PRESENTATION_SLIDES = [
    ("00_program_analysis.html", "① 프로그램 분석 보고서"),
    ("01_requirements.html", "② 요구사항정의서"),
    ("02_roles_wbs.html", "③ 업무분장 및 WBS"),
    ("03_wbs_detail.html", "④ WBS 상세"),
]

header_l, header_r = st.columns([6, 1])
with header_l:
    st.caption("AI 교육과정 안내 챗봇 · QA 자동화 파이프라인")
with header_r:
    if st.button("📑 프로젝트 진행", use_container_width=True, help="요구사항정의서 · 업무분장/WBS 자료 보기"):
        st.session_state["show_presentation"] = not st.session_state.get("show_presentation", False)
        st.session_state.setdefault("presentation_slide", 0)

if st.session_state.get("show_presentation"):
    st.title("📑 프로젝트 진행")

    nav_prev, nav_label, nav_next, nav_close = st.columns([1, 3, 1, 1])
    slide_idx = st.session_state.get("presentation_slide", 0)
    with nav_prev:
        if st.button("◀ 이전", disabled=(slide_idx == 0), use_container_width=True):
            st.session_state["presentation_slide"] = max(0, slide_idx - 1)
            st.rerun()
    with nav_label:
        st.markdown(
            f"<p style='text-align:center; padding-top:8px; font-weight:600;'>"
            f"{slide_idx + 1} / {len(PRESENTATION_SLIDES)} &nbsp;·&nbsp; {PRESENTATION_SLIDES[slide_idx][1]}</p>",
            unsafe_allow_html=True,
        )
    with nav_next:
        if st.button("다음 ▶", disabled=(slide_idx == len(PRESENTATION_SLIDES) - 1), use_container_width=True):
            st.session_state["presentation_slide"] = min(len(PRESENTATION_SLIDES) - 1, slide_idx + 1)
            st.rerun()
    with nav_close:
        if st.button("✖ 닫기", use_container_width=True):
            st.session_state["show_presentation"] = False
            st.rerun()

    slide_file = PRESENTATION_DIR / PRESENTATION_SLIDES[slide_idx][0]
    if slide_file.exists():
        components.html(slide_file.read_text(encoding="utf-8"), height=900, scrolling=True)
    else:
        st.error(f"❌ 발표자료 파일을 찾을 수 없습니다: {slide_file}")

    st.stop()

# 5. 메인 화면 상단 탭 메뉴 (기존 좌측 사이드바 라디오 메뉴를 화면 상단으로 이동)

# 5-1. 테스트 히스토리 선택 — 아래 3개 탭 전체가 이 선택에 따라 달라지는 상위 메뉴입니다.
history_runs = list_archived_runs()
df = None
selected_json_path = REPORTS_DIR / "evaluation_result.json"

if history_runs:
    def _format_run_label(run: dict) -> str:
        if "total" in run and "pass_rate" in run:
            return f"🕒 {run['display_time']} · {run['total']}건 · 합격률 {run['pass_rate']}%"
        return f"🕒 {run['display_time']}"

    selected_idx = st.selectbox(
        "📜 테스트 히스토리 (조회할 실행 결과를 선택하세요)",
        options=range(len(history_runs)),
        format_func=lambda i: _format_run_label(history_runs[i]),
    )
    selected_run = history_runs[selected_idx]
    df = load_run_csv(str(selected_run["csv_path"]))
    selected_json_path = Path(selected_run["json_path"])

if df is None:
    st.error("📊 리포트 파일이 없습니다. 먼저 파이프라인(main.py)을 실행하여 데이터를 생성해주세요.")
else:
    # KPI 지표 계산
    total = len(df)
    pass_n = (df['overall_decision'] == 'PASS').sum()
    pass_rate = (pass_n / total) * 100

    tab_stats, tab_logs, tab_summary = st.tabs(
        ["📊 종합 통계 분석", "🔍 세부 실행 로그", "🏁 품질 검증 최종 결론"]
    )

    # --- 탭 1: 종합 통계 분석 ---
    with tab_stats:
        st.title("📊 품질 지표 통계 분석")

        avg_acc = df['accuracy_score'].mean()
        avg_saf = df['safety_score'].mean()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("최종 합격률", f"{pass_rate:.1f}%", f"{pass_n}/{total}")
        m2.metric("평균 정확성", f"{avg_acc:.2f} / 5.0")
        m3.metric("평균 근거성", f"{df['groundedness_score'].mean():.2f} / 5.0")
        m4.metric("평균 안전성", f"{avg_saf:.2f} / 5.0")

        st.divider()

        col_l, col_r = st.columns(2)
        with col_l:
            st.plotly_chart(px.pie(df, names='overall_decision', title="판정 결과 분포",
                                   color='overall_decision',
                                   color_discrete_map={'PASS':'#10b981', 'REVIEW':'#f59e0b', 'FAIL':'#ef4444'},
                                   hole=0.4), use_container_width=True)
        with col_r:
            cat_chart = df.groupby('category')['accuracy_score'].mean().reset_index()
            st.plotly_chart(px.bar(cat_chart, x='category', y='accuracy_score', title="카테고리별 평균 정확성",
                                   color_discrete_sequence=['#4f46e5']), use_container_width=True)

    # --- 탭 2: 세부 실행 로그 ---
    with tab_logs:
        st.title("🔍 테스트 케이스별 실행 상세")
        st.write("각 테스트 케이스의 질문, 답변 및 AI의 상세 평가 근거를 확인할 수 있습니다.")

        st.dataframe(df[['case_id', 'category', 'overall_decision', 'user_question', 'ai_answer', 'summary']],
                     use_container_width=True)

        st.divider()

        # 케이스별 심층 평가 결과: 1차 규칙 검증 + AI 4대 지표(정확성/근거성/유용성/안전성) 점수·근거를
        # 케이스마다 펼쳐서 확인할 수 있도록 아코디언(expander)으로 표시합니다.
        st.subheader("🧠 케이스별 심층 평가 결과")
        st.caption("케이스를 펼치면 규칙 기반 1차 검증 결과와 AI 평가자(Judge Agent)의 4대 지표별 점수·근거를 확인할 수 있습니다.")

        decision_badge = {"PASS": "🟢 PASS", "REVIEW": "🟡 REVIEW", "FAIL": "🔴 FAIL"}

        for _, row in df.iterrows():
            badge = decision_badge.get(row["overall_decision"], row["overall_decision"])
            with st.expander(f"{row['case_id']} · {row['category']} ({row['test_type']}) — {badge}"):
                st.markdown(f"**사용자 질문:** {row['user_question']}")
                st.markdown(f"**챗봇 답변:** {row['ai_answer']}")

                st.markdown("##### ⚙️ 1차 규칙 기반 검증")
                rule_badge = "🟢 PASS" if row["rule_status"] == "PASS" else "🔴 FAIL"
                st.write(f"{rule_badge} (핵심 키워드 발견 여부: {row['keyword_found']})")
                st.caption(row["rule_reason"])

                st.markdown("##### 🧠 AI 심층 평가 (4대 지표)")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("정확성", f"{row['accuracy_score']}/5")
                m2.metric("근거성", f"{row['groundedness_score']}/5")
                m3.metric("유용성", f"{row['helpfulness_score']}/5")
                m4.metric("안전성", f"{row['safety_score']}/5")

                st.write(f"- **정확성 근거:** {row['accuracy_reason']}")
                st.write(f"- **근거성 근거:** {row['groundedness_reason']}")
                st.write(f"- **유용성 근거:** {row['helpfulness_reason']}")
                st.write(f"- **안전성 근거:** {row['safety_reason']}")

                st.info(f"**종합 판정 요약:** {row['summary']}")

    # --- 탭 3: 품질 검증 최종 결론 ---
    with tab_summary:
        st.title("🏁 품질 검증 최종 결론 (QA Executive Summary)")

        # 데이터 기반 자동 분석 (다운로드 리포트와 동일한 기준: 합격률 85% 이상, 지표 평균 4점 이상)
        avg_scores = df[['accuracy_score', 'groundedness_score', 'helpfulness_score', 'safety_score']].mean()
        weakest_metric_raw = avg_scores.idxmin()
        weakest_metric_key = weakest_metric_raw.replace('_score', '')
        weakest_metric = METRIC_LABELS.get(weakest_metric_key, weakest_metric_key.upper())
        weakest_metric_score = avg_scores[weakest_metric_raw]
        metric_ok = weakest_metric_score >= METRIC_PASS_SCORE

        cat_stats = df.groupby('category')['overall_decision'].apply(lambda x: (x == 'PASS').mean() * 100)
        worst_cat = cat_stats.idxmin()
        worst_cat_rate = cat_stats.min()
        category_ok = worst_cat_rate >= ITEM_PASS_THRESHOLD

        overall_ok = pass_rate >= ITEM_PASS_THRESHOLD
        summary_box = st.success if overall_ok else st.error
        summary_verdict = (
            f"합격 기준({ITEM_PASS_THRESHOLD}% 이상)을 **충족하였습니다**." if overall_ok
            else f"합격 기준({ITEM_PASS_THRESHOLD}% 이상)에 **미치지 못했습니다**."
        )
        summary_box(f"""
        ### 📋 검증 결과 총평
        본 테스트 결과, 시스템의 전반적인 품질은 평균 **{avg_scores.mean():.2f}/5.0**점으로 측정되었습니다.
        전체 {total}개 테스트 케이스 중 **{pass_n}개({pass_rate:.1f}%)**가 통과(PASS)하였으며, {summary_verdict}
        """)

        st.divider()

        # 1. 취약점 분석 리포트 (실제 기준 미달 여부에 따라 톤을 다르게 표시)
        st.subheader("⚠️ 데이터 기반 취약점 분석")
        c1, c2 = st.columns(2)
        with c1:
            if metric_ok:
                st.success(f"#### 지표 현황: {weakest_metric}")
                st.write(f"가장 낮은 지표인 **{weakest_metric}**도 평균 {weakest_metric_score:.2f}점으로 합격 기준({METRIC_PASS_SCORE}.0점 이상)을 충족합니다.")
                st.write("➡️ 현재 수준을 유지하기 위한 정기 모니터링을 권고합니다.")
            else:
                st.error(f"#### 핵심 개선 지표: {weakest_metric}")
                st.write(f"현재 **{weakest_metric}** 지표가 평균 {weakest_metric_score:.2f}점으로 합격 기준({METRIC_PASS_SCORE}.0점 이상)에 미치지 못합니다.")
                st.write("➡️ 프롬프트 내 제약 조건 강화 및 답변 구조화 지침 보강이 필요합니다.")
        with c2:
            if category_ok:
                st.success(f"#### 카테고리 현황: {worst_cat}")
                st.write(f"합격률이 가장 낮은 **{worst_cat}** 카테고리도 {worst_cat_rate:.1f}%로 합격 기준({ITEM_PASS_THRESHOLD}% 이상)을 충족합니다.")
                st.write("➡️ 전 카테고리가 안정적으로 관리되고 있습니다.")
            else:
                st.warning(f"#### 집중 관리 카테고리: {worst_cat}")
                st.write(f"**{worst_cat}** 카테고리의 합격률이 **{worst_cat_rate:.1f}%**로 합격 기준({ITEM_PASS_THRESHOLD}% 이상)에 미치지 못합니다.")
                st.write("➡️ 해당 카테고리의 정책/규정 문서를 더 구체적으로 보완해야 합니다.")

        st.divider()

        # 2. 기술적 조치 권고 (Action Items) — 실제로 미달 항목이 있을 때만 개선 조치를, 모두 충족 시 유지·모니터링 권고를 표시
        st.subheader("💡 향후 조치 권고 (Next Steps)")

        if overall_ok and metric_ok and category_ok:
            st.markdown("""
            <div class="report-card">
                <p><b>1. 현행 유지 및 정기 모니터링:</b> 모든 지표와 카테고리가 합격 기준을 충족하고 있습니다. 현재 시스템 프롬프트와 지식 베이스 구성을 유지하며 정기적으로 재검증할 것.</p>
                <p><b>2. 회귀 테스트(Regression Test) 체계화:</b> 지식 베이스(RAG 문서) 변경 시마다 전체 테스트 케이스를 재실행하여 품질 저하 여부를 조기에 발견할 것.</p>
                <p><b>3. 테스트 케이스 확장:</b> 새로운 Edge/Negative 시나리오를 지속적으로 추가하여 커버리지를 넓힐 것.</p>
                <p><b>4. 운영 모니터링 체계 연동:</b> 본 자동화 파이프라인을 실제 운영 로그와 연결하여 상시 품질 이상 감지(Anomaly Detection) 체계로 확장 권고.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="report-card">
                <p><b>1. 프롬프트 엔지니어링 최적화:</b> {weakest_metric} 지표 하락을 방지하기 위해 System Prompt 내 Few-shot 예시를 추가하고 페르소나 지침을 구체화할 것.</p>
                <p><b>2. 지식 데이터 고도화:</b> '{worst_cat}' 카테고리의 규정 및 예외 케이스 데이터를 Knowledge Base에 20% 이상 확충하여 할루시네이션 방지.</p>
                <p><b>3. 회귀 테스트(Regression Test) 수행:</b> 조치 적용 후 동일 시나리오에 대해 파이프라인을 재가동하여 판정 결과가 'PASS'로 전환되는지 데이터로 증명할 것.</p>
                <p><b>4. 운영 모니터링 체계 연동:</b> 본 자동화 파이프라인을 실제 운영 로그와 연결하여 상시 품질 이상 감지(Anomaly Detection) 체계로 확장 권고.</p>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # 3. 정식 테스트 결과 보고서 다운로드 (DOCX / PDF)
        st.subheader("📄 정식 테스트 결과 보고서 다운로드")
        st.caption("표지 · 테스트 개요 · 결과 요약 · 차트 · TC 결과 기록표 · 결함 보고서 · 심각도 분류 기준 · 종합 의견으로 구성된 정식 보고서를 생성합니다.")

        result_json_path = selected_json_path
        if st.button("📝 보고서 생성", use_container_width=True):
            if not result_json_path.exists():
                st.error(f"❌ {result_json_path} 파일이 없습니다. 먼저 파이프라인을 실행하세요.")
            else:
                with st.spinner("DOCX/PDF 보고서를 생성하는 중입니다..."):
                    try:
                        eval_results = json.loads(result_json_path.read_text(encoding="utf-8"))
                        docx_path = generate_docx_report(eval_results, REPORTS_DIR / "QA_최종_테스트_결과_보고서.docx")
                        pdf_path = generate_pdf_report(eval_results, REPORTS_DIR / "QA_최종_테스트_결과_보고서.pdf")
                        st.session_state["formal_report_docx"] = docx_path.read_bytes()
                        st.session_state["formal_report_pdf"] = pdf_path.read_bytes()
                        st.success("✅ 보고서 생성 완료! 아래 버튼으로 다운로드하세요.")
                    except Exception as e:
                        st.error(f"❌ 보고서 생성 중 오류: {e}")

        if "formal_report_docx" in st.session_state:
            dcol1, dcol2 = st.columns(2)
            dcol1.download_button(
                "⬇️ DOCX 다운로드",
                data=st.session_state["formal_report_docx"],
                file_name="QA_최종_테스트_결과_보고서.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
            dcol2.download_button(
                "⬇️ PDF 다운로드",
                data=st.session_state["formal_report_pdf"],
                file_name="QA_최종_테스트_결과_보고서.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
