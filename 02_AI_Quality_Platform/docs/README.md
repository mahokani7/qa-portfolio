# AI Agent 품질관리·운영 모니터링 플랫폼

`ai_quality_final_project_rule`(1차: AI 챗봇 품질평가 자동화 파이프라인)을 기반으로,
개발 → 자동테스트 → 품질평가 → 성능검증 → 모니터링 → 배포까지 포함하도록 확장한 프로젝트입니다.

## 폴더 구조

```
app/          → 실제 AI Agent API 서비스 (FastAPI, 서비스/규칙기반 챗봇, 지식검색)
quality/      → 품질검증 (규칙 검증, Judge 채점 파이프라인, 리포트 생성)
tests/        → pytest 자동화 테스트
performance/  → k6 부하테스트
dashboard/    → Streamlit 결과 대시보드
monitoring/   → Prometheus·Grafana 설정
docs/         → 테스트 계획서·결함보고서·성능보고서·최종 품질보고서
```

## 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
`.env.example`을 복사해 `.env`를 만들고 `OPENAI_API_KEY`를 채웁니다.

### 3. FastAPI 서버 실행
```bash
uvicorn app.main:app --reload
```
- `GET /health` : 헬스체크
- `POST /ask` : `{"question": "...", "use_rule_based": false}`
- `GET /metrics` : 운영 지표(임시 텍스트 포맷, TODO: Prometheus 표준 포맷으로 교체)

### 4. 품질평가 파이프라인 실행 (규칙 기반 vs API 기반 비교)
```bash
python -m quality.quality_pipeline
```
결과는 `quality/reports/`에 JSON/CSV/Markdown으로 저장됩니다.

### 5. 자동 테스트
```bash
pytest -v
```

### 6. Streamlit 대시보드
```bash
streamlit run dashboard/streamlit_app.py
```

### 7. 성능 테스트 (k6 설치 필요)
```bash
uvicorn app.main:app &
k6 run performance/k6_test.js
```

## 1차 프로젝트와의 관계
이 프로젝트는 `ai_quality_final_project_rule`의 완전한 재작성이 아니라, 같은 로직을 역할별 폴더(app/quality/tests/…)로
재배치하고 API·자동테스트·모니터링 레이어를 추가한 확장판입니다. 세부 이관 매핑은 1차 프로젝트의
`dashboard/docs/13_expansion_roadmap.html`, `14_presentation_development_plan.docx`를 참고하세요.
