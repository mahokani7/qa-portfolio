import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_loader import load_policy
from src.engine.calculator import RaiTCalculator
from src.engine.filter import RaiTFilter

st.set_page_config(page_title="RaiT 대시보드", layout="wide")
st.title("🛡️ RaiT 품질 기준점 시뮬레이터")

# 1. 사이드바 - 정책 설정
st.sidebar.header("⚙️ 평가 정책 설정")
policy_choice = st.sidebar.selectbox("도메인 정책 선택", ["default_pilot", "high_risk_finance", "low_risk_entertainment"])
mode_choice = st.sidebar.radio("연산 방식 선택", ["simple", "weight", "cutoff", "hybrid"])

policy = load_policy(policy_choice)

st.sidebar.write(f"**선택된 목표 기준점:** {policy['target_score']}점")
st.sidebar.write(f"**설정된 커트라인 수치:** {policy['cutoffs']}")

# 2. 메인 화면 - 점수 조정 입력 인터페이스
st.header("📊 8대 품질 지표 점수 시뮬레이션 (0 ~ 5점)")
col1, col2, col3, col4 = st.columns(4)

with col1:
    r = st.slider("관련성 (R)", 0.0, 5.0, 4.2, 0.1)
    e = st.slider("적합성 (E)", 0.0, 5.0, 4.2, 0.1)
with col2:
    u = st.slider("이해도 (U)", 0.0, 5.0, 3.8, 0.1)
    s = st.slider("안전성 (S)", 0.0, 5.0, 2.5, 0.1) # 문서 실패 예시 디폴트값
with col3:
    t = st.slider("표현성 (T)", 0.0, 5.0, 2.5, 0.1)
    a = st.slider("정확성 (A)", 0.0, 5.0, 4.0, 0.1)
with col4:
    c = st.slider("일관성 (C)", 0.0, 5.0, 4.0, 0.1)
    p = st.slider("지속성 (P)", 0.0, 5.0, 4.0, 0.1)

current_scores = {'R': r, 'E': e, 'U': u, 'S': s, 'T': t, 'A': a, 'C': c, 'P': p}

# 3. 연산 수행
if mode_choice in ['simple', 'cutoff']:
    final_score = RaiTCalculator.calculate_simple_average(current_scores)
else:
    final_score = RaiTCalculator.calculate_weighted_average(current_scores, policy["weights"])

result = RaiTFilter.check_pass_fail(
    final_score=final_score,
    target_score=policy["target_score"],
    scores=current_scores,
    cutoffs=policy["cutoffs"],
    mode=mode_choice
)

# 4. 결과 디스플레이
st.markdown("---")
st.subheader("🏁 최종 배포 심사 결과")

if result["status"] == "Pass":
    st.success(f"## 🎉 RELEASE PASS (최종 계산 점수: {result['final_score']} / 합격점: {policy['target_score']})")
else:
    st.error(f"## ❌ RELEASE FAIL (최종 계산 점수: {result['final_score']} / 합격점: {policy['target_score']})")
    if result["cutoff_fails"]:
        st.warning(f"⚠️ **과락(Cutoff) 통과 실패 지표:** {', '.join(result['cutoff_fails'])}")

# 디버깅용 가중치 현황판
st.json({"적용중인 정책 프로필": policy})