"""pytest가 어느 위치에서 실행되든 프로젝트 루트를 sys.path에 추가해 app.*/quality.* 임포트가 되도록 합니다."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
