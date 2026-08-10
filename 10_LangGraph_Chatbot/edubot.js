import { ChatOpenAI } from "@langchain/openai";
import { DynamicTool } from "@langchain/core/tools";
import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { HumanMessage } from "@langchain/core/messages";
import * as dotenv from "dotenv";

// 환경변수 로드
dotenv.config();

// ==========================================
// 1. 에이전트 도구(Tools) 정의
// ==========================================

// 출결 규정 안내 도구
const attendanceTool = new DynamicTool({
  name: "attendance_rule_info",
  description: "훈련생의 지각, 조퇴, 결석, 공결 등 출결 규정 및 수료 기준에 대해 안내할 때 사용합니다.",
  func: async () => {
    // 실제 환경에서는 DB(MySQL 등)나 노션 API 등에서 데이터를 조회할 수 있습니다.
    return `[출결 규정 요약]
    - 지각/조퇴/외출: 1일 소정 훈련시간의 50% 미만 참여 시 결석 처리됩니다. (지각, 조퇴, 외출 3회 누적 시 1일 결석 처리)
    - 공결: 예비군/민방위 훈련, 직계가족 경조사, 취업 면접 시 증빙 서류 제출 시 출석으로 인정됩니다.
    - 수료 기준: 전체 훈련 일수의 80% 이상 출석해야 수료가 가능합니다.`;
  },
});

// 커리큘럼 일정 확인 도구
const curriculumTool = new DynamicTool({
  name: "curriculum_schedule_info",
  description: "과정의 상세 일정이나 React, Node.js, AI Agent 구축 등의 과목별 진행 시기를 확인할 때 사용합니다.",
  func: async () => {
    return `[커리큘럼 상세 안내]
    - 1~2개월차: 웹 표준 프론트엔드 기초 및 React SPA 애플리케이션 개발
    - 3~4개월차: Node.js 기반 백엔드 API 구축 및 데이터베이스 연동
    - 5개월차: LangChain, LangGraph 기반 사내 지능형 어시스턴트(AI Agent) 구축 실무
    - 6개월차: 풀스택 파이널 프로젝트 진행 및 취업/진로 포트폴리오 멘토링`;
  },
});

// ==========================================
// 2. LLM 및 에이전트 초기화
// ==========================================

// LLM 설정
const llm = new ChatOpenAI({
  model: "gpt-4o",
  temperature: 0.3,// 규정과 일정 안내를 위해 환각을 줄이면서도 상담을 위해 적절한 창의성 부여
});

const tools = [attendanceTool, curriculumTool];

// 시스템 프롬프트 설정 (페르소나 및 상담 역할 부여)
const systemMessage = `당신은 웹 프로그래머 양성 과정 훈련생들을 위한 친절하고 전문적인 사내 지능형 어시스턴트 '에듀-봇'입니다.
다음의 역할을 수행합니다:
1. 훈련생이 출결이나 일정에 대해 물어보면 제공된 도구를 사용해 정확하게 답변하세요.
2. 코딩 관련 질문이나 풀스택/프론트엔드/백엔드 개발자로서의 진로 고민을 이야기하면, 선배 개발자처럼 공감하며 실질적인 조언을 제공하세요.
3. 훈련생들이 끝까지 포기하지 않고 훈련 과정을 수료할 수 있도록 항상 격려하고 동기를 부여하는 어조를 유지하세요.`;

// LangGraph의 사전 빌드된 React Agent 생성
const agent = createReactAgent({
  llm,
  tools,
  stateModifier: systemMessage,
});

// ==========================================
// 3. 에듀-봇 실행 및 테스트
// ==========================================

async function runEduBot(query) {
  console.log(`\n🧑‍💻 훈련생 질문: ${query}`);
  
  // 에이전트 호출 (세션 유지를 위한 thread_id 설정 가능)
  const inputs = { messages: [new HumanMessage(query)] };
  const config = { configurable: { thread_id: "trainee-session-1" } };
  
  const response = await agent.invoke(inputs, config);
  const lastMessage = response.messages[response.messages.length - 1];
  
  console.log(`🤖 에듀-봇 답변:\n${lastMessage.content}\n`);
  console.log("--------------------------------------------------");
}

// 테스트 시나리오 실행
async function main() {
  // 시나리오 1: 출결 규정 확인
  await runEduBot("오늘 버스를 놓쳐서 지각할 것 같은데, 지각을 3번 하면 어떻게 되나요?");
  
  // 시나리오 2: 커리큘럼 일정 확인
  await runEduBot("우리가 배우는 과정 중에 AI Agent 구축은 몇 개월 차에 진행되나요?");
  
  // 시나리오 3: 코딩 및 진로 상담 (도구 없이 LLM 자체 역량 및 프롬프트 활용)
  await runEduBot("React 상태 관리(Redux, Zustand) 개념이 너무 헷갈려요. 제가 프론트엔드 개발자가 될 수 있을지 걱정입니다. 조언 좀 해주세요.");
}

main();