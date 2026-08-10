"""
jira_reporter.py
- 품질평가 파이프라인 결과(FAIL 케이스)를 Jira 이슈로 자동 등록합니다. (9단계: Jira 결함관리)
- JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN/JIRA_PROJECT_KEY가 .env에 설정되지 않으면
  네트워크 호출 없이 건너뛰고 빈 리스트를 반환합니다 (로컬/실습 환경에서 안전하게 동작).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests

from config import JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY, JIRA_ISSUE_TYPE
from quality.formal_report_generator import _derive_severity

SEVERITY_TO_PRIORITY = {"Critical": "Highest", "High": "High", "Medium": "Medium", "Low": "Low"}


def is_configured() -> bool:
    return all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY])


def _auth():
    return (JIRA_EMAIL, JIRA_API_TOKEN)


def test_connection() -> dict:
    """
    Jira 인증/연결과 프로젝트 접근을 확인한다. (이슈를 만들지 않음)
    반환: {ok, message, account?, project?, project_ok?}
    """
    if not is_configured():
        missing = [n for n, v in (("JIRA_BASE_URL", JIRA_BASE_URL), ("JIRA_EMAIL", JIRA_EMAIL),
                                   ("JIRA_API_TOKEN", JIRA_API_TOKEN), ("JIRA_PROJECT_KEY", JIRA_PROJECT_KEY)) if not v]
        return {"ok": False, "message": f".env에 설정되지 않은 값: {', '.join(missing)}"}
    try:
        me = requests.get(f"{JIRA_BASE_URL}/rest/api/3/myself", auth=_auth(), timeout=10)
        if me.status_code == 401:
            return {"ok": False, "message": "인증 실패(401). 이메일/API 토큰을 확인하세요."}
        if me.status_code != 200:
            return {"ok": False, "message": f"연결 실패: {me.status_code} {me.text[:150]}"}
        account = me.json().get("displayName") or me.json().get("emailAddress")
        pr = requests.get(f"{JIRA_BASE_URL}/rest/api/3/project/{JIRA_PROJECT_KEY}", auth=_auth(), timeout=10)
        project_ok = pr.status_code == 200
        msg = f"연결 성공 — 계정: {account}, 프로젝트 {JIRA_PROJECT_KEY}: " + ("접근 가능 ✅" if project_ok else f"접근 불가({pr.status_code}) ⚠️")
        return {"ok": True, "account": account, "project": JIRA_PROJECT_KEY, "project_ok": project_ok, "message": msg}
    except Exception as e:
        return {"ok": False, "message": f"연결 오류: {e}"}


def _flatten_case(case: dict, agent_key: str, agent_label: str) -> dict:
    """{rule_based|api_based} 한쪽을 Jira 이슈 생성에 필요한 평탄한 형태로 변환한다."""
    agent_result = case.get(agent_key, {})
    eval_result = agent_result.get("evaluation_result", {})
    flat_for_severity = {
        "category": case.get("category"),
        "rule_validation": agent_result.get("rule_validation", {}),
        "evaluation_result": eval_result,
    }
    return {
        "case_id": case.get("case_id"),
        "agent_key": agent_key,
        "agent_label": agent_label,
        "category": case.get("category"),
        "user_question": case.get("user_question"),
        "ai_answer": agent_result.get("ai_answer"),
        "summary": eval_result.get("summary", ""),
        "decision": eval_result.get("overall_decision", "-"),
        "severity": _derive_severity(flat_for_severity),
    }


_AGENTS = (("rule_based", "규칙 기반"), ("api_based", "API 기반"))


def list_all_cases(pipeline_outputs: list) -> list:
    """모든 (케이스 × 챗봇) 조합을 평탄화해 반환한다. (개별 등록 선택용)"""
    return [_flatten_case(case, k, label) for case in pipeline_outputs for k, label in _AGENTS]


def _extract_fail_cases(pipeline_outputs: list) -> list:
    """중첩된 {rule_based, api_based} 결과에서 FAIL로 판정된 케이스만 평탄화해 추출합니다."""
    return [fc for fc in list_all_cases(pipeline_outputs) if fc["decision"] == "FAIL"]


def _build_issue_payload(fail_case: dict) -> dict:
    severity = fail_case["severity"]
    summary = f"[{fail_case['case_id']}][{fail_case['agent_label']}] {fail_case['category']} - {severity} 결함"
    description = (
        f"질문: {fail_case['user_question']}\n"
        f"답변: {fail_case['ai_answer']}\n"
        f"평가 요약: {fail_case['summary']}\n"
        f"심각도: {severity}"
    )
    return {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            },
            "issuetype": {"name": JIRA_ISSUE_TYPE},
            "priority": {"name": SEVERITY_TO_PRIORITY.get(severity, "Medium")},
            "labels": ["ai-quality-pipeline", severity.lower()],
        }
    }


def _post_issue(payload: dict) -> dict:
    """
    이슈 1건을 POST한다. 400(필드 스키마 불일치)이면 선택 필드(priority/labels)를 빼고 1회 재시도한다.
    (프로젝트에 priority/labels 화면 필드가 없으면 흔히 400이 나기 때문)
    반환: {ok, key?, url?, error?}
    """
    def _do(pl):
        return requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue", json=pl, auth=_auth(),
            headers={"Content-Type": "application/json"}, timeout=15,
        )
    try:
        r = _do(payload)
        if r.status_code in (200, 201):
            key = r.json().get("key")
            return {"ok": True, "key": key, "url": f"{JIRA_BASE_URL}/browse/{key}"}
        if r.status_code == 400:
            minimal = {"fields": {k: v for k, v in payload["fields"].items() if k not in ("priority", "labels")}}
            r2 = _do(minimal)
            if r2.status_code in (200, 201):
                key = r2.json().get("key")
                return {"ok": True, "key": key, "url": f"{JIRA_BASE_URL}/browse/{key}", "note": "priority/labels 제외 후 등록"}
            return {"ok": False, "error": f"400: {r.text[:200]} | 재시도: {r2.status_code} {r2.text[:150]}"}
        return {"ok": False, "error": f"{r.status_code} {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def create_single_issue(flat_case: dict) -> dict:
    """개별 케이스(FAIL이 아니어도) 1건을 Jira 이슈로 등록한다. 반환: {ok, key?, url?, error?, case_id}"""
    if not is_configured():
        return {"ok": False, "error": "Jira 미설정(.env)", "case_id": flat_case.get("case_id")}
    res = _post_issue(_build_issue_payload(flat_case))
    res["case_id"] = flat_case.get("case_id")
    if res.get("ok"):
        print(f"[Jira] 이슈 생성: {res['key']} ({flat_case.get('case_id')})")
    else:
        print(f"[Jira] 실패 ({flat_case.get('case_id')}): {res.get('error')}")
    return res


def create_issues_detailed(fail_or_cases: list) -> list:
    """여러 평탄화 케이스를 등록하고 건별 결과 목록을 반환한다. (대시보드용)"""
    return [create_single_issue(fc) for fc in fail_or_cases]


def create_issues_for_failures(pipeline_outputs: list) -> list:
    """
    FAIL 케이스를 Jira 이슈로 등록합니다. (파이프라인/CLI 호환용 — 생성된 이슈 키 목록 반환)
    Jira 미설정 또는 FAIL 케이스가 없으면 빈 리스트.
    """
    fail_cases = _extract_fail_cases(pipeline_outputs)
    if not fail_cases:
        return []
    if not is_configured():
        print(f"[Jira] 설정(JIRA_BASE_URL 등)이 없어 {len(fail_cases)}건의 FAIL 케이스 등록을 건너뜁니다.")
        return []
    return [r["key"] for r in create_issues_detailed(fail_cases) if r.get("ok")]


if __name__ == "__main__":
    import json
    from config import REPORTS_DIR

    result_file = REPORTS_DIR / "evaluation_result.json"
    if not result_file.exists():
        print(f"[Error] {result_file}이 없습니다. 먼저 quality_pipeline을 실행하세요.")
    else:
        outputs = json.loads(result_file.read_text(encoding="utf-8"))
        keys = create_issues_for_failures(outputs)
        print(f"총 {len(keys)}건의 Jira 이슈가 생성되었습니다.")
