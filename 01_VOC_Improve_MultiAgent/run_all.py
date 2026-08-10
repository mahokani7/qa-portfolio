# =============================================
# File: run_all.py
# =============================================
# VOC 멀티에이전트 시스템의 6개 gRPC 서버를 "하나의 명령"으로 동시에 기동하는 런처
#
# 배경:
# - 각 에이전트(interpreter/retriever/summarizer/evaluator/critic/improver)는
#   자체 serve()로 독립 실행되지만, 파이프라인이 동작하려면 6001~6006 포트가
#   모두 떠 있어야 합니다. 하나라도 없으면 오케스트레이터의 insecure_channel
#   호출이 타임아웃/실패합니다.
# - 이 스크립트는 6개 서버를 단일 asyncio 이벤트 루프에서 함께 띄웁니다.
#
# 사용법:
#   1) 의존성 설치:  pip install grpcio grpcio-tools mcp openai anthropic python-dotenv
#   2) API 키 설정 (아래 중 택1):
#        - 환경변수:  OPENAI_API_KEY, ANTHROPIC_API_KEY
#        - 또는 프로젝트 루트에 .env 파일 작성 (KEY=VALUE 형식)
#   3) 서버 기동:    python run_all.py
#   4) 별도 터미널에서 MCP 서버 실행:  python main.py
#      (또는 gRPC 오케스트레이터를 직접 호출)
#
# 종료: Ctrl+C (모든 서버를 정상 종료)

# ============ 표준 라이브러리 임포트 ============
import asyncio   # 비동기 이벤트 루프
import os        # 환경변수 읽기
import sys       # sys.path 조작

# ============ 프로젝트 루트를 import 경로에 추가 ============
# 에이전트 모듈들은 "import voc_pb2" 처럼 루트 기준으로 임포트하므로,
# 어느 위치에서 실행하든 동작하도록 루트를 sys.path에 넣어줍니다.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ============ .env 파일 로드 (선택) ============
# python-dotenv가 설치돼 있으면 프로젝트 루트의 .env를 읽어 환경변수로 주입합니다.
# 설치돼 있지 않거나 .env가 없어도 조용히 넘어갑니다.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    load_dotenv(os.path.join(os.path.dirname(ROOT), ".env"))
except Exception:
    pass

# ============ gRPC 및 서비스 임포트 ============
import grpc
import voc_pb2_grpc
from agents.interpreter import InterpreterServicer
from agents.retriever import RetrieverServicer
from agents.summarizer import SummarizerServicer
from agents.evaluator import EvaluatorServicer
from agents.critic import CriticServicer
from agents.improver import ImproverServicer
from utils.validation import validate_bind_address

# ============ 서버 구성 정의 ============
# (표시 이름, add_..._to_server 등록 함수, Servicer 클래스, 바인딩 주소)
# 바인딩 주소는 *_BIND 환경변수로 오버라이드할 수 있으며,
# 기본 포트(6001~6006)는 각 에이전트의 클라이언트 기본값(localhost:600X)과 일치합니다.
SERVERS = [
    ("Interpreter", voc_pb2_grpc.add_InterpreterServicer_to_server, InterpreterServicer,
     os.environ.get("INTERPRETER_BIND", "127.0.0.1:6001")),
    ("Retriever", voc_pb2_grpc.add_RetrieverServicer_to_server, RetrieverServicer,
     os.environ.get("RETRIEVER_BIND", "127.0.0.1:6002")),
    ("Summarizer", voc_pb2_grpc.add_SummarizerServicer_to_server, SummarizerServicer,
     os.environ.get("SUMMARIZER_BIND", "127.0.0.1:6003")),
    ("Evaluator", voc_pb2_grpc.add_EvaluatorServicer_to_server, EvaluatorServicer,
     os.environ.get("EVALUATOR_BIND", "127.0.0.1:6004")),
    ("Critic", voc_pb2_grpc.add_CriticServicer_to_server, CriticServicer,
     os.environ.get("CRITIC_BIND", "127.0.0.1:6005")),
    ("Improver", voc_pb2_grpc.add_ImproverServicer_to_server, ImproverServicer,
     os.environ.get("IMPROVER_BIND", "127.0.0.1:6006")),
]


def _preflight_check() -> None:
    """
    서버 기동 전 API 키를 점검하여, 누락 시 명확한 안내를 출력합니다.

    - OPENAI_API_KEY: Interpreter/Summarizer/Evaluator/Critic 에서 필요
      (특히 Interpreter는 키가 없으면 서버 구동 자체가 실패합니다)
    - ANTHROPIC_API_KEY: Improver(정책 생성)에서 필요
    """
    missing = []
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY (요약/평가/비평/질의해석에 필요)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY (정책 개선안 생성에 필요)")

    if missing:
        print("[run_all] 경고: 다음 API 키가 설정되지 않았습니다:")
        for m in missing:
            print(f"          - {m}")
        print("[run_all] 환경변수로 설정하거나 프로젝트 루트에 .env 파일을 작성하세요.")
        print("[run_all] (OPENAI_API_KEY가 없으면 Interpreter 서버 구동이 실패할 수 있습니다.)")


async def main() -> None:
    """
    6개 gRPC 서버를 생성·기동하고, 종료 신호를 받을 때까지 함께 대기합니다.
    Ctrl+C 입력 시 모든 서버를 정상 종료(graceful stop)합니다.
    """
    # ============ 사전 점검 ============
    _preflight_check()

    # ============ 서버 생성 및 기동 ============
    started = []  # (name, server) 목록
    for name, add_fn, servicer_cls, bind in SERVERS:
        try:
            bind = validate_bind_address(bind)
            server = grpc.aio.server()
            add_fn(servicer_cls(), server)  # Servicer 인스턴스를 서버에 등록
            server.add_insecure_port(bind)  # 지정 포트에 바인딩 (TLS 미사용, 로컬 개발용)
            await server.start()
            print(f"[run_all] [{name}] gRPC server started at {bind}")
            started.append((name, server))
        except Exception as e:
            # 한 서버라도 구동 실패 시, 이미 뜬 서버를 정리하고 원인과 함께 종료
            print(f"[run_all] [{name}] 구동 실패: {e}")
            for n, s in started:
                await s.stop(grace=1)
            raise

    print(f"[run_all] 총 {len(started)}개 에이전트가 모두 기동되었습니다. 종료하려면 Ctrl+C 를 누르세요.")

    # ============ 종료 대기 ============
    try:
        # 모든 서버가 종료될 때까지 동시에 대기합니다.
        await asyncio.gather(*(s.wait_for_termination() for _, s in started))
    except asyncio.CancelledError:
        # KeyboardInterrupt 등으로 취소되면 아래 finally에서 정리합니다.
        pass
    finally:
        # ============ 정상 종료 ============
        for name, s in started:
            await s.stop(grace=3)  # 진행 중인 요청에 3초 유예 후 종료
            print(f"[run_all] [{name}] stopped")


# ============ 메인 실행 블록 ============
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[run_all] Ctrl+C 감지 — 종료합니다.")
