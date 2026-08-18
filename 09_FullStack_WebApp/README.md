# 풀스택 웹앱 QA — Cypress E2E + Jest

Express(MongoDB) 백엔드 + React(Vite) 프론트엔드로 만든 Todo/연락처 앱입니다. 이 프로젝트의 포트폴리오 가치는 앱 자체가 아니라 **`cypress/` E2E 테스트와 `jest`/`node:test` 단위·통합 테스트**입니다 — 전통적인 웹 QA 자동화 역량을 보여주는 항목입니다.

## Project Type

개인 프로젝트

## My Role

테스트 대상 웹앱(백엔드 API + 프론트엔드)과 Cypress/Jest 테스트 스위트를 직접 작성했습니다.

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
