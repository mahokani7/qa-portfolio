# AI 교육과정 안내 챗봇 품질관리 자동화 파이프라인

교육과정 안내 챗봇(Service Agent)의 응답을 규칙 기반 1차 검증 + AI 평가자(Judge Agent) 2차 평가로 자동 채점하고,
결과를 JSON/CSV/Markdown 리포트와 Streamlit 대시보드로 확인하는 프로젝트입니다.
챗봇의 기준정보는 하드코딩이 아닌 업로드한 파일(.txt/.md/.docx/.pdf)을 ChromaDB에 임베딩하여 RAG 방식으로 검색합니다.

## Project Type

팀 프로젝트(4인) — `06_AI_Chatbot_QA`는 같은 팀이 이 코드를 이어받아 확장한 버전입니다.

## My Role

- 테스트 케이스 설계(`data/test_cases.json`)
- 단위·통합 테스트 수행
- 최종 발표 자료 및 데모 시나리오 제작

Service Agent·Judge Agent·규칙 검증(`service_agent.py`·`judge_agent.py`·`rule_validator.py`·`main.py`), 환경 구성(`config.py`·`knowledge_base.py`), 리포트·대시보드(`report_generator.py`·`dashboard/streamlit_app.py`)는 팀원이 담당했습니다. 근거: [`04_QA_WBS_TestPlan`](../04_QA_WBS_TestPlan/)의 업무분장 문서(`dashboard/docs/02_roles_wbs.html`).

---

## ⚠️ 압축을 풀기 전에 꼭 확인하세요

이 폴더를 zip으로 전달/전달받을 때 아래 두 가지는 **압축에서 제외하거나 전달받은 즉시 새로 만들어야** 합니다.

1. **`venv/` 폴더** — 가상환경에는 압축한 PC의 절대경로(Python 설치 위치 등)가 그대로 박혀 있어서,
   다른 PC의 다른 경로에 압축을 풀면 그대로 동작하지 않습니다. (용량도 700MB+로 커서 전달에도 비효율적입니다.)
   → 아래 "가상환경 재설정" 절차대로 **새로 생성**해야 합니다.
2. **`.env` 파일** — 여기에는 실제 OpenAI API Key가 평문으로 들어 있습니다. 이 파일이 포함된 채로 zip을 전달하면
   본인의 API 키가 그대로 노출/유출됩니다.
   → zip을 만들기 전에 `.env`를 제외하고, 전달받은 사람은 `.env.example`을 복사해 본인의 키를 입력해야 합니다.

---

## 1. 사전 준비물

- **Python 3.12** (이 프로젝트는 Python 3.12.9 기준으로 작성/테스트되었습니다. 3.11~3.12대면 대부분 호환됩니다.)
- OpenAI API Key ([https://platform.openai.com](https://platform.openai.com) 에서 발급)

## 2. 가상환경 재설정 방법 (다른 PC / 다른 경로에서 압축을 풀었을 때)

프로젝트 루트(`ai_quality_final_project/`)로 이동한 뒤 아래 순서대로 진행하세요.

### 2-1. 기존 venv 폴더 삭제 (포함되어 있었다면)

**Windows (PowerShell / cmd)**
```powershell
Remove-Item -Recurse -Force venv
```

**macOS / Linux**
```bash
rm -rf venv
```

### 2-2. 새 가상환경 생성

```bash
python -m venv venv
```
(`python`이 3.12를 가리키지 않는다면 `python3.12 -m venv venv` 처럼 버전을 명시하세요.)

### 2-3. 가상환경 활성화

**Windows (cmd)**
```cmd
venv\Scripts\activate.bat
```

**Windows (PowerShell)**
```powershell
venv\Scripts\Activate.ps1
```
> PowerShell에서 스크립트 실행이 차단된다면 관리자 권한 없이 현재 세션에만 허용:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

**macOS / Linux**
```bash
source venv/bin/activate
```

활성화되면 터미널 프롬프트 앞에 `(venv)`가 표시됩니다.

### 2-4. 패키지 설치

`requirements.txt`에 현재 프로젝트가 사용하는 전체 패키지 버전이 고정되어 있습니다.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 2-5. `.env` 파일 준비 (API Key 설정)

`.env.example`을 복사해 `.env`를 만들고, 본인의 OpenAI API Key를 입력하세요.

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux**
```bash
cp .env.example .env
```

이후 `.env` 파일을 열어 아래처럼 실제 키로 교체합니다.

```
OPENAI_API_KEY=sk-여기에-발급받은-실제-키-입력
```

### 2-6. 데이터 폴더 확인

`data/`, `data/knowledge/`, `data/knowledge/uploads/`, `reports/` 폴더는 `config.py`가 처음 임포트될 때
(=아무 스크립트나 처음 실행할 때) 자동으로 생성됩니다. 별도로 만들 필요는 없습니다.

기준정보(RAG 지식) 파일과 ChromaDB(`data/knowledge/chroma_db/`)가 zip에 이미 포함되어 있었다면 그대로 사용 가능하지만,
다른 환경으로 옮긴 뒤 검색 결과가 이상하면 대시보드의 **"🔄 크로마 DB 재생성"** 버튼으로 다시 구축하세요.

---

## 3. 실행 방법

가상환경이 활성화된(`(venv)` 표시) 상태에서 프로젝트 루트에서 실행합니다.

**전체 QA 파이프라인 실행** (테스트 케이스 순회 → 답변 생성 → 규칙 검증 → AI 평가 → 리포트 생성)
```bash
python main.py
```

**지식 베이스(RAG) 단독 테스트** (콘솔에서 파일 경로를 입력받아 ChromaDB에 추가 후 검색 시연)
```bash
python knowledge_base.py
```

**Streamlit 대시보드 실행** (지식 파일/테스트 케이스 업로드, 결과 분석)
```bash
streamlit run dashboard/streamlit_app.py
```

---

## 4. 프로젝트 구조

```
ai_quality_final_project/
├── .env                  # OpenAI API Key (직접 생성, 절대 공유 금지)
├── .env.example           # .env 템플릿
├── requirements.txt        # 고정 버전 패키지 목록
├── config.py               # 경로/환경변수/RAG 설정
├── knowledge_base.py        # 파일 업로드 → 청크 분할 → ChromaDB 임베딩/검색
├── service_agent.py         # 챗봇(RAG 기반 답변 생성)
├── rule_validator.py        # 1차 규칙 기반 검증
├── judge_agent.py           # AI 평가자(4대 지표 채점)
├── report_generator.py      # JSON/CSV/Markdown 리포트 생성
├── formal_report_generator.py  # 정식 DOCX/PDF 테스트 결과 보고서 생성 (표지/차트/결함보고서 포함)
├── main.py                  # 전체 파이프라인 실행 진입점
├── dashboard/
│   └── streamlit_app.py     # 결과 분석 대시보드 + 파일 업로드 UI + DOCX/PDF 보고서 다운로드
├── data/
│   ├── test_cases.json       # 테스트 케이스
│   └── knowledge/
│       ├── evaluation_criteria.json  # Judge Agent 평가 기준
│       ├── uploads/                  # 업로드된 지식 파일(.txt/.md/.docx/.pdf)
│       └── chroma_db/                # ChromaDB 영구 저장소 (자동 생성)
└── reports/                  # 파이프라인 실행 결과 리포트 (자동 생성)
```

---

## 5. 자주 발생하는 문제

| 증상 | 원인 / 해결 |
| --- | --- |
| `ModuleNotFoundError` | 가상환경을 활성화하지 않았거나 `pip install -r requirements.txt`를 안 한 경우입니다. |
| `[Error] OpenAI API Key가 설정되지 않았습니다` | `.env` 파일이 없거나 `OPENAI_API_KEY` 값이 비어 있습니다. |
| RAG 검색 결과가 비어 있거나 이상함 | 대시보드에서 지식 파일을 업로드한 뒤 **"🔄 크로마 DB 재생성"** 버튼을 눌러 임베딩을 반영하세요. |
| `python main.py` 실행 시 테스트 케이스 파일 없음 오류 | `data/test_cases.json`이 없는 경우입니다. 대시보드의 테스트 케이스 업로드 기능을 사용하거나 파일을 직접 준비하세요. |
| DOCX/PDF 보고서의 한글이 깨지거나 네모(□)로 나옴 | `formal_report_generator.py`는 Windows의 맑은 고딕(`C:\Windows\Fonts\malgun.ttf`) 폰트를 자동으로 찾아 사용합니다. macOS/Linux 등 이 폰트가 없는 환경에서는 한글이 정상적으로 표시되지 않을 수 있습니다. |
