"""
logger_config.py
- API 서버 전역에서 재사용하는 로거 설정입니다.
- 콘솔 + 파일(logs/app.log)에 요청 처리 로그와 오류를 기록합니다.
"""

import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

_configured = False


def get_logger(name: str = "ai_agent_quality") -> logging.Logger:
    """이름별 로거를 반환합니다. 최초 호출 시에만 핸들러를 등록해 중복 로깅을 방지합니다."""
    global _configured
    logger = logging.getLogger(name)

    if not _configured:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)

        root_logger = logging.getLogger("ai_agent_quality")
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(stream_handler)
        root_logger.addHandler(file_handler)
        _configured = True

    return logger
