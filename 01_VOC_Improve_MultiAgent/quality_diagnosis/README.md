# 품질 진단

교수님 실습 문서의 6번 품질 판정표를 코드와 동일한 기준으로 관리합니다.

- 배점 원본: `evaluation_rubric.csv`
- 실행 판정: `utils/quality_evaluator.py`
- 배치 실행 및 JSON/CSV 보고서: `e2e_runner.py`

배포 가능 기본 기준은 95점이며 웹 품질 운영 화면에서 0~100점 사이로 조정·저장할 수
있습니다. 라이브 E2E와 독립 Judge가 모두 현재 기준 이상이어야 기술 기준을 통과합니다.
80점 이상이지만 기준 미만이면 조건부 배포 보류, 70~79점은 주요 개선 필요,
69점 이하는 배포 보류입니다. 개인정보 노출, 근거 없는 사실, 장애 성공 위장,
결제·환불 오안내가 검출되면 점수와 관계없이 즉시 배포 보류합니다.

## 7번 장애 진단 실행

현재 가상환경에서 바로 실행:

```powershell
python -m unittest quality_diagnosis.test_fault_tolerance -v
python quality_diagnosis/run_fault_diagnosis.py
```

`pytest`를 설치한 환경에서는 교수님 문서의 명령도 사용할 수 있습니다.

```powershell
pytest quality_diagnosis/test_fault_tolerance.py -v
```

진단 대상은 Retriever 중단, 포트 충돌, CSV 누락, API 키 미설정·인증 거부,
응답 지연, 빈 검색 결과입니다. 테스트는 임시 로컬 포트와 가짜 클라이언트를 사용하므로
운영 서버나 실제 API 키를 변경하지 않습니다.

## 8번 전체 품질진단 실행

```powershell
python quality_diagnosis/build_case_catalog.py
python quality_diagnosis/run_quality_suite.py
python e2e_runner.py --mode offline --domain ecommerce
python quality_diagnosis/run_fault_diagnosis.py
python quality_diagnosis/llm_judge.py --provider deterministic
python quality_diagnosis/generate_deployment_report.py
```

최종 결과는 `quality_diagnosis/reports/test_result.csv`, `quality_score_report.md`,
`deployment_decision.md`에서 확인합니다. 실제 API와 독립 Judge를 실행하지 않은 경우
정식 배포 승인 대신 기술적 파일럿 검증으로 표시됩니다.

## 35건 종합 평가와 첨부 보고서

```powershell
python quality_diagnosis/run_35_case_evaluation.py
python quality_diagnosis/build_comprehensive_report.py
```

35건 평가는 이커머스 18건, 보험 15건, 핵심 결함 회귀 2건을 합쳐 초기
33 PASS / 2 FAIL에서 최종 35 PASS / 0 FAIL로 개선된 이력을 생성합니다. 종합 보고서는
PDF·HTML·XML·TXT·JSON, 테스트 추이·점검 범위·결함 상태·잔여 위험 PNG와 ZIP 첨부 묶음으로
저장됩니다. 웹의 **품질 운영·보고서 → 6. 종합 품질평가 첨부 보고서**에서도 같은 작업을
실행하고 내려받을 수 있습니다.

`run_quality_suite.py`, `run_fault_diagnosis.py`, `e2e_runner.py`, `llm_judge.py`의 공식 실행은
각 실행마다 `test_evidence_<종류>_<시각>.txt/.xml/.html`을 별도로 만들고
`reports/test_execution_history.jsonl`에 이력을 누적합니다.
