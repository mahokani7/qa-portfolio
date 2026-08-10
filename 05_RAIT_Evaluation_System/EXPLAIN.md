이 프로그램은 Streamlit으로 만든 RaiT 품질 평가 대시보드입니다.
사용자가 8개 품질 지표 점수를 조정하면, 선택한 정책과 계산 방식에 따라 **AI 서비스 배포 가능 여부(Pass/Fail)**를 판정합니다.

핵심 흐름은 다음과 같습니다.

import streamlit as st

Streamlit 웹 화면을 만들기 위한 라이브러리입니다.

sys.path.append(...)

app.py가 app 폴더 안에 있기 때문에, 상위 폴더의 src 모듈을 불러오기 위해 경로를 추가합니다.

from src.utils.config_loader import load_policy
from src.engine.calculator import RaiTCalculator
from src.engine.filter import RaiTFilter

외부 파일에서 기능을 가져옵니다.

load_policy는 정책 설정을 불러오고,
RaiTCalculator는 점수를 계산하고,
RaiTFilter는 합격/불합격을 판단합니다.

화면 구성은 크게 4단계입니다.

사이드바에서 정책 선택
policy_choice = st.sidebar.selectbox(...)
mode_choice = st.sidebar.radio(...)

사용자는 평가 도메인 정책을 선택합니다.

예:

default_pilot
high_risk_finance
low_risk_entertainment

그리고 계산 방식을 선택합니다.

simple   단순 평균
weight   가중 평균
cutoff   과락 기준 적용
hybrid   가중치 + 과락 기준 적용
8대 품질 지표 점수 입력
r = st.slider("관련성 (R)", 0.0, 5.0, 4.2, 0.1)

각 품질 지표를 0점부터 5점까지 조정합니다.

평가 지표는 다음 8개입니다.

R 관련성
E 적합성
U 이해도
S 안전성
T 표현성
A 정확성
C 일관성
P 지속성
점수 계산
if mode_choice in ['simple', 'cutoff']:
    final_score = RaiTCalculator.calculate_simple_average(current_scores)
else:
    final_score = RaiTCalculator.calculate_weighted_average(current_scores, policy["weights"])

simple, cutoff 방식이면 단순 평균을 계산합니다.
weight, hybrid 방식이면 정책 파일에 정의된 가중치를 반영해서 계산합니다.

합격/불합격 판정
result = RaiTFilter.check_pass_fail(...)

최종 점수가 목표 기준점 이상인지 확인하고, 과락 기준이 있으면 특정 지표가 기준 미달인지도 확인합니다.

결과는 화면에 이렇게 표시됩니다.

RELEASE PASS

또는

RELEASE FAIL

특정 지표가 과락이면 다음처럼 보여줍니다.

과락 통과 실패 지표: S, T

마지막의 코드입니다.

st.json({"적용중인 정책 프로필": policy})

현재 적용된 정책 내용을 JSON 형태로 보여주는 디버깅용 화면입니다.

정리하면 이 프로그램은 AI 응답 품질을 8개 지표로 평가하고, 도메인별 기준점과 과락 조건을 적용해 서비스 출시 가능 여부를 시뮬레이션하는 교육용 품질관리 도구입니다.