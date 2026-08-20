# 풀스택 웹앱 QA — Cypress E2E + Jest

Express(MongoDB) 백엔드 + React(Vite) 프론트엔드로 만든 Todo/연락처 앱입니다. 이 프로젝트의 포트폴리오 가치는 앱 자체가 아니라 **`cypress/` E2E 테스트와 `jest`/`node:test` 단위·통합 테스트**입니다 — 전통적인 웹 QA 자동화 역량을 보여주는 항목입니다.

**왜 필요한가**: AI QA뿐 아니라 전통적인 웹 서비스 QA(단위→통합→E2E 계층 분리, API 스텁)도 같은 사고방식으로 할 수 있음을 보여주는 항목입니다.

## QA SUMMARY

| 항목 | 내용 |
|---|---|
| 프로젝트 유형 | 개인 프로젝트 |
| 내 역할 | 테스트 대상 웹앱과 Cypress/Jest 테스트 스위트 전체 |
| 테스트 범위 | node:test 단위 5건 + Jest 통합 4건 = 9건 |
| 자동화 도구 | Cypress(`cy.intercept`), Jest, node:test |
| 주요 검증 | 단위(경계값) → 통합(API) → E2E(Cypress, 네트워크 스텁) 계층별 검증 |
| 주요 결함 | 단위(`node:test`)와 통합(Jest) 러너가 분리돼 있지 않아 서로의 대상 파일을 겹쳐 실행하던 문제 |
| 개선 결과 | `test:unit`/`test:integration`으로 러너 분리 → `npm test`가 둘을 순차 실행, 9건 전부 PASS(exit 0) |
| 최종 판정 | **PASS** — 9/9 |

## Project Type

개인 프로젝트

## My Role

테스트 대상 웹앱(백엔드 API + 프론트엔드)과 Cypress/Jest 테스트 스위트를 직접 작성했습니다.

## 📌 채용담당자용 핵심 문서

- [`backend/utils/passwordStrength.test.js`](backend/utils/passwordStrength.test.js) — node:test 단위 5건(경계값 위주)
- [`backend/routes/todos.integration.test.js`](backend/routes/todos.integration.test.js) — Jest 통합 4건
- [`frontend/cypress/e2e/todo-form.cy.js`](frontend/cypress/e2e/todo-form.cy.js) — Cypress E2E 1개 시나리오(네트워크 스텁 기반)

## QA 관점의 핵심

- **무엇을 검증했는가**: 단위(비밀번호 강도 경계값) → 통합(Todo API) → E2E(폼 제출→목록 반영) 세 계층을 분리해 각 계층에서 다른 종류의 결함을 잡을 수 있는지
- **왜 검증했는가**: AI QA뿐 아니라 전통적인 웹 서비스 QA도 같은 계층 분리 사고방식으로 할 수 있음을 보여주기 위해
- **PASS/FAIL 기준**: `npm test`(node:test + Jest) exit code, Cypress는 각 명령 단계 성공 여부
- **발견한 문제**: 단위(`node:test`)와 통합(Jest) 러너가 분리돼 있지 않아 서로의 대상 파일을 겹쳐 실행하던 문제
- **어떻게 분석했는가**: 두 러너가 같은 glob 패턴으로 파일을 잡아 중복 실행되는 것을 `package.json` 스크립트 정의에서 확인
- **재검증**: `test:unit`/`test:integration`으로 러너를 분리하고 `npm test`가 순차 실행하도록 수정 — node:test 5건 + Jest 4건 = 9건 전부 PASS(exit 0)

> **Cypress에 대한 참고**: E2E 시나리오는 현재 1개(`todo-form.cy.js` — 폼 입력→API 호출→목록 반영, `cy.intercept`로 네트워크 스텁)이며, 별도로 저장된 Cypress 실행 로그/리포트 파일은 없습니다(코드 자체가 증거). node:test·Jest의 9건은 위 두 테스트 파일에서 직접 확인한 정확한 수치입니다.

---

## 🔧 Technical Reference

아래는 실행 방법·코드 구조 등 기술적 상세입니다. 채용담당자는 위 내용만으로 프로젝트를 이해할 수 있습니다.

## 프로젝트 구조

```text
backend/
  index.js              # Express 서버 엔트리포인트
  socket.js             # Socket.IO 초기화
  schema.sql
  routes/
    todos.js             # Todo API
    todos.integration.test.js   # Jest 통합 테스트
    contacts.js
    transfers.js
    users.js
  utils/
    passwordStrength.js
    passwordStrength.test.js    # node:test 단위 테스트

frontend/
  src/                   # React 컴포넌트
  cypress/
    e2e/
      todo-form.cy.js    # Cypress E2E 테스트
```

## 실행 방법

```powershell
cd backend
npm install
copy .env.example .env
npm start                # Express API (schema.sql로 DB 먼저 생성)
npm test                 # 단위(node:test) + 통합(Jest) — exit 0

cd ..\frontend
npm install
npm run dev              # React/Vite 개발 서버
npx cypress open         # E2E 테스트
```

## 테스트 설계

- **Cypress E2E** (`todo-form.cy.js`): `cy.intercept()`로 백엔드 API를 네트워크 레벨에서 스텁 처리해, 실제 DB 연결 없이도 프론트엔드 동작(폼 입력 → API 호출 → 목록 반영)을 독립적으로 검증합니다.
- **node:test 단위 테스트** (`passwordStrength.test.js`): 빈 값·최대 길이 초과·특수문자 누락·대소문자/숫자 누락 등 경계값 위주로 설계했습니다.
- **Jest 통합 테스트** (`todos.integration.test.js`): 단위 테스트와 러너를 분리해(`test:unit` / `test:integration`) 두 러너가 서로의 대상 파일을 중복 실행하지 않도록 구성했습니다.

## 참고

MongoDB가 없으면 백엔드가 `process.exit(1)`로 종료합니다. 테스트는 실제 DB 대신 모델을 모킹하므로 DB 없이도 통과합니다.
