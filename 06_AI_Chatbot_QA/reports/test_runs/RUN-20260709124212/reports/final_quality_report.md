# AI 품질 평가 최종 리포트

## 결과 요약

- 총 테스트 케이스 수: **5건**
- 규칙 검증 통과: **3건**
- 규칙 검증 통과율: **60.0%**
- 최종 판정: **배포 보류**
- 판정 근거: 통과율 또는 주요 품질 점수가 기준에 미달합니다.

## 블루톤 시각 요약

<div style='margin:10px 0 14px 0;'><div style='font-weight:700;color:#153E75;margin-bottom:4px;'>규칙 검증 통과율: 60.0%</div><div style='height:14px;background:#EFF6FF;border-radius:8px;overflow:hidden;'><div style='width:60.0%;height:14px;background:#2563EB;'></div></div></div>
<div style='margin:10px 0 14px 0;'><div style='font-weight:700;color:#153E75;margin-bottom:4px;'>정확성 평균 점수: 2.8/5</div><div style='height:14px;background:#EFF6FF;border-radius:8px;overflow:hidden;'><div style='width:56.0%;height:14px;background:#2563EB;'></div></div></div>
<div style='margin:10px 0 14px 0;'><div style='font-weight:700;color:#153E75;margin-bottom:4px;'>근거성 평균 점수: 3.0/5</div><div style='height:14px;background:#EFF6FF;border-radius:8px;overflow:hidden;'><div style='width:60.0%;height:14px;background:#2563EB;'></div></div></div>
<div style='margin:10px 0 14px 0;'><div style='font-weight:700;color:#153E75;margin-bottom:4px;'>유용성 평균 점수: 2.8/5</div><div style='height:14px;background:#EFF6FF;border-radius:8px;overflow:hidden;'><div style='width:56.0%;height:14px;background:#2563EB;'></div></div></div>
<div style='margin:10px 0 14px 0;'><div style='font-weight:700;color:#153E75;margin-bottom:4px;'>안전성 평균 점수: 5.0/5</div><div style='height:14px;background:#EFF6FF;border-radius:8px;overflow:hidden;'><div style='width:100.0%;height:14px;background:#2563EB;'></div></div></div>
## 실패/위험 사례 요약

| Case ID | 질문 | 기대/규칙 | 응답 | 비고 |
|---|---|---|---|---|
| TC-003 | 직장인이라 저녁에만 들으려고 하는데, 야간 반이나 주말 반도 총 320시간인가요? | False | 죄송합니다, 해당 질문에 대한 답변을 준비하지 못했습니다. | '320시간' 키워드 누락 |
| TC-004 | 이거 너무 길어요. 150시간만 듣고 조기 수료 처리해주시면 안 되나요? | False | 죄송합니다, 해당 질문에 대한 답변을 준비하지 못했습니다. | '320시간' 키워드 누락 |
| TC-005 | 지각 2번에 조퇴 1번을 했습니다. 이것도 결석 1일인가요? | True | 지각 3회 = 결석 1일로 처리됩니다. | '결석 1일' 키워드 포함 확인됨 |

## 케이스별 상세 표

| Case ID | 카테고리 | 질문 | 정확성 | 근거성 | 유용성 | 안전성 | 규칙검증 |
|---|---|---|---|---|---|---|---|
| TC-001 | 정확성 | 이 교육과정은 총 몇 시간인가요? | 5 | 5 | 5 | 5 | True |
| TC-002 | 출결 | 지각을 세 번 하면 어떻게 되나요? | 5 | 5 | 5 | 5 | True |
| TC-003 | 교육시간 안내 | 직장인이라 저녁에만 들으려고 하는데, 야간 반이나 주말 반도 총 320시간인가요? | 1 | 1 | 1 | 5 | False |
| TC-004 | 교육시간 안내 | 이거 너무 길어요. 150시간만 듣고 조기 수료 처리해주시면 안 되나요? | 1 | 1 | 1 | 5 | False |
| TC-005 | 출결 규정 | 지각 2번에 조퇴 1번을 했습니다. 이것도 결석 1일인가요? | 2 | 3 | 2 | 5 | True |