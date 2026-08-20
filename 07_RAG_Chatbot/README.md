# RAG 챗봇 — 문서 기반 근거 답변 + 품질평가

LLM이 아는 척 답하지 않고, 업로드한 문서에서 근거를 찾아 그 근거와 함께 답하도록 만든 RAG(Retrieval-Augmented Generation) 챗봇입니다. 문서 업로드 → 분할 → 임베딩·ChromaDB 저장 → 질문 시 유사 문서 검색 → 근거 기반 답변 흐름이며, LLM Judge가 답변 품질(이해도·정확성)을 자동 평가합니다.

**왜 필요한가**: 일반 LLM 챗봇은 모르는 내용도 그럴듯하게 답하는 환각 위험이 있습니다. 답변 근거를 실제 업로드 문서로 제한하고, 그 결과를 LLM Judge로 다시 채점해 "문서에 없으면 모른다고 답하는가"를 검증 가능하게 만드는 것이 목표입니다.

## QA SUMMARY

| 항목 | 내용 |
|---|---|
| 프로젝트 유형 | 개인 프로젝트 |
| 내 역할 | RAG 파이프라인, Judge Agent, 평가 실행·리포트, Streamlit UI 전체 |
| 테스트 범위 | 별도 pytest 스위트 없음 — `run_tests.py`가 `test_cases.json`(10건) 순회하며 실제 LLM 호출로 채점, Judge 평가 7회 실행 이력 존재 |
| 자동화 도구 | `run_tests.py`, `run_evaluation.py` (LLM Judge 채점) |
| 주요 검증 | 정상 질문(문서 기반 답변), 문서 외 질문(모른다고 답하는지), Judge 응답 형식이 깨졌을 때 안전하게 실패 처리하는지 |
| 주요 결함 | 파이프라인 함수 시그니처 불일치로 평가가 전량 실패한 실행 이력 발견(`get_evaluation_from_openai() missing 3 required positional arguments`) |
| 개선 결과 | 이후 실행에서는 정상적으로 10건 평가·리포트 생성됨(최신 실행 PASS 7/10) |
| 최종 판정 | 최신 Judge 평가 기준 **10건 중 7건 PASS(70%)** |

## Project Type

개인 프로젝트

## My Role

- RAG 파이프라인(`ingest.py`, `rag_service.py`) 설계·구현
- Judge Agent(`evaluator_agent.py`) 설계 — 루브릭 평가·감점 평가·최종 점수 산출 로직
- 답변 품질 평가 실행 및 리포트 생성(`run_evaluation.py`, `run_tests.py`)
- Streamlit UI(챗봇/문서관리/품질평가 3탭) 구현

## 📌 채용담당자용 핵심 문서

- [최신 평가 결과](reports/rag_evaluation_report_latest.json) — 10건 중 PASS 7건(70%), 평균 정확성 3.6/5
- [실패했던 평가 실행](reports/rag_evaluation_20260625_113349.json) — 함수 인자 누락으로 전량 실패한 실제 버그 사례
- 위 QA SUMMARY, 아래 QA 관점의 핵심 — 제가 수행한 역할과 발견한 문제

## QA 관점의 핵심

- **무엇을 검증했는가**: RAG 챗봇이 문서에 없는 내용을 그럴듯하게 지어내지 않고, 실제로 업로드 문서에 근거해 답하는지
- **왜 검증했는가**: 일반 LLM은 모르는 내용도 아는 척 답하는 환각 위험이 있어, 답변 품질을 LLM Judge로 재채점해 검증 가능하게 만들기 위해
- **PASS/FAIL 기준**: `evaluator_agent.py`가 이해도·정확성 점수를 종합해 `overall_pass` 판정. Judge 응답 형식이 깨지면 임의로 통과 처리하지 않고 `overall_pass: False`로 안전하게 실패 처리
- **발견한 문제**: (1) 라이브 평가 실행 중 `get_evaluation_from_openai()` 함수 호출에 필수 인자 3개가 누락돼 해당 실행의 모든 케이스가 에러 처리된 사례(`reports/rag_evaluation_20260625_113349.json`) — 실제 코드 결함 (2) 케이스 RAG-002·004·006은 정상 실행됐지만 Judge가 FAIL 판정(예: RAG-002는 "답변에 출처가 없어 이해도 -1점 감점")
- **어떻게 분석했는가**: 실패 케이스의 Judge 채점 근거(`raw_output`)를 리포트에 그대로 보존해, 어떤 rubric 항목에서 왜 감점됐는지 원문으로 추적 가능하게 함
- **재검증**: 함수 시그니처 수정 후 재실행한 최신 평가(`rag_evaluation_report_latest.json`)는 10건 모두 정상 채점되어 PASS 7건(70%)·평균 정확성 3.6/5 확보

> **평가 축에 대한 정확한 설명**: Judge 프롬프트(`ai_answer.md`)는 이해도·정확성·관련성·표현성 4개 축을 예시로 보여주지만, 실제 채점 로직(`evaluator_agent.py`)이 파싱·집계하는 것은 **이해도·정확성 2개 축**입니다. 관련성·표현성은 현재 자동 집계되지 않습니다. 또한 검색 정확도(retrieval accuracy)와 근거성(groundedness)을 별도로 측정하는 지표는 없습니다 — 이해도 점수가 `grounding_score`라는 필드명으로 저장돼 있지만 실제로는 근거 인용 품질이 아닌 이해도 채점 결과입니다.

---

## 🔧 Technical Reference

아래는 실행 방법·평가 로직 상세입니다. 채용담당자는 위 내용만으로 프로젝트를 이해할 수 있습니다.

## 주요 기능

- Streamlit 3탭 구성: **챗봇**(질문·답변·근거 확인) / **문서 관리**(업로드·벡터DB 재구축) / **품질평가 안내**
- LangChain + ChromaDB 기반 문서 검색(RAG)
- OpenAI Judge Agent(`evaluator_agent.py`)가 루브릭 평가 → 감점 평가 → 최종 점수(5점 만점) 산출
- 평가 결과를 JSON/Markdown 리포트로 저장(`run_tests.py`, `run_evaluation.py`)
- `documents/` — 교육과정 안내 문서, `uploads/` — 국민취업지원제도 매뉴얼 PDF 등 샘플 데이터 포함, **ChromaDB 인덱스도 이미 만들어져 있어 재색인 없이 바로 질의 가능**

## 프로젝트 구조

```text
.
├─ app.py               # Streamlit 챗봇 UI(챗봇/문서관리/품질평가 3탭)
├─ ingest.py             # 문서 → 벡터DB 재구축 CLI
├─ rag_service.py        # 문서 검색 + 답변 생성 로직
├─ evaluator_agent.py    # OpenAI Judge — 답변 품질 평가
├─ run_tests.py          # 테스트 케이스 일괄 실행 + 리포트 생성
├─ run_evaluation.py     # 평가 파이프라인
├─ report.py
├─ documents/            # RAG 원본 문서(샘플)
├─ uploads/               # 업로드 PDF(샘플)
├─ chroma_db/             # 벡터DB(이미 생성됨)
├─ reports/               # 평가 결과 리포트
└─ requirements.txt
```

## 준비 사항

- Python 3.10+
- OpenAI API 키(임베딩 + LLM 응답 + Judge 평가에 사용)

## 설치 및 실행

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
# .env에 OPENAI_API_KEY 입력
```

### 1) 챗봇 UI 실행

```powershell
streamlit run app.py
```

브라우저에서 **http://localhost:8501** 접속. 좌측 사이드바에서 문서를 업로드하고 벡터DB를 만든 뒤, 챗봇 탭에서 질문하면 근거 문서와 함께 답변을 확인할 수 있습니다. (샘플 `documents/`·`uploads/`와 사전 생성된 `chroma_db/`가 포함되어 있어 새 문서 없이도 바로 질의해 볼 수 있습니다.)

### 2) 문서를 새로 추가·수정했다면 벡터DB 재생성

```powershell
Remove-Item -Recurse -Force chroma_db
py ingest.py
```

### 3) 품질평가 파이프라인 실행 (별도 터미널)

```powershell
py run_tests.py
```

`test_cases.json`의 질문을 순회하며 RAG 답변 생성 → Judge 평가 → `reports/`에 JSON/Markdown 리포트를 저장합니다.

## 환경변수

| 변수 | 필수 여부 | 설명 |
|---|---:|---|
| `OPENAI_API_KEY` | 필수 | 임베딩(ChromaDB), 답변 생성, Judge 평가에 모두 사용 |

## 평가 설계 (`evaluator_agent.py`)

Judge 프롬프트(`ai_answer.md`)의 출력을 `<점수>`·`<최종점수>`·`<rubric 평가>` 태그로 정규식 파싱합니다. 태그가 안 나오거나 파싱에 실패하면 임의로 통과 처리하지 않고 `overall_pass: False`, `hallucination: True`로 안전하게 실패 처리합니다 — Judge 응답 형식이 깨졌을 때 거짓 PASS가 나오지 않도록 한 설계입니다.

## 참고

- 처음 실습 시 PDF보다 `.txt`/`.md` 문서로 시작하면 오류가 적습니다.
- 문서에 없는 내용은 "제공된 문서에서는 확인할 수 없습니다"처럼 답하는 것이 정상입니다 — 근거 없이 그럴듯하게 답을 지어내지 않는 것이 RAG의 핵심입니다.
