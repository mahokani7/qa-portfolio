import json
from pathlib import Path

# config/ 는 프로젝트 루트에 있다. 이 파일은 <루트>/src/utils/ 에 있으므로 두 단계 위가 루트다.
# 상대경로("config/policy_config.json")를 쓰면 실행 위치(CWD)에 따라 파일을 못 찾는다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "policy_config.json"


def load_policy(policy_name="default_pilot"):
    if not CONFIG_PATH.exists():
        # 기본값을 자동 생성해 반환하면, 실제로는 설정을 못 읽은 상태인데도
        # 평가가 그대로 진행된다. high_risk_finance(S·A 가중치 2.0)를 요청해도
        # 전부 1.0인 기본 가중치로 채점되어 점수가 조용히 달라진다.
        # 설정 누락은 감추지 말고 즉시 실패시킨다.
        raise FileNotFoundError(
            f"정책 설정 파일을 찾을 수 없습니다: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        policies = json.load(f)

    if policy_name not in policies:
        raise KeyError(
            f"'{policy_name}' 정책이 {CONFIG_PATH}에 없습니다. "
            f"사용 가능한 정책: {', '.join(sorted(policies))}"
        )

    return policies[policy_name]
