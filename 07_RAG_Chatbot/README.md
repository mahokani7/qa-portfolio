# RAG 챗봇 — 문서 기반 근거 답변 + 품질평가

LLM이 아는 척 답하지 않고, 업로드한 문서에서 근거를 찾아 그 근거와 함께 답하도록 만든 RAG(Retrieval-Augmented Generation) 챗봇입니다. 문서 업로드 → 분할 → 임베딩·ChromaDB 저장 → 질문 시 유사 문서 검색 → 근거 기반 답변 흐름이며, LLM Judge가 답변 품질(이해도·정확성·관련성·표현성)을 자동 평가합니다.

**왜 필요한가**: 일반 LLM 챗봇은 모르는 내용도 그럴듯하게 답하는 환각 위험이 있습니다. 답변 근거를 실제 업로드 문서로 제한하고, 그 결과를 LLM Judge로 다시 채점해 "문서에 없으면 모른다고 답하는가"를 검증 가능하게 만드는 것이 목표입니다.

## QA SUMMARY

| 항목 | 내용 |
|---|---|
| 프로젝트 유형 | 개인 프로젝트 |
| 내 역할 | RAG 파이프라인, Judge Agent, 평가 실행·리포트, Streamlit UI 전체 |
| 테스트 범위 | 별도 pytest 스위트 없음 — `run_tests.py`가 `test_cases.json`을 순회하며 실제 LLM 호출로 채점(OpenAI API 키 필요, 이번 검증에서는 키 없이 모듈 import까지만 확인) |
| 자동화 도구 | `run_tests.py`, `run_evaluation.py` (LLM Judge 채점) |
| 주요 검증 | 정상 질문(문서 기반 답변), 문서 외 질문(모른다고 답하는지), Judge 응답 형식이 깨졌을 때 안전하게 실패 처리하는지 |
| 주요 결함 | 이 프로젝트 자체에서 발견한 결함은 없습니다 |
| 개선 결과 | 해당 없음 |
| 최종 판정 | 구조·의존성 확인 완료(API 키 있어야 전체 파이프라인 실행 가능) |

## Project Type

개인 프로젝트

## My Role

- RAG 파이프라인(`ingest.py`, `rag_service.py`) 설계·구현
- Judge Agent(`evaluator_agent.py`) 설계 — 루브릭 평가·감점 평가·최종 점수 산출 로직
- 답변 품질 평가 실행 및 리포트 생성(`run_evaluation.py`, `run_tests.py`)
- Streamlit UI(챗봇/문서관리/품질평가 3탭) 구현

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
