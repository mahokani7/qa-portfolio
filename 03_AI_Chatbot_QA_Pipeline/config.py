import os
from pathlib import Path
from dotenv import load_dotenv

# 1. 프로젝트 기본 경로 (Root Directory) 설정
# 현재 config.py 파일의 위치를 기준으로 상위 폴더(루트)를 지정합니다.
BASE_DIR = Path(__file__).resolve().parent

# 2. .env 파일 로드 (API Key 및 환경 변수 읽기)
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    print(f"[Warning] .env file not found at {ENV_PATH}. Please check your environment variables.")

# 3. 환경 변수 및 API Key 정의
# .env 파일에 정의된 API Key들을 가져옵니다. (없을 경우 None 반환)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# 필요에 따라 다른 LLM API Key도 여기에 추가할 수 있습니다.
# ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# 4. 세부 디렉토리 경로 정의
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
DASHBOARD_DIR = BASE_DIR / "dashboard"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
# HISTORY_DIR: 파이프라인을 실행할 때마다의 결과를 타임스탬프별로 보관하는 폴더 (대시보드 히스토리 목록용)
HISTORY_DIR = REPORTS_DIR / "history"

# 테스트 케이스 파일 경로 설정
TEST_CASE_FILE = DATA_DIR / "test_cases.json"

# RAG 기준정보(지식) 파일 및 벡터 저장소 경로
# - KNOWLEDGE_UPLOAD_DIR: 사용자가 업로드한 지식 파일(.txt/.md/.docx/.pdf)을 보관하는 폴더 (여러 개 업로드 가능)
# - EVALUATION_CRITERIA_FILE: Judge Agent가 참조하는 평가 기준 JSON 파일
# - CHROMA_DB_DIR / CHROMA_COLLECTION_NAME: 청크 임베딩을 저장하는 ChromaDB 영구 저장소
KNOWLEDGE_UPLOAD_DIR = KNOWLEDGE_DIR / "uploads"
EVALUATION_CRITERIA_FILE = KNOWLEDGE_DIR / "evaluation_criteria.json"
CHROMA_DB_DIR = KNOWLEDGE_DIR / "chroma_db"
CHROMA_COLLECTION_NAME = "education_policy"

# RAG 임베딩/검색 설정
EMBEDDING_MODEL = "text-embedding-3-small"
RAG_CHUNK_SIZE = 400        # 청크 최대 길이(문자 수)
RAG_CHUNK_OVERLAP = 50      # 슬라이딩 윈도우 청크 간 겹치는 길이
RAG_TOP_K = 3                # 질문당 검색해 올 청크 개수

# 5. 결과 저장 폴더 및 필수 폴더 자동 생성
# 프로젝트 실행 시 필요한 폴더들이 없으면 자동으로 생성해줍니다.
def init_directories():
    """프로젝트에 필요한 디렉토리가 없으면 자동으로 생성하는 함수"""
    directories = [DATA_DIR, REPORTS_DIR, DASHBOARD_DIR, KNOWLEDGE_DIR, KNOWLEDGE_UPLOAD_DIR, HISTORY_DIR]
    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            print(f"[Init] Created directory: {directory}")

# config.py가 임포트될 때 자동으로 폴더 구조를 초기화합니다.
init_directories()

# 간단한 디버깅용 확인 코드 (메인으로 실행할 때만 출력)
if __name__ == "__main__":
    print("--- Configuration Loaded ---")
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"REPORTS_DIR: {REPORTS_DIR}")
    print(f"OpenAI API Key Loaded: {'Success' if OPENAI_API_KEY else 'Failed'}")