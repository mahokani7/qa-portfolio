

# =============================================
# File: settings.py
# =============================================
# 시스템 설정 및 API 클라이언트 초기화
# 환경변수를 통한 설정 오버라이드 지원
# 
# 주요 설정:
# - AI 모델 API 키 및 모델명 설정
# - CSV 파일 경로 설정
# - OpenAI/Anthropic 클라이언트 초기화

# ============ 표준 라이브러리 임포트 ============
# 운영체제 관련 기능 (환경변수 읽기 등)
import os

# 어떤 진입점(main.py, 개별 agent, run_all.py)으로 실행하더라도 동일하게
# 프로젝트 루트의 .env를 먼저 읽습니다.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_project_root, ".env"))
    load_dotenv(os.path.join(os.path.dirname(_project_root), ".env"))
except Exception:
    pass

# ============ API 키 및 모델 설정 ============
# 모든 설정은 환경변수를 통해 오버라이드할 수 있습니다
# 이렇게 하면 코드 수정 없이 설정을 변경할 수 있어 배포 및 테스트가 용이합니다

# ============ AI 모델 API 키 설정 ============
# 환경변수에서 API 키를 읽어옵니다
# 환경변수가 설정되지 않았으면 None이 되어 해당 클라이언트는 사용할 수 없습니다
# ---- AI 모델 및 API 키 설정 (환경변수로 오버라이드 가능) ----
# OpenAI API 키 (환경변수에서 읽어옴, 없으면 None)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# Anthropic API 키 (환경변수에서 읽어옴, 없으면 None)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# ============ AI 모델명 설정 ============
# 각 작업 유형에 맞는 모델을 선택할 수 있습니다
# 환경변수로 오버라이드 가능하여 모델 변경이 용이합니다
# 사용할 AI 모델 설정 (환경변수로 오버라이드 가능)
# VOC 요약용 모델 (기본값: gpt-4o-mini)
# 요약 작업은 OpenAI 모델을 사용합니다. 환경변수 A2A_MODEL_SUMMARY로 오버라이드하세요.
MODEL_SUMMARY = os.environ.get("A2A_MODEL_SUMMARY", "gpt-4o-mini")
# 정책 개선안 생성용 모델 (계정 Models API에서 확인된 안정 모델)
# 정책 개선안 생성은 Anthropic Claude 모델을 사용합니다
MODEL_POLICY  = os.environ.get("A2A_MODEL_POLICY", "claude-sonnet-4-6")

# ============ 파일 경로 설정 ============
# VOC 데이터가 저장된 CSV 파일의 기본 경로를 설정합니다
# 환경변수로 오버라이드 가능하여 다른 환경에서 다른 경로를 사용할 수 있습니다

# 기본 VOC CSV 파일 경로 (환경변수로 오버라이드 가능)
# 프로젝트 루트 디렉토리를 기준으로 상대 경로를 사용합니다
# 이 파일(settings.py)이 utils/ 디렉토리에 있으므로, 상위 디렉토리로 올라가서 voc.csv를 찾습니다
_default_csv_path = os.path.join(_project_root, "voc.csv")
DEFAULT_CSV = os.environ.get("A2A_VOC_CSV", _default_csv_path)

# 요청 전체 제한과 개별 외부 호출 제한을 분리합니다.
TOTAL_TIMEOUT = float(os.environ.get("A2A_TOTAL_TIMEOUT", "180"))
STAGE_TIMEOUT = float(os.environ.get("A2A_STAGE_TIMEOUT", "45"))
# SDK 기본 재시도(보통 2회)가 gRPC 단계 제한 안에서 중첩되어 오류 응답을 오래
# 기다리는 문제를 줄입니다. 정상적인 일시 오류는 한 번만 재시도합니다.
API_TIMEOUT = min(
    STAGE_TIMEOUT,
    float(os.environ.get("A2A_API_TIMEOUT", str(STAGE_TIMEOUT))),
)
API_MAX_RETRIES = max(0, min(2, int(os.environ.get("A2A_API_MAX_RETRIES", "1"))))

# ============ AI 클라이언트 초기화 ============
# AI SDK를 지연 로딩 방식으로 임포트합니다
# 이렇게 하면 SDK가 설치되지 않은 환경에서도 모듈 임포트가 실패하지 않습니다

# ---- AI SDK 클라이언트 초기화 (지연 로딩 방식) ----
# OpenAI 클라이언트 초기화 시도
# try-except를 사용하여 SDK가 없어도 에러가 발생하지 않도록 합니다
try:
    from openai import AsyncOpenAI  # type: ignore
except Exception:
    # OpenAI SDK가 설치되지 않았거나 import 실패 시 None으로 설정
    # 이 경우 openai_client도 None이 되어 OpenAI 기능을 사용할 수 없습니다
    AsyncOpenAI = None  # type: ignore

# Anthropic 클라이언트 초기화 시도
# try-except를 사용하여 SDK가 없어도 에러가 발생하지 않도록 합니다
try:
    from anthropic import AsyncAnthropic  # type: ignore
except Exception:
    # Anthropic SDK가 설치되지 않았거나 import 실패 시 None으로 설정
    # 이 경우 claude_client도 None이 되어 Anthropic 기능을 사용할 수 없습니다
    AsyncAnthropic = None  # type: ignore


# ============ 클라이언트 인스턴스 생성 ============
# 실제로 사용할 수 있는 클라이언트 인스턴스를 생성합니다
# 조건부 생성: SDK 클래스와 API 키가 모두 존재할 때만 인스턴스를 생성합니다

# 실제 사용 가능한 클라이언트 인스턴스 생성
# API 키와 SDK가 모두 존재할 때만 클라이언트 생성, 아니면 None
# 조건부 표현식을 사용하여 간결하게 작성했습니다
openai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    timeout=API_TIMEOUT,
    max_retries=API_MAX_RETRIES,
) if (AsyncOpenAI and OPENAI_API_KEY) else None
claude_client = AsyncAnthropic(
    api_key=ANTHROPIC_API_KEY,
    timeout=API_TIMEOUT,
    max_retries=API_MAX_RETRIES,
) if (AsyncAnthropic and ANTHROPIC_API_KEY) else None

# ============ 모듈 초기화 완료 ============
# 이 시점에서 모든 설정이 완료되었습니다
# 다른 모듈에서 이 모듈을 임포트하면 설정된 값들을 사용할 수 있습니다
