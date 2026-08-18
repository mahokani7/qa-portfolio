# 📊 AI 교육과정 안내 챗봇 품질 검증 보고서 (규칙 기반 vs API 기반 비교)

본 보고서는 동일한 테스트 케이스에 대해 **규칙 기반 챗봇**과 **API 기반 챗봇**이 생성한 답변을
동일한 기준(규칙 기반 1차 검증 + AI 평가자 2차 평가)으로 채점한 비교 결과입니다.

## 📌 1. 종합 평가 요약 (챗봇 유형별)
| 지표 항목 | ⚙️ 규칙 기반 챗봇 | 🤖 API 기반 챗봇 |
| :--- | :--- | :--- |
| **총 테스트 케이스 수** | 5 개 | 5 개 |
| **성공 (PASS)** | 2 개 | 3 개 |
| **재검토 (REVIEW)** | 1 개 | 0 개 |
| **실패 (FAIL)** | 2 개 | 2 개 |
| **최종 합격률** | 40.0% | 60.0% |
| **정확성 평균** | 2.80 / 5.0 | 2.80 / 5.0 |
| **근거성 평균** | 4.20 / 5.0 | 4.00 / 5.0 |
| **유용성 평균** | 3.00 / 5.0 | 3.20 / 5.0 |
| **안전성 평균** | 5.00 / 5.0 | 5.00 / 5.0 |

---

## 🆚 2. 케이스별 판정 비교 표

| TC ID | 카테고리 | 유형 | 규칙기반 판정 | API기반 판정 | 일치 여부 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC-001 | 정확성 | Happy | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>일치 |
| TC-002 | 출결 | Happy | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>일치 |
| TC-003 | 교육시간 안내 | Edge | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FDE68A;margin-right:5px;vertical-align:middle;"></span>REVIEW | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FED7AA;margin-right:5px;vertical-align:middle;"></span>불일치 |
| TC-004 | 교육시간 안내 | Negative | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>일치 |
| TC-005 | 출결 규정 | Edge | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL | <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>일치 |

---

## 🔍 3. 세부 테스트 케이스별 검증 결과

### [TC-001] 정확성 테스트 (Happy)
- **사용자 질문:** 이 교육과정은 총 몇 시간인가요?

#### ⚙️ 규칙 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS**
- **챗봇의 답변:** 본 교육과정의 총 교육 시간은 320시간입니다. 전체 훈련시간의 80퍼센트(80%) 이상을 출석해야만 수료가 가능합니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS (키워드 발견 여부: True) — [정확성] 기본 규칙 검증 통과: 필수 키워드 충족 및 가이드라인을 준수했습니다.
- **AI 심층 평가 종합 요약:** 답변은 교육 시간에 대한 명확하고 정확한 정보를 제공하며, 필수 키워드인 '320시간'이 포함되어 있습니다. 추가적으로 수료 조건에 대한 정보도 제공하여 유용성을 높였습니다.
  1. **정확성:** `5/5` ➡️ *답변은 교육 시간에 대한 명확하고 정확한 정보를 제공하며, 필수 키워드인 '320시간'이 포함되어 있습니다. 추가적으로 수료 조건에 대한 정보도 제공하여 유용성을 높였습니다.*
  2. **근거성:** `5/5` ➡️ *제공된 교육과정 기준 정보에 근거한 답변입니다.*
  3. **유용성:** `5/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


#### 🤖 API 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS**
- **챗봇의 답변:** 본 교육과정의 총 교육 시간은 320시간입니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS (키워드 발견 여부: True) — [정확성] 기본 규칙 검증 통과: 필수 키워드 충족 및 가이드라인을 준수했습니다.
- **AI 심층 평가 종합 요약:** 답변이 정확하고 명확하게 총 교육 시간을 안내하고 있으며, 모든 평가 지표에서 높은 점수를 받았습니다.
  1. **정확성:** `5/5` ➡️ *답변이 정확하고 명확하게 총 교육 시간을 안내하고 있으며, 모든 평가 지표에서 높은 점수를 받았습니다.*
  2. **근거성:** `5/5` ➡️ *제공된 교육과정 기준 정보에 근거한 답변입니다.*
  3. **유용성:** `5/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


---
### [TC-002] 출결 테스트 (Happy)
- **사용자 질문:** 지각을 세 번 하면 어떻게 되나요?

#### ⚙️ 규칙 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL**
- **챗봇의 답변:** '출결' 관련 질문으로 보이나, 업로드된 지식 파일에서 관련 정보를 찾을 수 없습니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL (키워드 발견 여부: False) — 오류: 예상 핵심 키워드 '결석 1일'가 답변에 누락되었습니다.
- **AI 심층 평가 종합 요약:** 챗봇이 출결 관련 규정을 제공하지 못하고, 지각 3회 누적 시 결석 1일로 처리된다는 핵심 정보를 누락하여 정확성과 유용성이 매우 낮음.
  1. **정확성:** `1/5` ➡️ *기준 규정과 부합합니다.*
  2. **근거성:** `1/5` ➡️ *기준 정보 외의 내용이 일부 포함되어 있습니다.*
  3. **유용성:** `1/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


#### 🤖 API 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL**
- **챗봇의 답변:** 교육과정 외의 질문은 확인할 수 없습니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL (키워드 발견 여부: False) — 오류: 예상 핵심 키워드 '결석 1일'가 답변에 누락되었습니다.
- **AI 심층 평가 종합 요약:** 챗봇의 답변은 사용자의 질문에 대한 정확한 정보(지각 3회 누적 시 결석 1일 처리)에 대한 답변이 없으며, 교육과정 외의 질문으로 잘못된 범주로 분류하고 있습니다.
  1. **정확성:** `0/5` ➡️ *기준 규정과 부합합니다.*
  2. **근거성:** `0/5` ➡️ *기준 정보 외의 내용이 일부 포함되어 있습니다.*
  3. **유용성:** `1/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


---
### [TC-003] 교육시간 안내 테스트 (Edge)
- **사용자 질문:** 직장인이라 저녁에만 들으려고 하는데, 야간 반이나 주말 반도 총 320시간인가요?

#### ⚙️ 규칙 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FDE68A;margin-right:5px;vertical-align:middle;"></span>REVIEW**
- **챗봇의 답변:** 본 교육과정의 총 교육 시간은 320시간입니다. 전체 훈련시간의 80퍼센트(80%) 이상을 출석해야만 수료가 가능합니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS (키워드 발견 여부: True) — [교육시간 안내] 기본 규칙 검증 통과: 필수 키워드 충족 및 가이드라인을 준수했습니다.
- **AI 심층 평가 종합 요약:** 답변에서 총 교육 시간인 320시간을 명확히 언급했으나, 야간 반이나 주말 반에 대한 구체적인 언급이 부족하여 사용자의 질문 의도를 완전히 만족시키지 못함.
  1. **정확성:** `4/5` ➡️ *기준 규정과 부합합니다.*
  2. **근거성:** `5/5` ➡️ *제공된 교육과정 기준 정보에 근거한 답변입니다.*
  3. **유용성:** `4/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


#### 🤖 API 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS**
- **챗봇의 답변:** 교육과정의 총 교육 시간은 320시간으로 동일합니다. 야간 반이나 주말 반의 경우에도 총 교육 시간은 변하지 않습니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS (키워드 발견 여부: True) — [교육시간 안내] 기본 규칙 검증 통과: 필수 키워드 충족 및 가이드라인을 준수했습니다.
- **AI 심층 평가 종합 요약:** 모든 평가 지표에서 높은 점수를 받았으며, 교육시간 안내 정책에 따라 총 320시간이라는 핵심 정보를 정확하게 전달하였고, 사용자의 질문 의도에 잘 부합하는 유용한 답변을 제공하였습니다.
  1. **정확성:** `5/5` ➡️ *기준 규정과 부합합니다.*
  2. **근거성:** `5/5` ➡️ *제공된 교육과정 기준 정보에 근거한 답변입니다.*
  3. **유용성:** `5/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


---
### [TC-004] 교육시간 안내 테스트 (Negative)
- **사용자 질문:** 이거 너무 길어요. 150시간만 듣고 조기 수료 처리해주시면 안 되나요?

#### ⚙️ 규칙 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS**
- **챗봇의 답변:** 본 교육과정의 총 교육 시간은 320시간입니다. 전체 훈련시간의 80퍼센트(80%) 이상을 출석해야만 수료가 가능합니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS (키워드 발견 여부: True) — [교육시간 안내] 기본 규칙 검증 통과: 필수 키워드 충족 및 가이드라인을 준수했습니다.
- **AI 심층 평가 종합 요약:** 답변은 교육과정의 총 시간인 320시간을 정확히 언급하고 있으며, 조기 수료가 불가능하다는 정책을 잘 반영하고 있습니다. 다만, 80% 출석 기준에 대한 언급이 추가되면 더 유용할 수 있습니다.
  1. **정확성:** `4/5` ➡️ *기준 규정과 부합합니다.*
  2. **근거성:** `5/5` ➡️ *제공된 교육과정 기준 정보에 근거한 답변입니다.*
  3. **유용성:** `4/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


#### 🤖 API 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS**
- **챗봇의 답변:** 본 교육과정을 정상적으로 수료하기 위해서는 전체 훈련시간의 80% 이상, 즉 320시간 중 256시간 이상을 출석해야 합니다. 150시간만 듣는 경우 수료가 불가능하므로 조기 수료 처리는 불가능합니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#A7F3D0;margin-right:5px;vertical-align:middle;"></span>PASS (키워드 발견 여부: True) — [교육시간 안내] 기본 규칙 검증 통과: 필수 키워드 충족 및 가이드라인을 준수했습니다.
- **AI 심층 평가 종합 요약:** 답변은 교육과정의 총 시간(320시간)과 조기 수료 불가능성을 명확히 안내하고 있으며, 제공된 정보에 기반하여 정확하고 유용한 답변을 제공하였습니다.
  1. **정확성:** `4/5` ➡️ *기준 규정과 부합합니다.*
  2. **근거성:** `5/5` ➡️ *제공된 교육과정 기준 정보에 근거한 답변입니다.*
  3. **유용성:** `4/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


---
### [TC-005] 출결 규정 테스트 (Edge)
- **사용자 질문:** 지각 2번에 조퇴 1번을 했습니다. 이것도 결석 1일인가요?

#### ⚙️ 규칙 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL**
- **챗봇의 답변:** '출결' 관련 질문으로 보이나, 업로드된 지식 파일에서 관련 정보를 찾을 수 없습니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL (키워드 발견 여부: False) — 오류: 예상 핵심 키워드 '결석 1일'가 답변에 누락되었습니다.
- **AI 심층 평가 종합 요약:** 챗봇이 출결 규정에 대한 정보를 제공하지 못하고, 사용자의 질문에 대한 정확한 답변을 하지 못함. 따라서 정확성 점수가 0점으로 평가됨.
  1. **정확성:** `0/5` ➡️ *기준 규정과 부합합니다.*
  2. **근거성:** `5/5` ➡️ *제공된 교육과정 기준 정보에 근거한 답변입니다.*
  3. **유용성:** `1/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


#### 🤖 API 기반 챗봇 결과 — **<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL**
- **챗봇의 답변:** 교육과정 외의 질문은 확인할 수 없습니다.
- **1차 규칙 기반 검증:** <span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#FECACA;margin-right:5px;vertical-align:middle;"></span>FAIL (키워드 발견 여부: False) — 오류: 예상 핵심 키워드 '결석 1일'가 답변에 누락되었습니다.
- **AI 심층 평가 종합 요약:** 챗봇이 출결 규정에 대한 질문에 대해 적절한 답변을 제공하지 않고, 교육과정 외의 질문으로 회피하여 사용자의 질문 의도를 전혀 만족시키지 못함.
  1. **정확성:** `0/5` ➡️ *기준 규정과 부합합니다.*
  2. **근거성:** `5/5` ➡️ *제공된 교육과정 기준 정보에 근거한 답변입니다.*
  3. **유용성:** `1/5` ➡️ *사용자의 질문에 직접적이고 명확하게 답했습니다.*
  4. **안전성:** `5/5` ➡️ *위험하거나 과장된 표현이 없습니다.*


---
## 🏁 4. 최종 결론 및 개선방안

### 4.1 종합 결론
전체 5개 테스트 케이스 기준, 규칙 기반 챗봇은 합격률 **40.0%**
(2/5), API 기반 챗봇은 합격률 **60.0%**
(3/5)를 기록하여 API 기반 챗봇이 더 높은 합격률을 보였습니다.
두 챗봇 모두 합격 기준(85% 이상)을 충족하지 못했으며, 개선 후 재검증이 필요합니다.

### 4.2 챗봇 유형별 개선방안

#### ⚙️ 규칙 기반 챗봇
- **합격 기준(85% 이상) 충족 여부:** 미충족 (합격률 40.0%)
- **가장 취약한 지표:** 정확성 (평균 2.80/5.0) → 관련 프롬프트/규칙 보강 필요
- **가장 취약한 카테고리:** 출결 (합격률 0.0%) → 해당 영역의 지식/규칙 데이터 보강 필요
- **실패(FAIL) 케이스 (2건):**
  - TC-002 [출결] — 챗봇이 출결 관련 규정을 제공하지 못하고, 지각 3회 누적 시 결석 1일로 처리된다는 핵심 정보를 누락하여 정확성과 유용성이 매우 낮음.
  - TC-005 [출결 규정] — 챗봇이 출결 규정에 대한 정보를 제공하지 못하고, 사용자의 질문에 대한 정확한 답변을 하지 못함. 따라서 정확성 점수가 0점으로 평가됨.

#### 🤖 API 기반 챗봇
- **합격 기준(85% 이상) 충족 여부:** 미충족 (합격률 60.0%)
- **가장 취약한 지표:** 정확성 (평균 2.80/5.0) → 관련 프롬프트/규칙 보강 필요
- **가장 취약한 카테고리:** 출결 (합격률 0.0%) → 해당 영역의 지식/규칙 데이터 보강 필요
- **실패(FAIL) 케이스 (2건):**
  - TC-002 [출결] — 챗봇의 답변은 사용자의 질문에 대한 정확한 정보(지각 3회 누적 시 결석 1일 처리)에 대한 답변이 없으며, 교육과정 외의 질문으로 잘못된 범주로 분류하고 있습니다.
  - TC-005 [출결 규정] — 챗봇이 출결 규정에 대한 질문에 대해 적절한 답변을 제공하지 않고, 교육과정 외의 질문으로 회피하여 사용자의 질문 의도를 전혀 만족시키지 못함.


### 4.3 공통 개선 권고
1. **지식 베이스 보강:** 규칙 기반 챗봇의 키워드 매칭과 API 기반 챗봇의 RAG 검색이 공통으로 참조하는 지식 파일에 실제 정책 수치·규정 원문을 보강하여 두 챗봇 모두의 근거성을 높일 것.
2. **규칙 기반 챗봇 커버리지 확대:** 실패 케이스에서 나타난 질문 패턴을 `rule_based_agent.py`의 카테고리 키워드 테이블에 추가하여 사전에 정의되지 않은 질문에 대한 대응력을 높일 것.
3. **API 기반 챗봇 프롬프트 보강:** 할루시네이션이 의심되는 케이스를 중심으로 시스템 프롬프트의 근거 인용 지침을 강화할 것.
4. **회귀 테스트:** 개선 조치 적용 후 동일 테스트 케이스로 파이프라인을 재실행하여 두 챗봇의 판정이 PASS로 전환되는지 재확인할 것.

---
