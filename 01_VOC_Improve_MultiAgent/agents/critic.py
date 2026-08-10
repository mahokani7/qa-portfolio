# ================================================
# File: critic.py
# Role: 요약/정책 비평 에이전트 + gRPC 서버 
# Port (default bind): 127.0.0.1:6005
# ================================================

# ============ 표준 라이브러리 및 타입 힌트 ============
# Python 3.7+ 호환성을 위한 annotations 가져오기
from __future__ import annotations

# 운영체제 관련 기능 (환경변수 읽기 등)
import os
# 비동기 프로그래밍 지원
import asyncio
# 데이터 클래스 정의 (타입 안전한 구조체)
from dataclasses import dataclass
# 타입 힌트를 위한 타입 정의들
from typing import List

# ============ Protocol Buffers 생성 파일 임포트 ============
# voc.proto 파일로부터 생성된 메시지 및 서비스 정의
import grpc
import voc_pb2
import voc_pb2_grpc

# ============ 프로젝트 내부 모듈 임포트 ============
# 요약용 모델 및 OpenAI 클라이언트
from utils.settings import MODEL_SUMMARY, openai_client
# JSON 파싱 유틸리티 함수
from utils.json_utils import extract_json
from utils.validation import validate_bind_address

_DEFAULT_CLIENT = object()


# ============ 비즈니스 로직 ============
# 요약문/정책문을 검토하여 수정 필요 여부와 수정 지침을 생성하는 에이전트
# --------------------------------
# 비즈니스 로직
# --------------------------------

# ============ 비평 결과 데이터 클래스 ============
@dataclass
class CriticResult:
    """
    Critic의 검토 결과를 담는 데이터 클래스입니다.
    """
    need_refine: bool      # 개선 필요 여부
    edits: List[str]       # 수정 지침 리스트
    ask_more_samples: bool # 추가 샘플 필요 여부


# ============ Critic 에이전트 클래스 ============
class CriticAgent:
    """
    요약문/정책문을 검토하여 수정 필요 여부와 수정 지침을 생성
    """

    # ============ 초기화 메서드 ============
    def __init__(self, model: str | None = None, client=_DEFAULT_CLIENT):
        """
        CriticAgent 인스턴스를 초기화합니다.
        
        Args:
            model: 사용할 OpenAI 모델명 (None이면 settings.MODEL_SUMMARY 사용)
        """
        self.model = model or MODEL_SUMMARY
        self.client = openai_client if client is _DEFAULT_CLIENT else client

    # ============ 문서 검토 메서드 ============
    async def review(self, doc: str, role: str) -> CriticResult:
        """
        요약문 또는 정책 개선안을 검토하여 수정 필요 여부와 수정 지침을 생성합니다.
        
        LLM을 사용하여 문서의 명확성, 일관성, 구체성, 실행 가능성을 평가하고,
        개선이 필요한 경우 구체적인 수정 지침을 제공합니다.
        
        Args:
            doc: 검토할 문서 텍스트 (요약문 또는 정책 개선안)
            role: 문서 역할 ("summary" | "policy")
            
        Returns:
            CriticResult: 검토 결과 (need_refine, edits, ask_more_samples)
            
        Raises:
            RuntimeError: OpenAI 클라이언트가 초기화되지 않았을 때
        """
        # ============ OpenAI 클라이언트 검증 ============
        # OpenAI 클라이언트가 초기화되지 않았으면 에러를 발생시킵니다
        if self.client is None:
            raise RuntimeError("OpenAI client is not initialized (check OPENAI_API_KEY)")

        # ============ 역할 설명 결정 ============
        # 역할에 따라 프롬프트에 사용할 설명을 결정합니다
        role_desc = "요약문" if role == "summary" else "정책 개선안"

        # ============ 프롬프트 구성 ============
        # LLM에게 문서를 검토하고 수정 지침을 생성하도록 지시하는 프롬프트를 작성합니다
        prompt = f"""
다음 {role_desc}를 검토한 뒤, 수정이 필요한지 판단하고 구체적인 수정 지침을 제안해라.

[텍스트]
{doc}

[근거 준수 규칙]
- 사용자 질문과 검색 원문이 있으면 이를 최우선 근거로 삼아라.
- 선택 요약이 질문과 다른 문제를 중심으로 삼았는지 먼저 검사해라.
- 원문에 없는 채널, 원인, 사례, 현재 수치의 추가를 요구하지 마라.
- 구체성이 부족해도 근거가 없다면 수치를 만들어 넣으라고 지시하지 마라.

반드시 JSON 형식만 출력해라.

{{
  "need_refine": true,
  "edits": [
    "첫 문단에서 불필요한 반복을 줄여라.",
    "원문 근거 안에서 문제와 영향을 더 명확히 표현해라."
  ],
  "ask_more_samples": false
}}
"""

        # ============ OpenAI API 호출 ============
        # Chat Completions API를 사용하여 문서를 검토합니다
        resp = await self.client.chat.completions.create(
            model=self.model,  # 사용할 모델명
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 VOC 요약 및 정책 개선안을 검토하는 Critic Agent이다. "
                        "텍스트의 명확성, 일관성, 구체성, 실행 가능성을 기준으로 개선이 필요한지 판단하고 "
                        "JSON 형식으로만 결과를 반환해라."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt.strip(),  # 사용자 프롬프트
                },
            ],
            temperature=0.2,  # 낮은 온도로 일관된 결과 생성
        )

        # ============ 응답 파싱 ============
        # SDK 버전별 content 접근 안전 처리
        # 응답 구조가 복잡하므로 안전하게 접근합니다
        choice_msg = resp.choices[0].message
        text = getattr(choice_msg, "content", None)
        # 딕셔너리인 경우 get 메서드 사용
        if text is None and isinstance(choice_msg, dict):
            text = choice_msg.get("content", "")

        # ============ JSON 파싱 ============
        # LLM 응답에서 JSON 블록을 추출하고 파싱합니다
        data = extract_json(text or "") or {}

        # ============ 결과 추출 ============
        # 파싱된 데이터에서 각 필드를 추출합니다
        need_refine = bool(data.get("need_refine", False))  # 개선 필요 여부
        edits = data.get("edits") or []  # 수정 지침 리스트
        # 리스트가 아니면 빈 리스트로 변환
        if not isinstance(edits, list):
            edits = []
        # 모든 편집 지침을 문자열로 변환
        edits = [str(e) for e in edits]

        ask_more = bool(data.get("ask_more_samples", False))  # 추가 샘플 필요 여부

        # ============ 결과 반환 ============
        # 추출한 정보를 CriticResult 객체로 만들어 반환합니다
        return CriticResult(
            need_refine=need_refine,
            edits=edits,
            ask_more_samples=ask_more,
        )


# ============ gRPC 서비스 구현 ============
# Protocol Buffers로 정의된 서비스를 구현하는 클래스
# 클라이언트의 RPC 요청을 받아 CriticAgent의 비즈니스 로직을 실행합니다
# --------------------------------
# gRPC Servicer
# --------------------------------

class CriticServicer(voc_pb2_grpc.CriticServicer):
    """
    Critic gRPC 서비스를 구현하는 클래스입니다.
    
    voc_pb2_grpc.CriticServicer를 상속받아
    Protocol Buffers로 정의된 RPC 메서드들을 구현합니다.
    """
    # ============ 초기화 메서드 ============
    def __init__(self, agent: CriticAgent | None = None):
        """
        CriticServicer 인스턴스를 초기화합니다.
        비즈니스 로직을 담당하는 CriticAgent를 생성합니다.
        """
        self.critic = agent or CriticAgent()

    # ============ Review RPC 구현 ============
    async def Review(self, request, context):
        """
        Review RPC를 구현합니다.
        
        클라이언트로부터 문서와 역할을 받아 검토하고,
        role이 "summary"인 경우 Improver를 직접 호출하여 다음 단계로 진행합니다.
        role이 "policy"인 경우 최종 결과를 반환합니다.
        
        Args:
            request: ReviewReq 메시지 (doc, role 포함)
            context: gRPC 서비스 컨텍스트 (에러 처리 등에 사용)
            
        Returns:
            ReviewRes: 검토 결과를 포함한 응답 메시지
        """
        try:
            role = request.role or "summary"

            # ============ 문서 검토 ============
            # Critic은 "문서 검토(수정 필요 여부 + 수정 지침 생성)"만 담당하는 순수 에이전트입니다.
            # 다음 단계 호출(요약→Improver 등)은 오케스트레이터(run_pipeline)가 단일 경로로
            # 수행하므로, 여기서는 검토 결과만 반환합니다.
            result: CriticResult = await self.critic.review(
                request.doc,                    # 검토할 문서 텍스트
                role,                           # 문서 역할
            )

            # ============ 응답 메시지 생성 및 반환 ============
            # 검토 결과(need_refine, edits, ask_more_samples)를 반환합니다.
            # policy/summary 에코 필드는 호환성을 위해 유지하되, 하위 에이전트를 호출해
            # 생성하지 않습니다.
            return voc_pb2.ReviewRes(
                need_refine=result.need_refine,              # 개선 필요 여부
                edits=result.edits,                          # 수정 지침 리스트
                ask_more_samples=result.ask_more_samples,    # 추가 샘플 필요 여부
                policy=request.doc if role == "policy" else "",   # 검토 대상 정책 에코 (참고용)
                summary=request.doc if role == "summary" else "", # 검토 대상 요약 에코 (참고용)
            )
        except Exception as e:
            # ============ 에러 처리 ============
            # 예외 발생 시 gRPC 에러로 변환하여 클라이언트에 전달합니다
            await context.abort(grpc.StatusCode.INTERNAL, f"Critic error: {e}")


# ============ gRPC 서버 실행 함수 ============
# 이 모듈을 직접 실행할 때 gRPC 서버를 시작하는 함수
# --------------------------------
# gRPC Server Runner
# --------------------------------

async def serve() -> None:
    """
    Critic gRPC 서버를 시작합니다.
    
    환경변수 CRITIC_BIND에서 엔드포인트를 읽어옵니다.
    기본값은 "127.0.0.1:6005"입니다 (로컬 전용).
    """
    # ============ 엔드포인트 설정 ============
    # 환경변수에서 엔드포인트를 읽어오고, 없으면 기본값을 사용합니다
    bind = validate_bind_address(os.environ.get("CRITIC_BIND", "127.0.0.1:6005"))

    # ============ gRPC 서버 생성 ============
    # 비동기 gRPC 서버 인스턴스를 생성합니다
    server = grpc.aio.server()
    # ============ 서비스 등록 ============
    # CriticServicer를 서버에 등록하여 RPC 요청을 처리할 수 있도록 합니다
    voc_pb2_grpc.add_CriticServicer_to_server(CriticServicer(), server)
    # ============ 포트 바인딩 ============
    # 서버를 지정된 엔드포인트에 바인딩합니다 (TLS 없이)
    server.add_insecure_port(bind)

    # ============ 서버 시작 로그 ============
    # 서버가 시작되었음을 콘솔에 출력합니다
    print(f"[Critic] gRPC server started on {bind}")
    # ============ 서버 시작 및 대기 ============
    # 서버를 시작하고 종료 신호를 받을 때까지 대기합니다
    await server.start()
    # 서버가 종료될 때까지 무한 대기합니다 (Ctrl+C로 종료 가능)
    await server.wait_for_termination()


# ============ 메인 실행 블록 ============
# 스크립트가 직접 실행될 때만 서버를 시작합니다
if __name__ == "__main__":
    # asyncio.run()을 사용하여 비동기 서버를 실행합니다
    asyncio.run(serve())
