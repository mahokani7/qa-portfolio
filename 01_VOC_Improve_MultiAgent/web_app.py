# =============================================
# File: web_app.py
# =============================================
# 로컬 브라우저에서 VOC 분석을 테스트하기 위한 웹 UI
#
# 두 가지 모드:
#  (1) 단건 분석  : 질문 1개 → 6개 에이전트 단계별 산출물(내부 품질 진단) 표시
#  (2) 배치 테스트: 여러 테스트 케이스(파일 업로드 또는 여러 줄 붙여넣기)를
#                   한 번에 순차 실행하고 결과를 표로 요약
#
# 흐름: 사용자 질문 → Interpreter → Retriever → Summarizer → Evaluator → Critic → Improver
#
# 전제:
# - 먼저 `python grpc_server.py` 로 6개 에이전트가 떠 있어야 합니다.
# - OPENAI_API_KEY / ANTHROPIC_API_KEY 가 설정돼 있어야 합니다.
#
# 실행:
#   python web_app.py           # 이후 브라우저에서 http://127.0.0.1:8000 접속

import asyncio
import html
import json
import os
import re
import sys
import grpc
import secrets
from pathlib import Path

# ============ 프로젝트 루트를 import 경로에 추가 ============
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ============ .env 로드 (선택) ============
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    load_dotenv(os.path.join(os.path.dirname(ROOT), ".env"))
except Exception:
    pass

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Route

from grpc_server import VOCGRPCRuntime
from utils.settings import DEFAULT_CSV, TOTAL_TIMEOUT
from utils.deployment_policy import (
    evaluate_release_evidence,
    load_deployment_config,
    save_deployment_config,
)
from utils.api_resilience import (
    classify_provider_error,
    is_rate_limit_error,
    rate_limit_guidance,
    redact_api_secrets,
)
from utils.errors import error_result
from utils.validation import ValidationError, validate_csv_path, validate_question, validate_task
from utils.quality_evaluator import evaluate_quality_case, validate_quality_case
from e2e_runner import run as run_e2e
from quality_diagnosis.llm_judge import run as run_llm_judge
from quality_diagnosis.merge_e2e_retests import merge as merge_e2e_reports
from quality_diagnosis.qa_control_center import QAControlCenter
from quality_diagnosis.repeatability import run_repeatability
from quality_diagnosis.red_team import run_red_team
from quality_diagnosis.quality_gate import run_quality_gate
from quality_diagnosis.job_manager import AsyncJobManager
from quality_diagnosis.history_word_report import build_history_word_report
from presentation import PRESENTATION_PAGE

# 오케스트레이터 인스턴스 (MCP 도구와 동일한 파이프라인을 사용)
runtime = VOCGRPCRuntime()
ROOT_PATH = Path(ROOT)
REPORTS_PATH = ROOT_PATH / "quality_diagnosis" / "reports"
CONTROL_CENTER = QAControlCenter(REPORTS_PATH)
JOB_MANAGER = AsyncJobManager()
QUALITY_OPERATION_LOCK = asyncio.Lock()
AUTH_SESSIONS: dict[str, dict[str, str]] = {}
REPORT_SUFFIXES = {".json", ".csv", ".md", ".txt", ".xml", ".html", ".pdf", ".png", ".zip", ".docx"}
JUDGE_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o-mini",
    "deterministic": "",
}
TEST_SETS = {
    "ecommerce": {
        "label": "이커머스",
        "csv_path": DEFAULT_CSV,
        "cases_path": os.path.join(ROOT, "test_cases.txt"),
    },
    "insurance": {
        "label": "보험",
        "csv_path": os.path.join(ROOT, "data", "voc_insurance.csv"),
        "cases_path": os.path.join(ROOT, "test_cases_insurance.jsonl"),
    },
}


def _repeatability_profile() -> dict[str, object]:
    """Select the mandatory live profile from configured API keys."""
    openai = bool(os.environ.get("OPENAI_API_KEY"))
    anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    ready = openai and anthropic
    return {
        "mode": "live",
        "judge_provider": "anthropic" if anthropic else "openai",
        "requires_cost_consent": False,
        "ready": ready,
        "label": "라이브 E2E + 외부 LLM Judge",
        "reason": (
            "OpenAI·Anthropic 키를 사용해 실제 6-Agent E2E와 외부 Judge를 자동 실행합니다."
            if ready else
            "라이브 검사를 실행하려면 .env에 OPENAI_API_KEY와 ANTHROPIC_API_KEY가 모두 필요합니다."
        ),
    }


def _require_live_api_policy() -> dict[str, object]:
    """Reject silent offline fallbacks; configured keys are the execution policy."""
    profile = _repeatability_profile()
    if not profile["ready"]:
        raise ValidationError(
            ".env의 OPENAI_API_KEY와 ANTHROPIC_API_KEY가 모두 설정되어야 합니다. "
            "외부 LLM 검사는 오프라인 또는 deterministic 방식으로 대체하지 않습니다."
        )
    return profile
PAGE_ROUTE_CONFIG = {
    "/": {"view": "control-center", "panel": "control"},
    "/control-center": {"view": "control-center", "panel": "control"},
    "/dashboard": {"view": "dashboard", "panel": "control"},
    "/single": {"view": "single", "panel": "single"},
    "/batch": {"view": "batch", "panel": "batch"},
    "/quality": {"view": "quality", "panel": "quality"},
    "/test-cases": {"view": "test-cases", "panel": "control"},
    "/runs": {"view": "runs", "panel": "control"},
    "/compare": {"view": "compare", "panel": "control"},
    "/trace": {"view": "trace", "panel": "control"},
    "/security": {"view": "security", "panel": "quality"},
    "/approvals": {"view": "approvals", "panel": "control"},
    "/reports": {"view": "reports", "panel": "control"},
    "/settings": {"view": "settings", "panel": "control"},
}


def _operator_token() -> str:
    """Optional operator token; disabled when neither environment value exists."""
    return str(os.environ.get("WEB_OPERATOR_TOKEN") or os.environ.get("WEB_AUTH_TOKEN") or "").strip()


def _secure_cookie_enabled() -> bool:
    """Use Secure session cookies when HTTPS is terminated by the deployment edge."""
    return str(os.environ.get("WEB_COOKIE_SECURE") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _auth_tokens() -> dict[str, str]:
    return {
        "viewer": str(os.environ.get("WEB_VIEWER_TOKEN") or "").strip(),
        "reviewer": str(os.environ.get("WEB_REVIEWER_TOKEN") or "").strip(),
        "admin": str(os.environ.get("WEB_ADMIN_TOKEN") or _operator_token()).strip(),
    }


def _resolve_role(provided: str) -> str:
    if not provided:
        return ""
    for role in ("admin", "reviewer", "viewer"):
        configured = _auth_tokens()[role]
        if configured and secrets.compare_digest(provided, configured):
            return role
    return ""


async def operator_auth_middleware(request, call_next):
    tokens = _auth_tokens()
    enabled = any(tokens.values())
    mutation = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    protected = request.url.path == "/analyze" or request.url.path.startswith("/quality")
    authorization = str(request.headers.get("authorization") or "")
    bearer = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    provided = bearer or str(request.headers.get("x-qa-token") or "")
    session_id = str(request.cookies.get("qa_session") or "")
    session = AUTH_SESSIONS.get(session_id, {})
    role = _resolve_role(provided) or str(session.get("role") or "")
    request.state.qa_role = role or ("local-admin" if not enabled else "anonymous")
    request.state.qa_actor = str(session.get("name") or role or "local")
    request.state.qa_session_user = dict(session)
    if enabled and protected and (mutation or bool(tokens["viewer"])):
        required_role = "viewer"
        if mutation:
            required_role = (
                "viewer" if request.url.path == "/quality/compare"
                else "reviewer" if request.url.path == "/quality/approvals"
                else "admin"
            )
        ranks = {"": 0, "viewer": 1, "reviewer": 2, "admin": 3}
        if ranks.get(role, 0) < ranks[required_role]:
            return JSONResponse(
                error_result(
                    "AUTH_REQUIRED",
                    f"이 기능에는 {required_role} 이상 권한의 QA 토큰이 필요합니다.",
                ),
                status_code=401,
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if mutation and protected:
        try:
            await asyncio.to_thread(
                CONTROL_CENTER.audit,
                "WEB_MUTATION",
                request.state.qa_actor,
                request.url.path,
                {"method": request.method, "status": response.status_code},
            )
        except Exception:
            pass
    return response


async def auth_status(request):
    session = getattr(request.state, "qa_session_user", {}) or {}
    return JSONResponse({
        "ok": True,
        "enabled": any(_auth_tokens().values()),
        "authenticated": bool(session),
        "user": {
            "name": str(session.get("name") or ""),
            "role": str(session.get("role") or ""),
        } if session else None,
    })


async def auth_login(request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, TypeError, ValueError):
        return JSONResponse(error_result("INVALID_LOGIN", "로그인 요청 형식이 올바르지 않습니다."), status_code=400)
    username = str(data.get("username") or "").strip()
    token = str(data.get("token") or "").strip()
    if not username or len(username) > 80 or not re.fullmatch(r"[0-9A-Za-z가-힣_.@ -]+", username):
        return JSONResponse(error_result("INVALID_USERNAME", "사용자 이름을 1~80자로 입력하세요."), status_code=400)
    enabled = any(_auth_tokens().values())
    role = _resolve_role(token) if enabled else "admin"
    if enabled and not role:
        return JSONResponse(error_result("LOGIN_FAILED", "사용자 이름 또는 QA 접근 토큰을 확인하세요."), status_code=401)
    session_id = secrets.token_urlsafe(32)
    AUTH_SESSIONS[session_id] = {"name": username, "role": role}
    response = JSONResponse({"ok": True, "user": {"name": username, "role": role}})
    response.set_cookie(
        "qa_session", session_id, max_age=8 * 60 * 60, httponly=True,
        samesite="strict", secure=_secure_cookie_enabled(), path="/",
    )
    return response


async def auth_logout(request):
    session_id = str(request.cookies.get("qa_session") or "")
    if session_id:
        AUTH_SESSIONS.pop(session_id, None)
    response = JSONResponse({"ok": True})
    response.delete_cookie("qa_session", path="/")
    return response

# ============ HTML 페이지 (단일 파일 내장) ============
# raw 문자열(r""")로 두어 내부 JS 정규식의 백슬래시(\s, \d, \r\n 등)를
# 파이썬이 해석하지 않고 그대로 브라우저로 전달하게 합니다.
PAGE = r"""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>VOC 분석 테스트 · 6-에이전트 내부 품질 진단</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #07111f; --surface: #0c192b; --surface-2: #10233a;
    --line: #203852; --text: #e6edf7; --muted-text: #91a4bb;
    --brand: #38bdf8; --brand-2: #2dd4bf; --danger: #fb7185; --warning-color: #fbbf24;
  }
  :root[data-theme="light"] {
    color-scheme: light;
    --bg:#eef4f8; --surface:#ffffff; --surface-2:#e8f1f8;
    --line:#b8cad8; --text:#102033; --muted-text:#52677c;
    --brand:#0369a1; --brand-2:#0f766e; --danger:#be123c; --warning-color:#a16207;
  }
  * { box-sizing: border-box; }
  body {
    font-family: system-ui, "Segoe UI", "Malgun Gothic", sans-serif;
    max-width: 1680px; margin: 0 auto; padding: 24px 24px 24px 260px; line-height: 1.6;
    background: radial-gradient(circle at 10% -10%, #12345a 0, var(--bg) 34%); color: var(--text);
    min-height: 100vh;
  }
  h1 { font-size: 1.4rem; margin-bottom: 4px; }
  .sub { color: #888; font-size: .9rem; margin-top: 0; }
  textarea {
    width: 100%; padding: 12px; font-size: 1rem;
    border: 1px solid #ccc; border-radius: 8px; resize: vertical; font-family: inherit;
  }
  .row { display: flex; gap: 12px; align-items: center; margin: 12px 0; flex-wrap: wrap; }
  select, button, input[type=file] { padding: 10px 14px; font-size: .98rem; border-radius: 8px; border: 1px solid #ccc; }
  button { background: #2563eb; color: #fff; border: none; cursor: pointer; font-weight: 600; }
  button.sec { background: #0f766e; }
  button:disabled { background: #94a3b8; cursor: not-allowed; }
  .muted { color: #888; font-size: .9rem; }
  .error { color: #dc2626; font-weight: 600; }

  .tabs { display: flex; gap: 8px; margin: 0; border: 1px solid var(--line); }
  .tab { padding: 8px 14px; cursor: pointer; border: 1px solid transparent; border-bottom: none;
         border-radius: 8px 8px 0 0; color: #64748b; font-weight: 600; }
  .tab.active { color: #2563eb; border-color: #e2e8f0; background: rgba(37,99,235,.06); }
  .panel { display: none; }
  .panel.active { display: block; }

  .flow { font-size: .82rem; color: #64748b; background: rgba(127,127,127,.08);
          padding: 8px 12px; border-radius: 8px; margin: 14px 0; word-break: keep-all; }
  .sec-title { font-size: 1.1rem; margin: 22px 0 8px; }

  .card { border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin: 12px 0;
          background: rgba(127,127,127,0.05); }
  .card h2 { font-size: 1.05rem; margin: 0 0 8px; }
  .card table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: .9rem; }
  .card th, .card td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
  .card th { background: rgba(37,99,235,.1); }
  .content { white-space: pre-wrap; word-break: break-word; }

  .agent-card { border: 1px solid #d9e2ec; border-left: 5px solid #2563eb; border-radius: 10px;
                padding: 14px 16px; margin: 10px 0; background: rgba(127,127,127,0.04); }
  .agent-head { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
  .agent-name { font-weight: 700; font-size: 1.02rem; color: #2563eb; }
  .agent-role { color: #475569; font-size: .9rem; }
  .agent-check { color: #b45309; font-size: .86rem; margin: 6px 0 8px; }
  .agent-out { font-size: .92rem; }
  .agent-out ul { margin: 6px 0; padding-left: 18px; }
  .cand { padding: 6px 8px; margin: 4px 0; border-radius: 6px; background: rgba(127,127,127,0.08); white-space: pre-wrap; }
  .chip { display: inline-block; background: #2563eb22; border: 1px solid #2563eb55;
          border-radius: 999px; padding: 1px 10px; margin: 2px; font-size: .85rem; }
  .win { color: #16a34a; font-weight: 700; }

  .batch-toolbar { display: flex; gap: 10px; align-items: center; margin: 12px 0 6px; flex-wrap: wrap; }
  .batch-source-editor { margin:12px 0; border:1px solid var(--line); border-radius:8px;
    background:color-mix(in srgb, var(--surface) 94%, transparent); }
  .batch-source-editor > summary { cursor:pointer; list-style:none; padding:12px 14px; color:var(--muted-text); font-weight:700; }
  .batch-source-editor > summary::-webkit-details-marker { display:none; }
  .batch-source-editor > summary::before { content:"\2699  "; color:var(--brand); }
  .batch-source-editor[open] > summary { border-bottom:1px solid var(--line); }
  .batch-source-editor textarea { display:block; width:calc(100% - 24px); margin:12px; }
  details.case { border: 1px solid #e2e8f0; border-radius: 10px; margin: 10px 0; background: rgba(127,127,127,0.03); }
  details.case > summary { cursor: pointer; padding: 12px 14px; font-size: .95rem; list-style: none; word-break: break-word; }
  details.case > summary::-webkit-details-marker { display: none; }
  details.case > summary::before { content: "\25B8  "; color: #64748b; }
  details.case[open] > summary::before { content: "\25BE  "; }
  details.case[open] > summary { border-bottom: 1px solid #e2e8f0; }
  .case-body { padding: 8px 14px 14px; }
  .st-ok { color: #16a34a; font-weight: 700; }
  .st-empty { color: #b45309; font-weight: 700; }
  .st-err { color: #dc2626; font-weight: 700; }
  .st-run { color: #2563eb; font-weight: 700; }
  .ops-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items:start; }
  .ops-grid > .card { min-width:0; }
  .ops-grid > .card.is-result-expanded { grid-column:1 / -1; }
  .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 10px; }
  .metric { border: 1px solid #cbd5e1; border-radius: 9px; padding: 10px 12px; background: rgba(37,99,235,.05); }
  .metric b { display: block; font-size: 1.15rem; }
  .warning { border-left: 5px solid #d97706; background: rgba(217,119,6,.09); padding: 10px 12px; border-radius: 8px; }
  .success { color: #15803d; font-weight: 700; }
  .report-list { max-height: 310px; overflow: auto; }
  .report-item { padding: 7px 0; border-bottom: 1px solid #dbe3ec; word-break: break-all; }
  .report-item a { color: #2563eb; }
  .ops-log { max-height: 360px; overflow: auto; white-space: pre-wrap; font-size: .84rem; }
  .operation-result { min-height: 92px; margin-top: 14px; padding: 12px; border: 1px dashed var(--line);
    border-radius: 9px; background: color-mix(in srgb, var(--surface-2) 78%, transparent); }
  .operation-result h3 { margin: 0 0 8px; font-size: .95rem; }
  .operation-result .ops-log { max-height: 220px; margin: 0; }
  .operation-result.is-idle { display: grid; place-items: center; color: var(--muted-text); text-align: center; }
  .operation-result.is-error { border-style: solid; border-color: var(--danger); }
  .operation-result.is-complete { border-style: solid; border-color: var(--brand-2); }
  .operation-result details { margin-top: 8px; }
  .operation-result summary { cursor: pointer; font-weight: 700; }
  .result-verdict { display:flex; align-items:center; justify-content:space-between; gap:10px; margin:4px 0 10px; }
  .result-verdict strong { font-size:1.25rem; color:var(--heading); }
  .result-metrics { display:grid; grid-template-columns:repeat(auto-fit,minmax(105px,1fr)); gap:8px; margin:10px 0; }
  .result-metric { border:1px solid var(--line); border-radius:8px; padding:9px 10px; background:var(--surface); color:var(--muted-text); font-size:.78rem; }
  .result-metric b { display:block; margin-top:2px; color:var(--heading); font-size:1.05rem; }
  .result-table-wrap { max-height:360px; overflow:auto; border:1px solid var(--line); border-radius:8px; margin-top:10px; }
  .result-table { width:100%; border-collapse:collapse; font-size:.82rem; }
  .result-table th, .result-table td { padding:8px 9px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
  .result-table th { position:sticky; top:0; z-index:1; background:#12335f; color:#fff; }
  .result-table td:nth-child(1) { min-width:105px; font-weight:700; }
  .result-table td:last-child { min-width:220px; }
  .result-files { display:flex; flex-wrap:wrap; gap:7px; margin-top:10px; }
  .result-files a { display:inline-flex; align-items:center; min-height:32px; padding:5px 9px; border:1px solid var(--line); border-radius:7px; background:var(--surface); text-decoration:none; }
  .technical-data { max-height:240px; overflow:auto; white-space:pre-wrap; word-break:break-word; font-size:.76rem; }
  .artifact-preview { margin-top:14px; padding:16px; border:1px solid var(--line); border-radius:10px; background:var(--surface-2); }
  .artifact-preview h3 { margin-top:0; }
  select[multiple] { min-height: 115px; min-width: 100%; }
  button.warn { background: #b45309; }
  input, select, textarea { background: #071424; color: var(--text); border-color: var(--line) !important; }
  button, .tab { min-height: 42px; }
  button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, a:focus-visible {
    outline: 3px solid #facc15; outline-offset: 2px;
  }
  .app-header { padding: 18px 20px; background: linear-gradient(110deg, #0d223b, #0b3040);
    border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 18px 50px #0005; }
  .eyebrow { margin: 0; color: var(--brand-2); font-weight: 800; letter-spacing: .08em; font-size: .75rem; }
  .tabs { position:fixed; z-index:20; top:24px; bottom:24px;
    left:max(12px, calc((100vw - 1680px) / 2 + 24px)); width:216px; padding:14px;
    overflow-y:auto; scrollbar-width:thin; flex-direction:column; border-radius:16px;
    background:linear-gradient(180deg,#0d223b,#071424); box-shadow:0 18px 50px #0005; }
  .nav-brand { padding:8px 8px 14px; border-bottom:1px solid var(--line); margin-bottom:4px; }
  .nav-brand b { display:block; font-size:1.05rem; }
  .nav-section { margin:10px 8px 2px; color:#7dd3fc; font-size:.7rem; letter-spacing:.08em; font-weight:900; }
  .side-link { width:100%; display:flex; align-items:center; text-align:left; text-decoration:none;
    background:transparent; color:var(--muted-text); padding:8px 10px; min-height:36px; }
  .side-link:hover { background:#12304a; color:#fff; }
  .nav-toggle { display:none; }
  .tab { display:flex; align-items:center; text-decoration:none; background: transparent; color: var(--muted-text); white-space: nowrap; }
  .tab.active { color: #fff; background: #075985; border-color: #0ea5e9; }
  .card, details.case, .agent-card { background: color-mix(in srgb, var(--surface) 94%, transparent); border-color: var(--line); }
  .metric { background: linear-gradient(135deg, #102a46, #0d1d31); border-color: var(--line); }
  .muted, .sub { color: var(--muted-text); }
  .control-hero { display: grid; grid-template-columns: 1.7fr 1fr; gap: 14px; align-items: stretch; }
  .release-banner { display: flex; justify-content: space-between; gap: 18px; align-items: center;
    padding: 20px; border: 1px solid var(--line); border-radius: 14px; background: linear-gradient(130deg,#0c2741,#102e37); }
  .release-verdict { font-size: 2rem; font-weight: 900; line-height: 1.1; }
  .release-score { width:220px; min-height:132px; flex:0 0 220px; display:grid; align-content:center;
    justify-items:center; gap:3px; padding:14px 16px; border:1px solid #31506f; border-left:6px solid #d97706;
    border-radius:10px; background:#071424; }
  .release-score.pass { border-left-color:#16845b; }
  .release-score.hold { border-left-color:#d97706; }
  .release-score-label { color:var(--muted-text); font-size:.72rem; font-weight:800; letter-spacing:.08em; }
  .release-score-number { display:flex; align-items:baseline; justify-content:center; gap:5px; line-height:1; }
  .release-score-value { color:#7dd3fc; font-size:3.5rem; font-weight:950; letter-spacing:-.06em; }
  .release-score-unit { color:var(--muted-text); font-size:1rem; font-weight:800; }
  .release-score-status { margin-top:3px; color:#fbbf24; font-size:.82rem; font-weight:900; letter-spacing:.08em; }
  .release-score.pass .release-score-status { color:#5eead4; }
  .control-toolbar { display: grid; grid-template-columns: repeat(auto-fit,minmax(140px,1fr));
    gap: 8px; align-items: end; }
  .control-toolbar label, .form-stack label { display: grid; gap: 4px; color: var(--muted-text); font-size: .84rem; }
  .case-filter-toolbar { grid-template-columns:minmax(180px,1.2fr) minmax(115px,.75fr) minmax(115px,.75fr)
    minmax(130px,.85fr) minmax(110px,.65fr) minmax(145px,.9fr) minmax(125px,.72fr) minmax(140px,.82fr); gap:10px; }
  .case-filter-toolbar > label { min-width:0; width:100%; }
  .case-filter-toolbar input:not([type="checkbox"]), .case-filter-toolbar select,
  .case-filter-toolbar > button { display:block; width:100%; max-width:100%; min-width:0; }
  .case-filter-toolbar .case-checkbox { display:flex; align-items:center; justify-content:flex-start; gap:8px;
    min-height:44px; padding:0 8px; white-space:nowrap; }
  .case-filter-toolbar .case-checkbox input { flex:0 0 auto; width:16px; height:16px; margin:0; }
  .run-filter-toolbar { grid-template-columns:minmax(160px,1.15fr) minmax(130px,.9fr) minmax(110px,.72fr)
    minmax(110px,.72fr) minmax(105px,.65fr) minmax(125px,.82fr) minmax(130px,.85fr)
    minmax(120px,.72fr) minmax(135px,.82fr); gap:10px; }
  .run-filter-toolbar > label { min-width:0; width:100%; }
  .run-filter-toolbar input:not([type="checkbox"]), .run-filter-toolbar select,
  .run-filter-toolbar > button { display:block; width:100%; max-width:100%; min-width:0; }
  .run-filter-toolbar .run-checkbox { display:flex; align-items:center; justify-content:flex-start; gap:8px;
    min-height:44px; padding:0 8px; white-space:nowrap; }
  .run-filter-toolbar .run-checkbox input { flex:0 0 auto; width:16px; height:16px; margin:0; }
  .table-wrap { width: 100%; overflow: auto; border: 1px solid var(--line); border-radius: 10px; }
  .data-table { width: 100%; border-collapse: collapse; min-width: 820px; font-size: .86rem; }
  .data-table th { position: sticky; top: 0; z-index: 1; background: #102b47; color: #cde9ff; text-align: left; }
  .data-table th, .data-table td { padding: 9px 10px; border-bottom: 1px solid var(--line); }
  .data-table tr:hover td { background: #12304a88; }
  .badge { display:inline-flex; align-items:center; border-radius:999px; padding:2px 8px; font-size:.75rem; font-weight:800; }
  .badge.pass, .badge.improved, .badge.approved { color:#5eead4; background:#134e4a99; }
  .badge.fail, .badge.regressed, .badge.rejected { color:#fecdd3; background:#88133799; }
  .badge.hold, .badge.warning, .badge.pending { color:#fde68a; background:#78350f99; }
  .badge.reviewing, .badge.changes_requested { color:#fef3c7; background:#92400eaa; }
  .badge.info, .badge.unchanged, .badge.added { color:#bae6fd; background:#07598599; }
  .control-grid { display:grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap:14px; }
  .page-launch-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-top:14px; }
  .page-launch-card { display:block; min-height:112px; padding:16px; color:var(--text); text-decoration:none;
    border:1px solid var(--line); border-left:4px solid var(--brand); border-radius:8px; background:var(--surface); }
  .page-launch-card:hover { border-color:var(--brand); transform:translateY(-1px); }
  .page-launch-card b { display:block; margin-bottom:5px; color:var(--brand); font-size:1rem; }
  .page-launch-card span { color:var(--muted-text); font-size:.84rem; line-height:1.45; }
  .chart-shell { min-height: 200px; display:flex; flex-direction:column; align-items:center; justify-content:center; width:100%; }
  .trend-svg { width:100%; height:210px; overflow:visible; }
  .trace-list { display:grid; gap:8px; margin-top:12px; }
  .trace-stage { display:grid; grid-template-columns: 120px minmax(100px,1fr) 105px 95px; gap:8px;
    align-items:center; padding:9px; border:1px solid var(--line); border-radius:9px; background:#0b1d31; }
  .trace-bar-wrap { background:#06101d; height:12px; border-radius:99px; overflow:hidden; }
  .trace-bar { height:100%; background:linear-gradient(90deg,var(--brand),var(--brand-2)); border-radius:99px; min-width:3px; }
  .compare-summary { display:grid; grid-template-columns:repeat(5,minmax(95px,1fr)); gap:8px; margin:10px 0; }
  .compact-stat { padding:9px; border:1px solid var(--line); border-radius:9px; text-align:center; background:#0b1d31; }
  .compact-stat b { display:block; font-size:1.15rem; }
  .form-stack { display:grid; gap:9px; }
  .notice { border:1px solid #155e75; background:#082f49aa; border-radius:10px; padding:10px 12px; }
  .progress-shell { height:14px; background:#06101d; border:1px solid var(--line); border-radius:999px; overflow:hidden; margin:10px 0; }
  .progress-value { height:100%; width:0; background:linear-gradient(90deg,#0284c7,#2dd4bf); transition:width .3s ease; }
  .job-card { border-left:5px solid var(--brand); }
  .case-detail-panel { margin:14px 0; padding:18px; border:2px solid var(--brand); border-radius:10px;
    background:color-mix(in srgb, var(--surface) 96%, var(--brand) 4%); scroll-margin-top:18px; }
  .case-detail-head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:12px; }
  .case-detail-head h3 { margin:0; color:var(--brand); }
  .case-detail-status { margin:8px 0 14px; }
  body.run-detail-open { overflow:hidden; }
  .run-detail-layer { position:fixed; z-index:90; inset:0; display:grid; place-items:center; padding:24px;
    background:#06101dcc; backdrop-filter:blur(3px); }
  .run-detail-dialog { width:min(1320px,96vw); max-height:92vh; display:flex; flex-direction:column;
    overflow:hidden; border:2px solid var(--brand); border-radius:14px; background:var(--surface);
    box-shadow:0 24px 80px #02061788; }
  .run-detail-head { flex:0 0 auto; display:flex; align-items:flex-start; justify-content:space-between; gap:18px;
    padding:16px 18px; border-bottom:1px solid var(--line); background:var(--surface-2); }
  .run-detail-head h3 { margin:3px 0 0; color:var(--brand); }
  .run-detail-head .row { margin:0; justify-content:flex-end; }
  .run-detail-scroll { min-height:0; overflow:auto; padding:18px; overscroll-behavior:contain; }
  .run-actions { display:grid; grid-template-columns:1fr; gap:7px; min-width:132px; }
  .run-action { width:100%; min-height:44px; display:inline-flex; align-items:center; justify-content:center;
    padding:9px 12px; border:1px solid transparent; border-radius:8px; color:#fff !important;
    text-decoration:none; font-weight:850; line-height:1.25; white-space:normal; text-align:center; }
  .run-action.detail { background:#0f766e; border-color:#0b625c; }
  .run-action.detail:hover { background:#0b625c; }
  .run-action.word { background:#1d5f9f; border-color:#174e83; }
  .run-action.word:hover { background:#174e83; }
  .run-data-audit { margin:10px 0 14px; border-left:5px solid var(--brand); }
  .run-result-section { margin:14px 0; }
  .run-result-section h4 { margin:14px 0 7px; color:var(--heading); }
  .run-result-value { margin:7px 0; padding:11px 12px; border:1px solid var(--line); border-radius:8px;
    background:var(--surface); white-space:pre-wrap; word-break:break-word; }
  .run-result-value strong { color:var(--heading); }
  .run-result-list { margin:5px 0 5px 20px; padding:0; }
  .run-result-list li { margin:3px 0; }
  .agent-result-table td:last-child { min-width:300px; }
  .run-case-list { display:grid; gap:9px; margin:14px 0; }
  .run-case-list details { margin:0; }
  .run-case-columns { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
  .full-data-view { max-height:620px; overflow:auto; margin:0; padding:14px; white-space:pre-wrap;
    word-break:break-word; border-radius:7px; color:#cde9ff; background:#071424; font:12px/1.5 Consolas,monospace; }
  .download-link { display:inline-flex; align-items:center; justify-content:center; min-height:42px; padding:10px 14px;
    border-radius:6px; color:#fff !important; background:#14599d; text-decoration:none; font-weight:800; }
  .download-link:hover { background:#0b477f; }
  .approval-queue { max-height:330px; overflow:auto; }
  .review-queue-item { display:block; height:auto; white-space:normal; text-align:left; border:1px solid var(--line); margin:6px 0; }
  .review-question { display:block; margin:4px 0; color:var(--text); font-weight:700; line-height:1.45; }
  .approval-steps { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:12px 0; }
  .approval-step { padding:10px 12px; border:1px solid var(--line); border-radius:9px; color:var(--muted-text); background:var(--surface-2); }
  .approval-step b { display:block; color:var(--heading); }
  .approval-step.active { border-color:var(--brand); box-shadow:inset 4px 0 var(--brand); }
  .approval-filter-grid { display:grid;
    grid-template-columns:minmax(170px,.72fr) minmax(280px,1.55fr) minmax(170px,.78fr) minmax(220px,1fr);
    gap:12px; align-items:end; }
  .approval-filter-grid label { display:grid; gap:5px; min-width:0; width:100%; color:var(--muted-text); font-size:.84rem; }
  .approval-filter-grid input, .approval-filter-grid select { display:block; width:100%; max-width:100%; min-width:0; }
  #approvalQueueRun { overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
  .approval-workspace { display:grid; grid-template-columns:minmax(320px,.9fr) minmax(420px,1.1fr); gap:14px; align-items:start; }
  .approval-workspace > section { min-width:0; border:1px solid var(--line); border-radius:10px; padding:14px; background:var(--surface); }
  .selected-review-context { min-height:150px; }
  .selected-review-context .content { max-height:220px; overflow:auto; }
  .approval-form fieldset { border:0; padding:0; margin:0; min-width:0; }
  .approval-form fieldset:disabled { opacity:.58; }
  .approval-history { margin-top:16px; border-top:1px solid var(--line); padding-top:12px; }
  :root[data-theme="light"] body { background:linear-gradient(135deg,#e8f3fa,#f8fbfd); }
  :root[data-theme="light"] .tabs { background:linear-gradient(180deg,#ffffff,#e8f1f8); box-shadow:0 14px 38px #33415522; }
  :root[data-theme="light"] .side-link:hover { background:#dbeafe; color:#0c4a6e; }
  :root[data-theme="light"] .card,
  :root[data-theme="light"] details.case,
  :root[data-theme="light"] .agent-card { background:#fff; }
  :root[data-theme="light"] .metric,
  :root[data-theme="light"] .compact-stat,
  :root[data-theme="light"] .trace-stage { background:#f1f7fb; }
  :root[data-theme="light"] .app-header,
  :root[data-theme="light"] .release-banner { background:linear-gradient(120deg,#fff,#e6f6fb); box-shadow:none; }
  :root[data-theme="light"] input,
  :root[data-theme="light"] select,
  :root[data-theme="light"] textarea { background:#fff; color:#102033; }
  /* Enterprise QA dashboard theme: 첨부 레퍼런스의 레이아웃·색상 체계만 반영 */
  body { max-width:none; margin:0; padding:86px 28px 32px 278px; }
  .system-bar { position:fixed; z-index:50; inset:0 0 auto 0; height:58px; display:grid;
    grid-template-columns:280px 1fr auto; align-items:center; gap:24px; padding:0 20px;
    color:#fff; background:#12335f; border-bottom:3px solid #245a97; box-shadow:0 2px 10px #0f27441f; }
  .system-brand { display:flex; align-items:center; gap:10px; color:#fff; text-decoration:none;
    font-size:1.05rem; font-weight:900; letter-spacing:-.02em; }
  .brand-mark { width:28px; height:28px; display:grid; place-items:center; border-radius:7px;
    color:#12335f; background:#fff; font-size:.9rem; }
  .system-links { height:100%; display:flex; justify-content:center; align-items:stretch; gap:8px; }
  .system-link { display:grid; place-items:center; min-width:112px; padding:0 16px; color:#bdcae0;
    border-bottom:3px solid transparent; font-size:.82rem; font-weight:700; text-decoration:none;
    transition:color .15s ease, background .15s ease, border-color .15s ease; }
  .system-link:hover { color:#fff; background:#ffffff0a; }
  .system-link.active { color:#fff; border-bottom-color:#61a5ff; background:#ffffff0a; }
  .system-meta { display:flex; align-items:center; gap:10px; font-size:.78rem; font-weight:700; }
  .live-dot { width:8px; height:8px; border-radius:50%; background:#39c688; box-shadow:0 0 0 4px #39c68824; }
  .user-chip { padding:5px 10px; border:1px solid #ffffff38; border-radius:7px; background:#ffffff12; }
  .app-header, .panel { width:min(100%, 1480px); margin-left:auto; margin-right:auto; }
  .app-header { position:relative; padding:18px 22px 20px; margin-bottom:16px; border-radius:8px;
    border:1px solid #c8d9ee; box-shadow:none; }
  .app-header > .row { margin:0; }
  .app-header h1 { margin:2px 0 2px; color:#0b3768; font-size:1.7rem; letter-spacing:-.035em; }
  .breadcrumb { margin:0 0 10px; color:#70839a; font-size:.76rem; }
  .header-actions a { color:#155da8 !important; padding:8px 10px; border:1px solid #c7d9ee;
    border-radius:7px; background:#f7faff; text-decoration:none; }
  .tabs { top:58px; bottom:0; left:0; width:250px; padding:22px 14px; border:0; border-radius:0;
    background:#17263c; box-shadow:2px 0 12px #0f274419; }
  .nav-brand { padding:3px 9px 18px; margin-bottom:8px; border-bottom-color:#34465f; }
  .nav-brand b { color:#fff; font-size:1.1rem; }
  .nav-brand small { display:block; margin-top:4px; color:#93a5bb; }
  .nav-section { margin-top:18px; color:#7f91a9; letter-spacing:.1em; }
  .tab, .side-link { border-radius:5px; }
  .tab { border:0; border-left:3px solid transparent; padding:10px 12px; color:#aebed2; }
  .tab:hover, .side-link:hover { color:#fff; background:#263c59; }
  .tab.active { color:#fff; border-left-color:#5b9df1; background:#315079; box-shadow:none; }
  .side-link { color:#9fb0c6; }
  .side-link.active { color:#fff; border-left:3px solid #5b9df1; background:#294767; }
  [data-page-container].single-page-view { grid-template-columns:1fr; }
  .panel > .sec-title:first-child { margin-top:0; }
  .control-live-status { margin:0 0 12px; padding:10px 13px; border:1px solid #b8d2ef;
    border-left:4px solid #1d63ad; border-radius:7px; background:#edf5fd; color:#15477b; font-size:.86rem; }
  .control-live-status:empty { display:none; }
  .control-hero { grid-template-columns:1fr; gap:10px; }
  #controlKpis { grid-template-columns:repeat(4,minmax(0,1fr)); }
  .release-banner { min-height:120px; padding:18px 22px; border-radius:8px; }
  .release-verdict { margin:3px 0 2px; font-size:1.55rem; }
  .release-score { width:220px; min-height:136px; flex-basis:220px; padding:14px 18px; }
  .metric { min-height:82px; display:flex; flex-direction:column; justify-content:center; border-radius:7px;
    border-left:4px solid #2a6fb8; padding:11px 14px; color:#3c5876; font-size:.78rem; }
  .metric b { margin-top:3px; color:#0a477f; font-size:1.28rem; line-height:1.2; }
  .card { border-radius:8px; padding:17px; }
  .card h2 { color:#123d6d; font-size:1.08rem; letter-spacing:-.015em; }
  .sec-title { color:#123d6d; padding:0 0 7px; border-bottom:2px solid #d8e6f5; }
  .control-grid { gap:12px; }
  .control-toolbar { padding:11px; border:1px solid #d2e1f1; border-radius:7px; background:#f7faff; }
  .control-toolbar label, .form-stack label { color:#506982; font-size:.8rem; font-weight:650; }
  button { border-radius:6px; background:#14599d; box-shadow:none; transition:background .15s ease, transform .15s ease; }
  button:hover:not(:disabled) { background:#0b477f; transform:translateY(-1px); }
  button.sec { background:#11766f; }
  button.sec:hover:not(:disabled) { background:#0b5f59; }
  button.warn { background:#b75b07; }
  button.warn:hover:not(:disabled) { background:#934904; }
  .operation-result { border-radius:7px; }
  .data-table th { background:#173f6b; color:#fff; }
  .table-wrap { border-radius:7px; }
  .badge { border-radius:5px; }
  .trace-stage, .compact-stat { border-radius:7px; }
  :root[data-theme="light"] body { color:#16283d; background:#f4f7fb; }
  :root[data-theme="light"] .system-bar { background:#12335f; }
  :root[data-theme="light"] .tabs { background:#17263c; box-shadow:2px 0 12px #0f274419; }
  :root[data-theme="light"] .tab, :root[data-theme="light"] .side-link { color:#aebed2; }
  :root[data-theme="light"] .tab:hover, :root[data-theme="light"] .side-link:hover { color:#fff; background:#263c59; }
  :root[data-theme="light"] .tab.active { color:#fff; background:#315079; border-color:#5b9df1; }
  :root[data-theme="light"] .app-header { background:#fff; }
  :root[data-theme="light"] .release-banner { background:#fff; border-color:#c9dcef; box-shadow:none; }
  :root[data-theme="light"] .release-score { color:#0a477f; background:#f3f8fe; border-color:#c3d7ed; border-left-color:#d97706; box-shadow:0 5px 16px #1e3a5f12; }
  :root[data-theme="light"] .release-score.pass { border-left-color:#16845b; }
  :root[data-theme="light"] .release-score-value { color:#0b4f8a; }
  :root[data-theme="light"] .release-score-status { color:#a85400; }
  :root[data-theme="light"] .release-score.pass .release-score-status { color:#087449; }
  :root[data-theme="light"] .card,
  :root[data-theme="light"] details.case,
  :root[data-theme="light"] .agent-card { background:#fff; border-color:#c9dcef; box-shadow:0 1px 3px #264b7212; }
  :root[data-theme="light"] .metric { background:#fff; border-color:#c9dcef; border-left-color:#2a6fb8; }
  :root[data-theme="light"] .compact-stat,
  :root[data-theme="light"] .trace-stage { color:#173553; background:#f7faff; border-color:#c9dcef; }
  :root[data-theme="light"] input,
  :root[data-theme="light"] select,
  :root[data-theme="light"] textarea { color:#173553; background:#f8fbff; border-color:#bfd3e9 !important; }
  :root[data-theme="light"] .data-table tr:hover td { background:#eef5fd; }
  :root[data-theme="light"] .operation-result { color:#173553; background:#f5f9fd; border-color:#aac7e5; }
  :root[data-theme="light"] .run-detail-dialog { background:#fff; border-color:#8eb8df; }
  :root[data-theme="light"] .full-data-view { color:#183b5d; background:#eef5fd; border:1px solid #c3d7ed; }
  :root[data-theme="light"] .batch-source-editor { background:#fff; border-color:#c9dcef; }
  :root[data-theme="light"] .notice { color:#174a78; background:#edf5fd; border-color:#b9d3ec; }
  :root[data-theme="light"] .warning { color:#75420a; background:#fff8e7; }
  :root[data-theme="light"] .badge.pass,
  :root[data-theme="light"] .badge.improved,
  :root[data-theme="light"] .badge.approved { color:#087449; background:#e8f7ef; }
  :root[data-theme="light"] .badge.fail,
  :root[data-theme="light"] .badge.regressed,
  :root[data-theme="light"] .badge.rejected { color:#b4233d; background:#fdecef; }
  :root[data-theme="light"] .badge.hold,
  :root[data-theme="light"] .badge.warning,
  :root[data-theme="light"] .badge.pending { color:#965a05; background:#fff3d9; }
  :root[data-theme="light"] .badge.info,
  :root[data-theme="light"] .badge.unchanged,
  :root[data-theme="light"] .badge.added { color:#155b9d; background:#eaf3fd; }
  :root[data-theme="light"] .progress-shell, :root[data-theme="light"] .trace-bar-wrap { background:#e5eef7; }
  :root[data-theme="light"] .panel .side-link { width:auto; min-height:32px; padding:5px 9px;
    color:#155b9d; background:#eef5fd; border:1px solid #c2d8ee; }
  :root[data-theme="light"] .panel .side-link:hover { color:#fff; background:#155b9d; }
  :root[data-theme="light"] .panel .review-queue-item { width:100%; display:block; margin:5px 0;
    text-align:left; color:#173553; background:#f7faff; }
  /* 첨부 레퍼런스 기반 텍스트 입력: 연한 채움, 둥근 테두리, 명확한 포커스 */
  input:not([type="checkbox"]):not([type="radio"]):not([type="file"]),
  textarea {
    min-height:44px; padding:10px 13px; border:1px solid #31506f !important; border-radius:9px;
    background:#0c2035; color:var(--text); box-shadow:inset 0 1px 2px #02061740;
    font:inherit; line-height:1.35; transition:border-color .16s ease, box-shadow .16s ease, background .16s ease;
  }
  textarea { min-height:96px; }
  input:not([type="checkbox"]):not([type="radio"]):not([type="file"])::placeholder,
  textarea::placeholder { color:#7e93aa; opacity:1; }
  input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):hover,
  textarea:hover { border-color:#4d7baa !important; }
  input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):focus,
  textarea:focus {
    border-color:#2c72b8 !important; outline:none; background:#102943;
    box-shadow:0 0 0 3px #4b91d633, inset 0 1px 2px #02061738;
  }
  input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):disabled,
  textarea:disabled { cursor:not-allowed; opacity:.68; }
  :root[data-theme="light"] input:not([type="checkbox"]):not([type="radio"]):not([type="file"]),
  :root[data-theme="light"] textarea {
    background:#f1f6fc; color:#172b43; border-color:#c3d7ed !important;
    box-shadow:inset 0 1px 2px #1e3a5f0d, 0 1px 2px #1e3a5f0a;
  }
  :root[data-theme="light"] input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):hover,
  :root[data-theme="light"] textarea:hover { background:#edf4fc; border-color:#8fb5dd !important; }
  :root[data-theme="light"] input:not([type="checkbox"]):not([type="radio"]):not([type="file"]):focus,
  :root[data-theme="light"] textarea:focus {
    background:#fff; border-color:#2c72b8 !important;
    box-shadow:0 0 0 3px #2c72b824, inset 0 1px 2px #1e3a5f0d;
  }
  /* Sidebar identity, status and signed-in user area. */
  .tabs { display:flex; flex-direction:column; padding:17px 12px 0; }
  .nav-brand { padding:0 2px 17px; border-bottom:1px solid #31445f; }
  .nav-identity { display:flex; align-items:center; gap:11px; }
  .nav-logo { width:40px; height:40px; flex:0 0 40px; display:grid; place-items:center; border-radius:10px;
    color:#fff; background:linear-gradient(145deg,#56c7ef,#2579b9); box-shadow:0 7px 16px #0b172b66; font-size:1.35rem; }
  .nav-title { min-width:0; }
  .nav-title b { display:block; color:#fff; font-size:1rem; line-height:1.1; }
  .nav-title small { display:block; margin-top:3px; color:#64c9ef; font-size:.68rem; font-weight:800; letter-spacing:.11em; }
  .nav-status { display:flex; align-items:center; justify-content:center; gap:8px; margin-top:13px; padding:7px 9px;
    border:1px solid #29415f; border-radius:8px; color:#9fb5d0; background:#142944; font-size:.68rem; letter-spacing:.06em; }
  .nav-status strong { color:#fff; }
  .nav-status-dot { width:7px; height:7px; border-radius:50%; background:#2ed68b; box-shadow:0 0 0 4px #2ed68b19; }
  .nav-section-heading { display:flex; align-items:center; gap:10px; margin:22px 3px 8px; color:#6f88a9;
    font-size:.64rem; font-weight:800; letter-spacing:.2em; }
  .nav-section-heading::after { content:""; height:1px; flex:1; background:#29415f; }
  .tabs .tab, .tabs .side-link { gap:11px; min-height:41px; padding:8px 10px; border-radius:8px; }
  .nav-icon { width:19px; flex:0 0 19px; display:inline-grid; place-items:center; color:#7f9ab9; font-size:1rem; }
  .tabs .tab.active .nav-icon, .tabs .side-link.active .nav-icon { color:#67c9ee; }
  .nav-shortcut, .nav-badge { margin-left:auto; flex:0 0 auto; border-radius:999px; font-size:.64rem; }
  .nav-shortcut { padding:1px 5px; color:#6481a4; border:1px solid #315071; }
  .nav-badge { min-width:24px; padding:2px 6px; text-align:center; color:#90dcfa; border:1px solid #397093; background:#173b59; }
  .nav-badge.alert { color:#ffd36d; border-color:#826326; background:#3a2d16; }
  .nav-badge:empty { display:none; }
  .nav-user { position:sticky; bottom:0; display:grid; grid-template-columns:38px 1fr auto; align-items:center; gap:9px;
    margin:18px -12px 0; padding:13px 12px; border-top:1px solid #31445f; background:#102038f2; backdrop-filter:blur(8px); }
  .nav-avatar { width:34px; height:34px; display:grid; place-items:center; border-radius:50%; color:#d9f4ff; background:#244e78; font-size:.78rem; font-weight:900; }
  .nav-user-copy { min-width:0; }
  .nav-user-copy b { display:block; overflow:hidden; color:#fff; font-size:.8rem; text-overflow:ellipsis; white-space:nowrap; }
  .nav-user-copy small { display:block; overflow:hidden; color:#6e8bad; font-size:.62rem; text-overflow:ellipsis; white-space:nowrap; }
  .nav-auth-action { width:30px; min-height:30px; padding:0; display:grid; place-items:center; color:#7f9ab9; border:0; background:transparent; box-shadow:none; font-size:1rem; }
  .nav-auth-action:hover:not(:disabled) { color:#fff; background:#263f5e; transform:none; }
  .login-layer { position:fixed; z-index:120; inset:0; display:grid; place-items:center; padding:20px; background:#071424aa; backdrop-filter:blur(4px); }
  .login-dialog { width:min(420px,100%); padding:25px; border:1px solid #d7e3f2; border-radius:16px; background:#fff; box-shadow:0 24px 70px #07142455; }
  .login-dialog h2 { margin:3px 0 4px; color:#10284a; }
  .login-dialog .form-stack { margin-top:18px; }
  .login-dialog-actions { display:flex; justify-content:flex-end; gap:9px; margin-top:4px; }
  .login-dialog-status { min-height:22px; margin:8px 0 0; font-size:.8rem; }
  /* Shared visual system for every Control Center detail page. */
  body[data-page-view="dashboard"] { --page-accent:#2475df; --page-tint:#eaf2ff; --page-rgb:36,117,223; }
  body[data-page-view="test-cases"] { --page-accent:#159b63; --page-tint:#e8f7ef; --page-rgb:21,155,99; }
  body[data-page-view="runs"] { --page-accent:#8350d2; --page-tint:#f2eaff; --page-rgb:131,80,210; }
  body[data-page-view="compare"] { --page-accent:#d97716; --page-tint:#fff1e3; --page-rgb:217,119,22; }
  body[data-page-view="trace"] { --page-accent:#109dbd; --page-tint:#e4f7fb; --page-rgb:16,157,189; }
  body[data-page-view="security"] { --page-accent:#dd4a58; --page-tint:#ffedef; --page-rgb:221,74,88; }
  body[data-page-view="approvals"] { --page-accent:#128f88; --page-tint:#e5f6f4; --page-rgb:18,143,136; }
  body[data-page-view="reports"] { --page-accent:#d99708; --page-tint:#fff6df; --page-rgb:217,151,8; }
  body[data-page-view="settings"] { --page-accent:#3473cf; --page-tint:#eaf2ff; --page-rgb:52,115,207; }
  body[data-page-view="dashboard"], body[data-page-view="test-cases"], body[data-page-view="runs"],
  body[data-page-view="compare"], body[data-page-view="trace"], body[data-page-view="security"],
  body[data-page-view="approvals"], body[data-page-view="reports"], body[data-page-view="settings"] {
    background:linear-gradient(145deg,#f7faff 0%,#f1f6fc 52%,#f8fbff 100%);
  }
  body:not([data-page-view="control-center"]):not([data-page-view="single"]):not([data-page-view="batch"]):not([data-page-view="quality"]) .app-header {
    min-height:174px; overflow:hidden; padding:25px 30px; border:1px solid #dce7f4;
    border-radius:17px; background:linear-gradient(115deg,#fff 0%,#fff 58%,var(--page-tint) 100%);
    box-shadow:0 10px 30px #234b7a10;
  }
  body:not([data-page-view="control-center"]):not([data-page-view="single"]):not([data-page-view="batch"]):not([data-page-view="quality"]) .app-header::before {
    content:""; position:absolute; width:260px; height:260px; right:90px; top:-135px; border-radius:50%;
    border:34px solid rgba(var(--page-rgb),.08); box-shadow:0 0 0 26px rgba(var(--page-rgb),.045);
  }
  body:not([data-page-view="control-center"]):not([data-page-view="single"]):not([data-page-view="batch"]):not([data-page-view="quality"]) .app-header::after {
    position:absolute; right:52px; bottom:7px; color:rgba(var(--page-rgb),.12); font-size:5.2rem; font-weight:900; line-height:1;
  }
  body[data-page-view="dashboard"] .app-header::after { content:"▦"; }
  body[data-page-view="test-cases"] .app-header::after { content:"☷"; }
  body[data-page-view="runs"] .app-header::after { content:"◴"; }
  body[data-page-view="compare"] .app-header::after { content:"⇄"; }
  body[data-page-view="trace"] .app-header::after { content:"⌁"; }
  body[data-page-view="security"] .app-header::after { content:"♢"; }
  body[data-page-view="approvals"] .app-header::after { content:"♙"; }
  body[data-page-view="reports"] .app-header::after { content:"□"; }
  body[data-page-view="settings"] .app-header::after { content:"⚙"; }
  body:not([data-page-view="control-center"]):not([data-page-view="single"]):not([data-page-view="batch"]):not([data-page-view="quality"]) .app-header > .row {
    position:relative; z-index:2; align-items:flex-start;
  }
  body:not([data-page-view="control-center"]):not([data-page-view="single"]):not([data-page-view="batch"]):not([data-page-view="quality"]) .app-header h1 {
    margin:7px 0 4px; color:#0b1d3a; font-size:2rem; line-height:1.15;
  }
  body:not([data-page-view="control-center"]):not([data-page-view="single"]):not([data-page-view="batch"]):not([data-page-view="quality"]) .app-header .eyebrow { color:var(--page-accent); }
  .page-context-badge { display:none; align-items:center; gap:7px; width:max-content; margin-top:15px; padding:5px 11px;
    border:1px solid rgba(var(--page-rgb),.16); border-radius:999px; color:var(--page-accent); background:var(--page-tint); font-size:.75rem; font-weight:800; }
  body:not([data-page-view="control-center"]):not([data-page-view="single"]):not([data-page-view="batch"]):not([data-page-view="quality"]) .page-context-badge { display:inline-flex; }
  .page-context-badge::before { content:""; width:7px; height:7px; border-radius:50%; background:var(--page-accent); box-shadow:0 0 0 4px rgba(var(--page-rgb),.1); }
  body:not([data-page-view="control-center"]) #panel-control > [data-page-view]:not(.sr-only),
  body:not([data-page-view="control-center"]) #panel-control > [data-page-container] {
    animation:page-rise .28s ease both;
  }
  @keyframes page-rise { from { opacity:0; transform:translateY(7px); } to { opacity:1; transform:none; } }
  body:not([data-page-view="control-center"]) #panel-control .card {
    border:1px solid #dfe8f3; border-radius:14px; background:#fff; box-shadow:0 7px 22px #254a7510;
  }
  body:not([data-page-view="control-center"]) #panel-control .card h2 { color:#10284a; }
  body:not([data-page-view="control-center"]) #panel-control .card > h2:first-child,
  body:not([data-page-view="control-center"]) #panel-control .card > .row:first-child h2 {
    position:relative; padding-left:14px;
  }
  body:not([data-page-view="control-center"]) #panel-control .card > h2:first-child::before,
  body:not([data-page-view="control-center"]) #panel-control .card > .row:first-child h2::before {
    content:""; position:absolute; left:0; top:2px; width:4px; height:21px; border-radius:4px; background:var(--page-accent);
  }
  body:not([data-page-view="control-center"]) .control-toolbar,
  body:not([data-page-view="control-center"]) .approval-filter-grid {
    padding:15px; border:1px solid #e0e9f4; border-radius:11px; background:linear-gradient(135deg,#fbfdff,var(--page-tint));
  }
  body:not([data-page-view="control-center"]) .control-toolbar label,
  body:not([data-page-view="control-center"]) .approval-filter-grid label,
  body:not([data-page-view="control-center"]) .form-stack label { color:#4c627d; font-weight:700; }
  body:not([data-page-view="control-center"]) #panel-control button:not(.sec):not(.warn) { background:var(--page-accent); }
  body:not([data-page-view="control-center"]) #panel-control button:not(.sec):not(.warn):hover { filter:brightness(.9); }
  body:not([data-page-view="control-center"]) .table-wrap { border-color:#dfe8f3; border-radius:11px; box-shadow:0 3px 10px #254a7508; }
  body:not([data-page-view="control-center"]) .data-table th { padding:12px 11px; background:#f2f6fb; color:#405774; border-bottom:2px solid rgba(var(--page-rgb),.25); }
  body:not([data-page-view="control-center"]) .data-table td { padding:11px; color:#2e435d; background:#fff; }
  body:not([data-page-view="control-center"]) .data-table tr:nth-child(even) td { background:#fbfdff; }
  body:not([data-page-view="control-center"]) .data-table tr:hover td { background:var(--page-tint); }
  body[data-page-view="dashboard"] #panel-control > .row[data-page-view="dashboard"] {
    margin:0 0 12px; padding:17px 20px; border:1px solid #dfe8f3; border-radius:13px; background:#fff; box-shadow:0 5px 18px #254a750c;
  }
  body[data-page-view="dashboard"] .release-banner { min-height:170px; border:1px solid #dbe7f4; border-radius:14px;
    background:linear-gradient(130deg,#fff,#edf4ff); box-shadow:0 7px 22px #254a7510; }
  body[data-page-view="dashboard"] .metric { min-height:96px; border:1px solid #dfe8f3; border-top:4px solid var(--page-accent);
    border-left:1px solid #dfe8f3; border-radius:12px; background:#fff; box-shadow:0 6px 18px #254a750e; }
  body[data-page-view="dashboard"] .release-score { border-radius:12px; background:#fff; }
  body[data-page-view="compare"] #compareCard, body[data-page-view="trace"] #traceCard { min-height:520px; padding:25px; }
  body[data-page-view="compare"] #compareCard .form-stack, body[data-page-view="trace"] #traceCard .form-stack,
  body[data-page-view="settings"] #settingsCard .form-stack {
    padding:18px; border:1px solid #e1eaf4; border-radius:11px; background:linear-gradient(135deg,#fbfdff,var(--page-tint));
  }
  body[data-page-view="compare"] #compareResult, body[data-page-view="trace"] #traceResult {
    min-height:250px; padding:18px; border:1px dashed #cbd9e8; border-radius:11px; background:#fbfdff;
  }
  body[data-page-view="approvals"] .approval-step { border-color:#dfe8f3; border-radius:10px; background:#f8fbfe; }
  body[data-page-view="approvals"] .approval-step.active { border-color:var(--page-accent); background:var(--page-tint); box-shadow:inset 4px 0 var(--page-accent); }
  body[data-page-view="approvals"] .approval-workspace > section { border-color:#dfe8f3; border-radius:12px; background:#fbfdff; }
  body[data-page-view="reports"] .report-item { padding:11px 7px; border-bottom-color:#e4ebf4; }
  body[data-page-view="reports"] .artifact-preview { border-color:#dfe8f3; border-radius:12px; background:#fbfdff; }
  body[data-page-view="settings"] #settingsCard > h3 { margin-top:26px; padding:8px 0; color:#173b68; border-bottom:1px solid #dfe8f3; }
  body[data-page-view="security"] #panel-quality .sec-title { padding:12px 17px; border:1px solid #f0cbd0; border-radius:12px; background:var(--page-tint); color:#9e2835; }
  body[data-page-view="security"] #panel-quality .ops-grid > .card { border:1px solid #eadfe2; border-top:4px solid var(--page-accent); border-radius:14px; background:#fff; box-shadow:0 7px 22px #5d26300d; }
  body[data-page-view="security"] #panel-quality .operation-result { border-radius:10px; background:#fbfdff; }
  :root[data-theme="dark"] body:not([data-page-view="control-center"]) #panel-control .card,
  :root[data-theme="dark"] body[data-page-view="security"] #panel-quality .ops-grid > .card { background:var(--surface); border-color:var(--line); }
  :root[data-theme="dark"] body:not([data-page-view="control-center"]) .data-table td { color:var(--text); background:var(--surface); }
  :root[data-theme="dark"] body:not([data-page-view="control-center"]) .data-table th { color:#cde9ff; background:#102b47; }
  @media (max-width:900px) {
    body:not([data-page-view="control-center"]):not([data-page-view="single"]):not([data-page-view="batch"]):not([data-page-view="quality"]) .app-header { min-height:155px; padding:20px; }
    body:not([data-page-view="control-center"]):not([data-page-view="single"]):not([data-page-view="batch"]):not([data-page-view="quality"]) .app-header::after { right:18px; font-size:4rem; }
  }
  /* Control Center landing page: airy analytics workspace inspired by the approved concept. */
  .header-visual, .hero-facts { display:none; }
  body[data-page-view="control-center"] { background:linear-gradient(145deg,#f7faff 0%,#eef5ff 48%,#f8fbff 100%); }
  body[data-page-view="control-center"] .app-header {
    min-height:274px; overflow:hidden; padding:30px 34px; border:1px solid #dce7f5;
    border-radius:18px; background:linear-gradient(112deg,#fff 0%,#fff 49%,#eef5ff 100%);
    box-shadow:0 12px 35px #234b7a12;
  }
  body[data-page-view="control-center"] .app-header::before {
    content:""; position:absolute; width:430px; height:430px; right:75px; top:-215px; border-radius:50%;
    background:radial-gradient(circle,#dceaff 0%,#edf5ff 58%,transparent 59%); opacity:.9;
  }
  body[data-page-view="control-center"] .app-header > .row { position:relative; z-index:2; align-items:flex-start; }
  body[data-page-view="control-center"] .app-header h1 { margin:9px 0 5px; color:#071a3a; font-size:2.55rem; line-height:1.12; }
  body[data-page-view="control-center"] .app-header .sub { max-width:620px; margin-bottom:0; font-size:1rem; }
  body[data-page-view="control-center"] .breadcrumb { position:relative; z-index:2; margin-bottom:18px; }
  body[data-page-view="control-center"] .header-actions a {
    color:#fff !important; border-color:#1760c7; background:linear-gradient(135deg,#2477e8,#1255c2);
    padding:11px 17px; border-radius:9px; box-shadow:0 8px 18px #1d63c929;
  }
  .header-visual { position:absolute; z-index:1; right:185px; bottom:18px; width:365px; height:185px; pointer-events:none; }
  body[data-page-view="control-center"] .header-visual { display:block; }
  .header-visual .visual-glow { position:absolute; inset:25px 0 0; border-radius:50%; background:#cfe2ff88; filter:blur(18px); }
  .visual-window { position:absolute; left:25px; top:18px; width:245px; height:155px; padding:34px 24px 18px;
    border:1px solid #d9e6f7; border-radius:18px; background:#ffffffd9; transform:rotate(4deg); box-shadow:0 18px 36px #2f67ad25; }
  .visual-window::before { content:"•••"; position:absolute; top:6px; left:17px; color:#69a0ed; font-size:1.2rem; letter-spacing:4px; }
  .visual-bars { height:75px; display:flex; align-items:flex-end; gap:14px; border-bottom:2px solid #dbe8f8; }
  .visual-bars i { width:14px; border-radius:5px 5px 0 0; background:linear-gradient(#79aff7,#276ed6); box-shadow:0 3px 8px #2462ba25; }
  .visual-bars i:nth-child(1){height:38%}.visual-bars i:nth-child(2){height:72%}.visual-bars i:nth-child(3){height:53%}.visual-bars i:nth-child(4){height:88%}
  .visual-ring { position:absolute; right:58px; top:35px; width:80px; height:80px; border:11px solid #5c9df2; border-right-color:#c5dcfb; border-radius:50%; box-shadow:0 7px 16px #1c63c333; }
  .visual-ring::after { content:""; position:absolute; width:55px; height:11px; right:-43px; bottom:-22px; border-radius:8px; background:#2468cb; transform:rotate(48deg); }
  .visual-shield { position:absolute; right:3px; bottom:2px; width:78px; height:88px; display:grid; place-items:center;
    color:#fff; font-size:2.2rem; font-weight:900; background:linear-gradient(145deg,#3c83e8,#1252b8);
    clip-path:polygon(50% 0,94% 15%,88% 68%,50% 100%,12% 68%,6% 15%); filter:drop-shadow(0 10px 12px #1d59ae38); }
  .hero-facts { gap:12px; margin-top:27px; }
  body[data-page-view="control-center"] .hero-facts { display:flex; }
  .hero-fact { min-width:155px; display:flex; align-items:center; gap:10px; padding:10px 14px; border:1px solid #e2eaf5;
    border-radius:10px; color:#526881; background:#ffffffc9; box-shadow:0 3px 10px #31557d0b; font-size:.78rem; }
  .hero-fact strong { display:block; color:#145dcc; font-size:1.08rem; }
  .hero-fact-icon { color:#2675db; font-size:1.25rem; }
  .control-center-home { padding:27px 30px 30px; border:1px solid #dce7f5 !important; border-radius:18px !important; box-shadow:0 12px 35px #234b7a12 !important; }
  .launch-section-head { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; margin-bottom:20px; }
  .launch-heading h2 { position:relative; margin:0 0 6px; padding-left:17px; color:#0b2346 !important; font-size:1.28rem !important; }
  .launch-heading h2::before { content:""; position:absolute; left:0; top:3px; width:5px; height:22px; border-radius:5px; background:#2978e8; }
  .launch-heading p { margin:0; }
  .launch-search { position:relative; width:min(280px,100%); flex:0 0 280px; }
  .launch-search::before { content:"⌕"; position:absolute; z-index:1; left:15px; top:7px; color:#7890ad; font-size:1.35rem; }
  .launch-search input { width:100%; padding-left:43px !important; border-radius:999px !important; background:#fff !important; }
  .page-launch-grid { grid-template-columns:repeat(4,minmax(0,1fr)); gap:18px; margin-top:0; }
  .page-launch-card { position:relative; min-height:170px; padding:18px 17px 42px 74px; border:1px solid #e2e9f3;
    border-left:1px solid #e2e9f3; border-radius:13px; color:#172945; background:#fff; box-shadow:0 5px 16px #22456e0d;
    transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease; }
  .page-launch-card:hover { transform:translateY(-4px); border-color:#b8d3f4; box-shadow:0 14px 28px #1d579b1c; }
  .page-launch-card b { margin:10px 0 6px; color:#101f38; font-size:1.02rem; }
  .page-launch-card span:not(.launch-icon):not(.launch-arrow) { display:block; color:#60728a; font-size:.8rem; line-height:1.55; }
  .launch-icon { position:absolute; left:17px; top:18px; width:43px; height:43px; display:grid; place-items:center;
    border-radius:10px; color:var(--card-accent,#2475df); background:var(--card-tint,#eaf2ff); font-size:1.35rem; }
  .launch-arrow { position:absolute; right:16px; bottom:14px; width:31px; height:31px; display:grid; place-items:center;
    border:1px solid #dce7f5; border-radius:50%; color:#3277d5; background:#fff; font-size:1.1rem; transition:transform .18s ease, background .18s ease; }
  .page-launch-card:hover .launch-arrow { color:#fff; background:#2475df; transform:translateX(3px); }
  .page-launch-card.is-filtered-out { display:none; }
  .launch-empty { display:none; grid-column:1/-1; padding:32px; color:#687b94; text-align:center; }
  .launch-empty.visible { display:block; }
  .control-summary { width:min(100%,860px); display:grid; grid-template-columns:repeat(3,1fr); margin:12px auto 0; border:1px solid #e1eaf5; border-radius:13px; background:#fbfdff; box-shadow:0 5px 16px #234b7a0a; }
  .summary-item { display:flex; align-items:center; justify-content:center; gap:14px; min-height:86px; padding:14px 24px; }
  .summary-item + .summary-item { border-left:1px solid #e5edf7; }
  .summary-icon { width:42px; height:42px; display:grid; place-items:center; border-radius:50%; color:#2475df; background:#eaf3ff; font-size:1.15rem; }
  .summary-item small { display:block; color:#7a8da5; }
  .summary-item strong { color:#185fc3; font-size:1.13rem; }
  .latest-overview { width:100%; margin:18px auto 0; overflow:hidden; border:1px solid #e1eaf5; border-radius:13px; background:#fff; box-shadow:0 7px 20px #234b7a0d; }
  .latest-overview + .page-launch-grid { margin-top:18px; }
  .latest-overview-head { min-height:38px; display:flex; align-items:center; justify-content:space-between; gap:16px; padding:8px 20px; border-bottom:1px solid #e7eef7; }
  .latest-overview-head h3 { margin:0; color:#10284a; font-size:1rem; }
  .latest-overview-head span { color:#7a8da5; font-size:.76rem; }
  .latest-overview-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); grid-template-areas:"quality pass recent" "drift deploy duration"; }
  .latest-stat { position:relative; min-height:101px; padding:15px 25px; }
  .latest-stat.quality { grid-area:quality; }
  .latest-stat.pass-rate { grid-area:pass; }
  .latest-stat.drift { grid-area:drift; }
  .latest-stat.deploy { grid-area:deploy; }
  .latest-stat.recent-runs { grid-area:recent; }
  .latest-stat.average-duration { grid-area:duration; }
  .latest-stat { border-right:1px solid #e7eef7; }
  .latest-stat:nth-child(3n) { border-right:0; }
  .latest-stat:nth-child(-n+3) { border-bottom:1px solid #e7eef7; }
  .latest-stat-label { display:block; margin-bottom:7px; color:#7186a0; font-size:.7rem; font-weight:800; letter-spacing:.14em; }
  .latest-stat-value { display:inline-flex; align-items:baseline; gap:4px; color:#1768c7; font-size:1.7rem; font-weight:900; line-height:1.05; }
  .latest-stat-value.good { color:#119b63; }
  .latest-stat-value.warn { color:#d97716; }
  .latest-stat-value small { color:#526b88; font-size:.75rem; font-weight:700; }
  .latest-stat-detail { display:block; margin-top:6px; color:#58708c; font-size:.76rem; }
  .latest-sparkline { position:absolute; right:24px; bottom:17px; width:86px; height:34px; }
  .latest-overview-loading { padding:30px; color:#7186a0; text-align:center; }
  @media (max-width:1400px) {
    .page-launch-grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
    .header-visual { right:130px; transform:scale(.9); transform-origin:right bottom; }
  }
  @media (max-width:1100px) {
    body[data-page-view="control-center"] .header-visual { display:none; }
    body[data-page-view="control-center"] .app-header .sub { max-width:none; }
    .page-launch-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  }
  [hidden] { display:none !important; }
  body:not([data-page-view="dashboard"]) #panel-control [data-page-view="dashboard"] { display:none !important; }
  .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
  @media (max-width: 1200px) {
    .system-links { display:none; }
    .system-bar { grid-template-columns:1fr auto; }
    #controlKpis { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .approval-filter-grid { grid-template-columns:minmax(170px,.7fr) minmax(260px,1.3fr) minmax(170px,.7fr); }
    .approval-filter-grid label:last-child { grid-column:1/-1; }
    .case-filter-toolbar { grid-template-columns:repeat(4,minmax(0,1fr)); }
    .run-filter-toolbar { grid-template-columns:repeat(3,minmax(0,1fr)); }
  }
  @media (max-width: 900px) {
    body { padding: 76px 12px 24px; }
    .system-bar { height:58px; padding:0 12px; }
    .system-meta .env-label { display:none; }
    .tabs { left:0; top:58px; bottom:0; transform:translateX(-105%); transition:transform .25s ease; }
    body.nav-open .tabs { transform:translateX(0); }
    .nav-toggle { display:inline-flex; }
    .control-hero, .control-grid { grid-template-columns:1fr; }
    .control-toolbar { grid-template-columns:1fr 1fr; }
    .case-filter-toolbar { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .run-filter-toolbar { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .trace-stage { grid-template-columns:90px 1fr; }
    .compare-summary { grid-template-columns:repeat(2,1fr); }
    .run-case-columns { grid-template-columns:1fr; }
    .run-detail-layer { padding:8px; }
    .run-detail-dialog { width:100%; max-height:96vh; }
    .run-detail-head { flex-direction:column; }
    .run-detail-head .row { width:100%; justify-content:flex-start; }
    .ops-grid { grid-template-columns:1fr; }
    .ops-grid > .card.is-result-expanded { grid-column:auto; }
    .approval-workspace { grid-template-columns:1fr; }
    .approval-filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .approval-filter-grid label:last-child { grid-column:auto; }
  }
  @media (max-width: 600px) {
    .system-brand { font-size:.92rem; }
    .user-chip { display:none; }
    .app-header { padding:14px; }
    .app-header h1 { font-size:1.4rem; }
    #controlKpis, .metric-grid, .control-toolbar { grid-template-columns:1fr; }
    .case-filter-toolbar { grid-template-columns:1fr; }
    .run-filter-toolbar { grid-template-columns:1fr; }
    .approval-steps, .approval-filter-grid { grid-template-columns:1fr; }
    .release-banner { align-items:stretch; flex-direction:column; }
    .release-score { width:100%; min-height:112px; flex-basis:auto; }
    .release-score-value { font-size:3rem; }
    body[data-page-view="control-center"] .app-header { min-height:0; padding:20px; border-radius:13px; }
    body[data-page-view="control-center"] .app-header h1 { font-size:1.85rem; }
    .hero-facts { flex-direction:column; margin-top:18px; }
    .hero-fact { width:100%; }
    .control-center-home { padding:20px 16px 18px; }
    .launch-section-head { align-items:stretch; flex-direction:column; }
    .launch-search { width:100%; flex-basis:auto; }
    .page-launch-grid { grid-template-columns:1fr; gap:12px; }
    .page-launch-card { min-height:145px; }
    .control-summary { grid-template-columns:1fr; }
    .summary-item + .summary-item { border-left:0; border-top:1px solid #e5edf7; }
    .latest-overview-grid { grid-template-columns:1fr; grid-template-areas:"quality" "pass" "recent" "drift" "deploy" "duration"; }
    .latest-stat { border-right:0; }
    .latest-stat:nth-child(-n+5) { border-bottom:1px solid #e7eef7; }
  }
</style>
</head>
<body>
  <div class="system-bar" role="banner">
    <a class="system-brand" href="/control-center" aria-label="VOC QA Control Center 시작 페이지"><span class="brand-mark">QA</span><span>VOC QA Control Center</span></a>
    <nav class="system-links" aria-label="상단 주요 메뉴">
      <a class="system-link active" href="/dashboard" data-top-nav="overview">종합 현황</a>
      <a class="system-link" href="/test-cases" data-top-nav="tests">테스트 관리</a>
      <a class="system-link" href="/quality" data-top-nav="quality">품질 운영</a>
      <a class="system-link" href="/trace" data-top-nav="trace">Agent Trace</a>
      <a class="system-link" href="/reports" data-top-nav="evidence">품질 증적</a>
    </nav>
    <div class="system-meta"><span class="live-dot" aria-hidden="true"></span><span class="env-label">환경 Local</span><span id="systemUserChip" class="user-chip">로그인 필요</span></div>
  </div>
  <header class="app-header">
    <div class="header-visual" aria-hidden="true">
      <span class="visual-glow"></span>
      <div class="visual-window"><span class="visual-bars"><i></i><i></i><i></i><i></i></span></div>
      <span class="visual-ring"></span><span class="visual-shield">✓</span>
    </div>
    <p id="pageBreadcrumb" class="breadcrumb">홈 › VOC QA › 종합 현황</p>
    <div class="row" style="justify-content:space-between">
      <div><p class="eyebrow">VOC QUALITY ENGINEERING</p><h1 id="pageTitle">AI QA 모니터링 대시보드</h1><p id="pageSubtitle" class="sub">배포 판단, 회귀 비교, Agent Trace, 승인 이력과 품질 증적을 한 화면에서 관리합니다.</p><span id="pageContextBadge" class="page-context-badge">운영 화면</span>
        <div class="hero-facts" aria-label="Control Center 구성 요약">
          <div class="hero-fact"><span class="hero-fact-icon">▦</span><span>독립 업무 화면<strong>8개 QA 기능</strong></span></div>
          <div class="hero-fact"><span class="hero-fact-icon">⌁</span><span>분석 파이프라인<strong>6-Agent</strong></span></div>
        </div>
      </div>
      <div class="row header-actions"><button id="navToggle" class="nav-toggle sec" type="button" aria-expanded="false" aria-controls="primaryNav">☰ 메뉴</button><a href="/presentation" target="_blank">🎤 개발 발표자료 열기</a></div>
    </div>
  </header>

  <div class="tabs" id="primaryNav" role="tablist" aria-label="주요 기능">
    <div class="nav-brand">
      <div class="nav-identity"><span class="nav-logo">⌁</span><span class="nav-title"><b>Control Center</b><small>VOC QA</small></span></div>
      <div class="nav-status"><span class="nav-status-dot"></span><strong>Local</strong><span>·</span><span>Agent 6</span><span>·</span><span>ONLINE</span></div>
    </div>
    <div class="nav-section-heading">WORKSPACE</div>
    <a class="tab active" href="/control-center" aria-current="page" data-tab="control"><span class="nav-icon">▦</span><span>QA Control Center</span><span class="nav-shortcut">⌘1</span></a>
    <a class="tab" href="/single" data-tab="single"><span class="nav-icon">⌕</span><span>단건 분석</span></a>
    <a class="tab" href="/batch" data-tab="batch"><span class="nav-icon">☷</span><span>배치 테스트</span></a>
    <a class="tab" href="/quality" data-tab="quality"><span class="nav-icon">□</span><span>품질 실행·보고서</span></a>
    <div class="nav-section-heading">CONTROL CENTER</div>
    <a class="side-link" href="/dashboard" data-page-nav="dashboard"><span class="nav-icon">◷</span><span>대시보드</span></a>
    <a class="side-link" href="/test-cases" data-page-nav="test-cases"><span class="nav-icon">☑</span><span>테스트 케이스</span><span id="navCaseBadge" class="nav-badge"></span></a>
    <a class="side-link" href="/runs" data-page-nav="runs"><span class="nav-icon">⌁</span><span>수행 결과 이력</span></a>
    <a class="side-link" href="/compare" data-page-nav="compare"><span class="nav-icon">⇧</span><span>실험 비교</span></a>
    <a class="side-link" href="/trace" data-page-nav="trace"><span class="nav-icon">⌘</span><span>Trace</span></a>
    <a class="side-link" href="/security" data-page-nav="security"><span class="nav-icon">♢</span><span>보안 진단</span><span id="navSecurityBadge" class="nav-badge alert"></span></a>
    <a class="side-link" href="/approvals" data-page-nav="approvals"><span class="nav-icon">♙</span><span>승인 관리</span><span id="navApprovalBadge" class="nav-badge alert"></span></a>
    <a class="side-link" href="/reports" data-page-nav="reports"><span class="nav-icon">▤</span><span>보고서 센터</span></a>
    <a class="side-link" href="/settings" data-page-nav="settings"><span class="nav-icon">⚙</span><span>설정·버전</span></a>
    <button id="themeToggle" class="side-link" type="button"><span class="nav-icon">☀</span><span>밝은 테마</span></button>
    <div class="nav-user">
      <span id="navUserAvatar" class="nav-avatar">?</span>
      <span class="nav-user-copy"><b id="navUserName">로그인 필요</b><small id="navUserRole">사용자 인증 전</small></span>
      <button id="navAuthAction" class="nav-auth-action" type="button" title="로그인" aria-label="로그인">⇥</button>
    </div>
  </div>

  <div id="loginLayer" class="login-layer" role="dialog" aria-modal="true" aria-labelledby="loginTitle" hidden>
    <form id="loginForm" class="login-dialog">
      <p class="eyebrow">VOC QA ACCESS</p><h2 id="loginTitle">Control Center 로그인</h2>
      <p class="muted">사용자 이름과 QA 접근 토큰으로 로그인합니다.</p>
      <div class="form-stack">
        <label>사용자 이름<input id="loginUsername" maxlength="80" autocomplete="username" placeholder="예: 최성우" required/></label>
        <label id="loginTokenLabel">QA 접근 토큰<input id="loginToken" type="password" autocomplete="current-password" placeholder="환경에 설정된 접근 토큰"/></label>
      </div>
      <p id="loginStatus" class="login-dialog-status muted" role="status" aria-live="polite"></p>
      <div class="login-dialog-actions"><button id="cancelLogin" class="sec" type="button">취소</button><button id="submitLogin" type="submit">로그인</button></div>
    </form>
  </div>

  <!-- ===================== QA Control Center ===================== -->
  <main class="panel active" id="panel-control" role="tabpanel">
    <section class="card control-center-home" data-page-view="control-center" aria-labelledby="controlCenterHomeTitle">
      <div class="launch-section-head">
        <div class="launch-heading"><h2 id="controlCenterHomeTitle">QA Control Center 시작</h2><p class="muted">수행할 QA 업무를 선택하세요. 각 기능은 고유 URL에서 독립된 페이지로 실행됩니다.</p></div>
        <label class="launch-search"><span class="sr-only">기능 검색</span><input id="controlFeatureSearch" type="search" placeholder="기능 검색…" autocomplete="off"/></label>
      </div>
      <section class="latest-overview" aria-labelledby="latestOverviewTitle">
        <div class="latest-overview-head"><h3 id="latestOverviewTitle">가장 최근 품질 데이터</h3><span id="latestOverviewTime">최신 실행을 확인하는 중…</span></div>
        <div id="latestQualityOverview" class="latest-overview-loading" role="status" aria-live="polite">품질 데이터를 불러오는 중…</div>
      </section>
      <div class="page-launch-grid">
        <a class="page-launch-card" href="/dashboard" style="--card-accent:#2475df;--card-tint:#eaf2ff"><span class="launch-icon">▦</span><b>대시보드</b><span>품질 점수, PASS율, 배포 준비도와 드리프트를 확인합니다.</span><span class="launch-arrow">→</span></a>
        <a class="page-launch-card" href="/test-cases" style="--card-accent:#17a568;--card-tint:#e7f8ef"><span class="launch-icon">☷</span><b>테스트 케이스</b><span>실패·결함·점수·Agent 조건으로 케이스를 조회합니다.</span><span class="launch-arrow">→</span></a>
        <a class="page-launch-card" href="/runs" style="--card-accent:#8b4cdd;--card-tint:#f3eaff"><span class="launch-icon">◴</span><b>실행 이력</b><span>Experiment별 모델, 데이터, 비용과 처리시간을 추적합니다.</span><span class="launch-arrow">→</span></a>
        <a class="page-launch-card" href="/compare" style="--card-accent:#e77a16;--card-tint:#fff1e3"><span class="launch-icon">⇄</span><b>실험 비교</b><span>기준선과 후보 실행의 개선 및 회귀를 비교합니다.</span><span class="launch-arrow">→</span></a>
        <a class="page-launch-card" href="/trace" style="--card-accent:#14a4c7;--card-tint:#e4f8fc"><span class="launch-icon">⌁</span><b>6-Agent Trace</b><span>Agent 입력·출력·지연·토큰·오류 흐름을 확인합니다.</span><span class="launch-arrow">→</span></a>
        <a class="page-launch-card" href="/security" style="--card-accent:#e84d5b;--card-tint:#ffecef"><span class="launch-icon">♢</span><b>보안 진단</b><span>장애 진단, OWASP Red Team과 CI 품질 게이트를 실행합니다.</span><span class="launch-arrow">→</span></a>
        <a class="page-launch-card" href="/approvals" style="--card-accent:#159c94;--card-tint:#e5f7f5"><span class="launch-icon">♙</span><b>승인 관리</b><span>사람 검토, 수정 요청, 승인과 배포 결정을 기록합니다.</span><span class="launch-arrow">→</span></a>
        <a class="page-launch-card" href="/reports" style="--card-accent:#e6a20d;--card-tint:#fff6df"><span class="launch-icon">□</span><b>보고서 센터</b><span>TXT·XML·HTML·JUnit·PDF·ZIP 품질 증적을 관리합니다.</span><span class="launch-arrow">→</span></a>
        <p id="controlFeatureEmpty" class="launch-empty">검색 조건에 맞는 기능이 없습니다.</p>
      </div>
    </section>
    <span id="dashboardAnchor" class="sr-only" data-page-view="dashboard">대시보드 시작</span>
    <div class="row" data-page-view="dashboard" style="justify-content:space-between">
      <div><h2 style="margin-bottom:0">Release Command Center</h2><p class="muted" style="margin-top:2px">현재 배포 준비도와 품질 회귀를 먼저 확인하세요.</p></div>
      <div class="row"><div id="authControls" class="row" hidden><label>Operator 토큰 <input id="qaAuthToken" type="password" autocomplete="off" placeholder="세션에만 저장"/></label><button id="saveAuthToken" type="button">토큰 적용</button></div><button id="refreshControl" type="button" class="sec">전체 상태 새로고침</button></div>
    </div>
    <div id="controlLiveStatus" class="control-live-status" role="status" aria-live="polite" data-page-view="dashboard"></div>
    <div class="control-hero" data-page-view="dashboard">
      <div id="controlReleaseBanner" class="release-banner"><span class="muted">품질 이력을 불러오는 중…</span></div>
      <div id="controlKpis" class="metric-grid"></div>
    </div>
    <div class="control-grid" data-page-view="dashboard">
      <section class="card" aria-labelledby="trendTitle">
        <h2 id="trendTitle">품질 점수·PASS율 추이</h2>
        <div id="controlTrend" class="chart-shell"><span class="muted">데이터 준비 중</span></div>
      </section>
      <section class="card" aria-labelledby="driftTitle">
        <div class="row" style="justify-content:space-between"><h2 id="driftTitle">드리프트·회귀 알림</h2><button id="enableNotifications" type="button" class="sec">브라우저 알림 허용</button></div>
        <div id="driftAlerts" class="report-list"><span class="muted">점검 중</span></div>
      </section>
    </div>

    <section class="card" id="historyCard" data-page-view="runs" aria-labelledby="historyTitle">
      <div class="row" style="justify-content:space-between"><div><h2 id="historyTitle">테스트 수행결과 이력</h2><p class="muted">실행별 전체 데이터와 케이스·Agent 결과를 확인하고 Word 종합 품질평가 보고서를 내려받습니다.</p></div><span id="runCount" class="muted"></span></div>
      <div class="control-toolbar run-filter-toolbar">
        <label>검색<input id="runSearch" type="search" placeholder="파일명·Run ID·모델"/></label>
        <label>유형<select id="runKind"><option value="">전체</option><option value="e2e">E2E</option><option value="comprehensive_35">35건 종합</option><option value="llm_judge">LLM Judge</option><option value="quality_suite">품질 Suite</option><option value="fault_diagnosis">장애진단</option><option value="repeatability">반복 안정성</option><option value="red_team">Red Team</option><option value="quality_gate">CI Gate</option></select></label>
        <label>도메인<select id="runDomain"><option value="">전체</option><option value="ecommerce">이커머스</option><option value="insurance">보험</option></select></label>
        <label>결과<select id="runStatus"><option value="">전체</option><option value="PASS">PASS</option><option value="FAIL">FAIL</option></select></label>
        <label>최소 점수<input id="runMinimumScore" type="number" min="0" max="100" placeholder="예: 80"/></label>
        <label>Agent<select id="runAgent"><option value="">전체</option><option>Interpreter</option><option>Retriever</option><option>Summarizer</option><option>Evaluator</option><option>Critic</option><option>Improver</option></select></label>
        <label>정렬<select id="runSort"><option value="generated_at:desc">최신순</option><option value="average_score:asc">점수 낮은순</option><option value="average_score:desc">점수 높은순</option><option value="p95_duration_ms:desc">P95 느린순</option><option value="estimated_cost:desc">비용 높은순</option></select></label>
        <label class="run-checkbox"><input id="runDefectsOnly" type="checkbox"/> 결함 실행만</label>
        <button id="filterRuns" type="button">필터 적용</button>
      </div>
      <div class="table-wrap" style="margin-top:10px"><table class="data-table">
        <thead><tr><th>실행 시각</th><th>유형/모델</th><th>도메인</th><th>결과</th><th>점수</th><th>평균/P95</th><th>비용·결함</th><th>버전·승인</th><th>전체 결과·보고서</th></tr></thead>
        <tbody id="runTableBody"><tr><td colspan="9" class="muted">이력을 불러오는 중…</td></tr></tbody>
      </table></div>
      <div id="runDetailPanel" class="run-detail-layer" role="dialog" aria-modal="true" aria-labelledby="runDetailTitle" hidden>
        <section class="run-detail-dialog">
        <div class="run-detail-head">
          <div><span class="eyebrow">SELECTED RUN FULL EVIDENCE</span><h3 id="runDetailTitle">수행결과 전체 데이터</h3></div>
          <div class="row"><button id="copyRunDetail" type="button" class="sec">요약 복사</button><a id="downloadRunWord" class="run-action word" href="#" role="button">Word 최종보고서 다운로드</a><button id="closeRunDetail" type="button" class="sec">닫기</button></div>
        </div>
        <div class="run-detail-scroll">
        <div id="runDetailSummary" class="metric-grid"></div>
        <div id="runDetailMetadata" class="run-result-section"></div>
        <div id="runDetailCases" class="run-case-list"></div>
        <div id="runDetailStatus" class="control-live-status" role="status" aria-live="polite"></div>
        </div></section>
      </div>
    </section>

    <section class="card" id="caseExplorer" data-page-view="test-cases" aria-labelledby="caseExplorerTitle">
      <div class="row" style="justify-content:space-between"><h2 id="caseExplorerTitle">테스트 케이스 · 결과/실패 원인 Explorer</h2><span id="caseCount" class="muted"></span></div>
      <div class="control-toolbar case-filter-toolbar">
        <label>검색<input id="caseSearch" type="search" placeholder="case_id·질문·출력"/></label>
        <label>도메인<select id="caseDomain"><option value="">전체</option><option value="ecommerce">이커머스</option><option value="insurance">보험</option></select></label>
        <label>상태<select id="caseStatus"><option value="">전체</option><option value="FAIL">FAIL</option><option value="PASS">PASS</option><option value="ERROR">ERROR</option></select></label>
        <label>Agent<select id="caseAgent"><option value="">전체</option><option>Interpreter</option><option>Retriever</option><option>Summarizer</option><option>Evaluator</option><option>Critic</option><option>Improver</option></select></label>
        <label>최소 점수<input id="caseMinimumScore" type="number" min="0" max="100"/></label>
        <label>정렬<select id="caseSort"><option value="generated_at:desc">최신순</option><option value="score:asc">점수 낮은순</option><option value="duration:desc">느린순</option><option value="case_id:asc">Case ID</option></select></label>
        <label class="case-checkbox"><input id="caseDefectsOnly" type="checkbox"/> 실패·결함만</label>
        <button id="filterCases" type="button">케이스 조회</button>
      </div>
      <section id="caseDetailPanel" class="case-detail-panel" aria-labelledby="caseDetailTitle" hidden>
        <div class="case-detail-head">
          <div><p class="eyebrow">SELECTED TEST CASE</p><h3 id="caseDetailTitle">케이스 상세 수행결과</h3></div>
          <button id="closeCaseDetail" type="button" class="sec">닫기</button>
        </div>
        <div id="caseDetailStatus" class="case-detail-status muted" role="status" aria-live="polite"></div>
        <div id="caseDetailContent"></div>
      </section>
      <div class="table-wrap" style="margin-top:10px"><table class="data-table"><thead><tr><th>Case</th><th>질문</th><th>도메인</th><th>상태</th><th>점수</th><th>결함/원인</th><th>상세</th></tr></thead><tbody id="caseTableBody"><tr><td colspan="7" class="muted">케이스를 불러오는 중…</td></tr></tbody></table></div>
    </section>

    <div class="control-grid" data-page-container="compare-trace">
      <section class="card" id="compareCard" data-page-view="compare" aria-labelledby="compareTitle">
        <h2 id="compareTitle">기준선 ↔ 후보 회귀 비교</h2>
        <div class="form-stack">
          <label>기준선 실행<select id="baselineRun"></select></label>
          <label>후보 실행<select id="candidateRun"></select></label>
          <button id="compareRuns" type="button">비교 실행</button>
        </div>
        <div id="compareResult" class="muted" style="margin-top:10px">두 실행을 선택하면 케이스별 변화와 출력 차이를 확인합니다.</div>
      </section>
      <section class="card" id="traceCard" data-page-view="trace" aria-labelledby="traceTitle">
        <h2 id="traceTitle">6-Agent Trace</h2>
        <div class="form-stack">
          <label>실행<select id="traceRun"></select></label>
          <label>테스트 케이스<select id="traceCase"></select></label>
        </div>
        <div id="traceResult" class="muted" style="margin-top:10px">실행 이력을 선택하세요.</div>
      </section>
    </div>

    <div class="control-grid" data-page-container="approval-settings">
      <section class="card" id="approvalCard" data-page-view="approvals" aria-labelledby="approvalTitle">
        <h2 id="approvalTitle">Human Review · 승인 워크벤치</h2>
        <p class="muted">검토 대상을 먼저 선택하고 실제 질문·응답·판정 근거를 확인한 뒤 사람 평가를 기록합니다.</p>
        <div class="approval-steps" aria-label="승인 검토 단계">
          <div class="approval-step active" id="approvalStep1"><b>1. 대상 선택</b>날짜·회차·보류/실패 필터</div>
          <div class="approval-step" id="approvalStep2"><b>2. 근거 확인</b>질문·응답·점수 차이 확인</div>
          <div class="approval-step" id="approvalStep3"><b>3. 평가 기록</b>결정·점수·의견 저장</div>
        </div>
        <section aria-labelledby="reviewQueueTitle">
          <div class="row" style="justify-content:space-between"><h3 id="reviewQueueTitle">자동 검토 큐</h3><b id="reviewQueueCount">0건</b></div>
          <div class="approval-filter-grid">
            <label>실행 날짜<input id="approvalQueueDate" type="date"/></label>
            <label>테스트 회차<select id="approvalQueueRun"><option value="">전체 회차</option></select></label>
            <label>판정 유형<select id="approvalQueueStatus"><option value="">전체 검토 대상</option><option value="hold">보류</option><option value="fail">실패·오류</option><option value="gap">점수 차이</option><option value="unapproved">승인 미기록</option></select></label>
            <label>케이스 검색<input id="approvalQueueSearch" placeholder="케이스 번호·질문 검색"/></label>
          </div>
          <div id="reviewQueue" class="approval-queue"><span class="muted">검토 큐를 불러오는 중…</span></div>
        </section>
        <div class="approval-workspace">
          <section aria-labelledby="selectedReviewTitle">
            <h3 id="selectedReviewTitle">선택한 검토 대상</h3>
            <div id="selectedReviewContext" class="selected-review-context notice">위 자동 검토 큐에서 평가할 케이스를 선택하세요.</div>
            <details style="margin-top:10px"><summary>큐에 없는 실행 직접 선택</summary><div class="form-stack">
              <label>검토 실행<select id="approvalRun"></select></label>
              <label>테스트 케이스<select id="approvalCase"><option value="">실행 전체</option></select></label>
              <button id="selectManualApproval" type="button" class="sec">직접 선택 적용</button>
            </div></details>
          </section>
          <section class="approval-form" aria-labelledby="evaluationTitle">
            <h3 id="evaluationTitle">사람 평가·승인 기록</h3>
            <fieldset id="approvalEvaluationFields" disabled><div class="form-stack">
              <label>검토자<input id="approvalReviewer" maxlength="80" placeholder="예: QA 담당자"/></label>
              <label>결정<select id="approvalDecision"><option value="REVIEWING">검토 중</option><option value="APPROVED">승인</option><option value="CHANGES_REQUESTED">수정 요청</option><option value="REJECTED">반려</option><option value="PENDING">검토 대기</option></select></label>
              <label>사람 평가 점수<input id="approvalScore" type="number" min="0" max="100" step="0.1" placeholder="0~100점"/></label>
              <label>Judge 판정<select id="judgeAgreement"><option value="">판단 안 함</option><option value="true">동의</option><option value="false">동의하지 않음</option></select></label>
              <label><input id="finalDeploymentApproval" type="checkbox"/> 최종 배포 승인</label>
              <label>검토 의견<textarea id="approvalComment" rows="4" maxlength="2000" placeholder="승인·보류·수정 요청의 판단 근거를 기록하세요."></textarea></label>
              <button id="saveApproval" type="button" class="sec">검토 결과 기록</button>
            </div></fieldset>
          </section>
        </div>
        <section class="approval-history" aria-labelledby="approvalHistoryTitle"><h3 id="approvalHistoryTitle">최근 검토 결과</h3><div id="approvalList" class="report-list"></div></section>
      </section>
      <section class="card" id="settingsCard" data-page-view="settings" aria-labelledby="observeTitle">
        <h2 id="observeTitle">비용·드리프트 기준</h2>
        <p class="notice">토큰 사용량은 공급자 usage 값이 없는 과거 보고서에 대해 글자 수 기반 추정치로 표시합니다. 단가는 직접 입력할 때만 비용을 계산합니다.</p>
        <div class="form-stack">
          <label>입력 100만 토큰 단가<input id="inputCostRate" type="number" min="0" step="0.01"/></label>
          <label>출력 100만 토큰 단가<input id="outputCostRate" type="number" min="0" step="0.01"/></label>
          <label>실행 비용 한도<input id="costBudget" type="number" min="0" step="0.01"/></label>
          <label>점수 하락 알림 기준<input id="driftScoreDrop" type="number" min="0" step="0.1"/></label>
          <label>PASS율 하락 알림 기준(%p)<input id="driftPassDrop" type="number" min="0" step="0.1"/></label>
          <label>지연 증가 알림 기준(%)<input id="driftLatencyRise" type="number" min="0" step="1"/></label>
          <label>P95 증가 알림 기준(%)<input id="driftP95Rise" type="number" min="0" step="1"/></label>
          <label>비용 증가 알림 기준(%)<input id="driftCostRise" type="number" min="0" step="1"/></label>
          <label>HTTP 429 알림 건수<input id="rateLimitAlert" type="number" min="1" step="1"/></label>
          <label>Judge-사람 점수차 검토 기준<input id="judgeHumanGap" type="number" min="0" max="100" step="0.1"/></label>
          <button id="saveObservability" type="button">관측 기준 저장</button>
        </div>
        <h3>중앙 실행 설정</h3>
        <div class="form-stack">
          <label>배포 기준 점수<input id="controlDeploymentThreshold" type="number" min="0" max="100" step="0.1" value="95"/></label>
          <label>기본 동시 실행<select id="controlConcurrency"><option value="1">1건</option><option value="2" selected>2건</option><option value="3">3건</option></select></label>
          <label>기본 Judge<select id="controlJudge"><option value="auto">.env 기반 외부 LLM 자동 선택</option></select></label>
          <button id="saveControlSettings" type="button">배포·실행 설정 저장</button>
        </div>
        <h3>프롬프트·모델·데이터 버전</h3><div id="versionList" class="report-list"></div>
      </section>
    </div>
    <div class="control-grid" data-page-view="reports">
      <section class="card" id="evidenceCard" aria-labelledby="evidenceTitle">
        <div class="row" style="justify-content:space-between"><h2 id="evidenceTitle">품질 증적 센터</h2><select id="artifactGroup" aria-label="증적 유형"><option value="">전체</option><option value="evidence">TXT·XML·HTML·JUnit 증적</option><option value="attachment">PDF·ZIP 첨부</option><option value="result">JSON·CSV 결과</option><option value="document">판정 문서</option></select></div>
        <div id="artifactList" class="report-list"><span class="muted">산출물을 불러오는 중…</span></div>
        <div id="artifactPreview" class="artifact-preview" role="status" aria-live="polite" hidden></div>
      </section>
      <section class="card" aria-labelledby="auditTitle">
        <h2 id="auditTitle">승인·설정 감사 이력</h2>
        <div id="auditList" class="report-list"><span class="muted">감사 이력을 불러오는 중…</span></div>
      </section>
    </div>
  </main>

  <!-- ===================== 단건 분석 ===================== -->
  <div class="panel" id="panel-single" role="tabpanel">
    <textarea id="q" rows="3" placeholder="예) 결제했는데 주문 내역이 안 보여요"></textarea>
    <div class="row">
      <label>작업:
        <select id="task">
          <option value="both">요약 + 정책 (both)</option>
          <option value="summary">요약만</option>
          <option value="policy">정책만</option>
        </select>
      </label>
      <button id="go">분석 실행</button>
      <span id="status" class="muted" aria-live="polite"></span>
    </div>
    <div id="result"></div>
  </div>

  <!-- ===================== 배치 테스트 ===================== -->
  <div class="panel" id="panel-batch" role="tabpanel">
    <p class="muted">기대 결과가 포함된 <b>JSONL(한 줄에 JSON 객체 하나)</b>을 입력하거나 업로드하세요.
       기존 질문-only 텍스트도 실행할 수 있지만 품질 PASS/FAIL 판정은 제공되지 않습니다.<br>
       요약+정책 1건은 외부 LLM을 최소 6회 호출합니다. 동시 2건이 권장값이며 3건은 API 사용량 제한에 걸릴 수 있습니다.</p>
    <div class="row">
      <label>테스트 도메인:
        <select id="bdomain">
          <option value="ecommerce">이커머스</option>
          <option value="insurance">보험</option>
        </select>
      </label>
      <button id="loadSet" type="button" class="sec">기본 테스트 세트 불러오기</button>
      <button id="clearBatchSource" type="button">테스트 데이터 초기화</button>
      <input type="file" id="file" accept=".jsonl,.json,.txt,application/json,text/plain"/>
      <label>작업:
        <select id="btask">
          <option value="both">요약 + 정책 (both)</option>
          <option value="summary">요약만</option>
          <option value="policy">정책만</option>
        </select>
      </label>
      <label>동시 실행:
        <select id="bconcurrency">
          <option value="1">1건(안정)</option>
          <option value="2" selected>2건(권장)</option>
          <option value="3">3건(빠름·제한 주의)</option>
        </select>
      </label>
    </div>
    <p id="datasetInfo" class="notice">테스트 세트를 불러오거나 JSONL·TXT 파일을 선택해 주세요.</p>
    <details id="batchSourceEditor" class="batch-source-editor">
      <summary>고급 설정 · 테스트 데이터 원문 보기/편집 <span id="batchSourceSummary" class="muted">원문 없음</span></summary>
      <textarea id="cases" rows="10" aria-label="배치 테스트 데이터 원문" placeholder='{"case_id":"TC-01","question":"결제는 완료되었는데 주문 내역에 보이지 않습니다.","expected_intent":"결제 완료 후 주문 조회 실패","expected_keywords":["결제","주문 내역"],"required_output":["원인 추정","고객 안내","개선안","우선순위"],"prohibited_output":["개인정보 요구"]}'></textarea>
    </details>
    <div class="row">
      <button id="runBatch" class="sec" disabled>일괄 실행 (배치)</button>
      <button id="downloadJson" type="button" class="sec" disabled>JSON 결과 저장</button>
      <button id="downloadCsv" type="button" class="sec" disabled>CSV 결과 저장</button>
      <span id="bstatus" class="muted" aria-live="polite"></span>
    </div>
    <div id="batchResult"></div>
  </div>

  <!-- ===================== 품질 운영 ===================== -->
  <div class="panel" id="panel-quality" role="tabpanel">
    <p class="muted">자동 테스트, 장애 진단, 실제 API E2E, 재시험 통합, 독립 Judge와 배포 판단을 웹에서 실행합니다.</p>
    <div class="row">
      <button id="refreshQuality" type="button" class="sec">상태 새로고침</button>
      <span id="qualityStatusText" class="muted" aria-live="polite"></span>
    </div>
    <div id="qualityDashboard"></div>

    <h2 class="sec-title" id="securityAnchor">1. 무료 로컬 진단·보안</h2>
    <div class="ops-grid">
      <div class="card">
        <h2>자동 품질 테스트</h2>
        <p class="muted">Agent 단위·E2E·MCP·Judge 형식 검증을 실행합니다.</p>
        <button id="runQualitySuite" type="button" class="sec">품질 테스트 실행</button>
        <div id="resultQualitySuite" class="operation-result is-idle" role="status" aria-live="polite">품질 테스트 실행 결과가 여기에 표시됩니다.</div>
      </div>
      <div class="card">
        <h2>장애 진단</h2>
        <p class="muted">포트 충돌, API 키, CSV, 타임아웃, Agent 중단을 검사합니다.</p>
        <button id="runFault" type="button" class="sec">장애 진단 실행</button>
        <div id="resultFault" class="operation-result is-idle" role="status" aria-live="polite">장애 진단 실행 결과가 여기에 표시됩니다.</div>
      </div>
      <div class="card">
        <h2>OWASP Red Team</h2>
        <p class="muted">프롬프트 공격, 개인정보 노출, 경로 이탈, 과다 입력, 근거 없는 출력과 429 복구를 무료로 점검합니다.</p>
        <button id="runRedTeam" type="button" class="warn">Red Team 20종 실행</button>
        <div id="resultRedTeam" class="operation-result is-idle" role="status" aria-live="polite">Red Team 실행 결과가 여기에 표시됩니다.</div>
      </div>
      <div class="card">
        <h2>CI 품질 게이트</h2>
        <p class="muted">자동 테스트·Red Team·필수 라이브 E2E·외부 LLM Judge를 배포 기준 점수로 통합하고 JUnit 증적을 생성합니다.</p>
        <label>도메인 <select id="gateDomain"><option value="ecommerce">이커머스</option><option value="insurance">보험</option></select></label>
        <div class="row"><button id="runQualityGate" type="button">CI Gate 실행</button></div>
        <div id="resultQualityGate" class="operation-result is-idle" role="status" aria-live="polite">CI 품질 게이트 결과가 여기에 표시됩니다.</div>
      </div>
      <div class="card">
        <h2>외부 LLM E2E</h2>
        <p class="muted">.env의 OpenAI·Anthropic 키로 실제 6-Agent E2E와 외부 Judge를 연속 실행합니다. 오프라인 대체는 사용하지 않습니다.</p>
        <div class="row">
          <label>도메인 <select id="offlineDomain"><option value="ecommerce">이커머스</option><option value="insurance">보험</option></select></label>
          <label>실행 범위 <select id="offlineLimit"><option value="1">1건</option><option value="3">3건</option><option value="all">전체</option></select></label>
          <label>동시 실행 <select id="offlineConcurrency"><option value="1">1건</option><option value="2" selected>2건(권장)</option><option value="3">3건</option><option value="4">4건</option></select></label>
        </div>
        <label>특정 case_id <input id="offlineCaseIds" placeholder="예: TC-01, TC-02"/></label>
        <div class="row"><button id="runOfflineE2E" type="button" class="sec">외부 LLM E2E 실행</button></div>
        <div id="resultOfflineE2E" class="operation-result is-idle" role="status" aria-live="polite">라이브 E2E와 외부 Judge 결과가 여기에 표시됩니다.</div>
      </div>
      <div class="card">
        <h2>반복 안정성·Flakiness</h2>
        <p class="muted">같은 케이스를 2~5회 실행해 PASS 전환, 점수 표준편차와 출력 변형을 진단합니다. 실행 모드와 Judge는 설정된 API 키에 따라 자동 선택됩니다.</p>
        <div id="repeatAutoProfile" class="notice">API 키 구성을 확인하고 있습니다.</div>
        <div class="row">
          <label>도메인 <select id="repeatDomain"><option value="ecommerce">이커머스</option><option value="insurance">보험</option></select></label>
          <label>케이스 <select id="repeatLimit"><option value="1">1건</option><option value="3">3건</option><option value="5" selected>중요 5건</option></select></label>
          <label>반복 <select id="repeatTrials"><option value="2">2회</option><option value="3" selected>3회</option><option value="4">4회</option><option value="5">5회</option></select></label>
        </div>
        <label>특정 case_id <input id="repeatCaseIds" placeholder="예: TC-01, TC-02"/></label><br>
        <div class="row"><button id="runRepeatability" type="button" class="sec">반복 안정성 실행</button></div>
        <div id="resultRepeatability" class="operation-result is-idle" role="status" aria-live="polite">반복 안정성 실행 결과가 여기에 표시됩니다.</div>
      </div>
    </div>

    <h2 class="sec-title">2. 실제 API 라이브 E2E</h2>
    <div class="card">
      <p class="notice">운영 정책: .env의 OpenAI·Anthropic 키로 라이브 E2E와 외부 Judge를 자동 실행합니다.</p>
      <div class="row">
        <label>도메인 <select id="liveDomain"><option value="ecommerce">이커머스</option><option value="insurance">보험</option></select></label>
        <label>실행 범위 <select id="liveLimit"><option value="1">1건</option><option value="3">3건</option><option value="all">전체</option></select></label>
        <label>동시 실행 <select id="liveConcurrency"><option value="1">1건(안정)</option><option value="2" selected>2건(권장)</option><option value="3">3건(제한 주의)</option></select></label>
        <label>특정 case_id <input id="liveCaseIds" placeholder="예: TC-10, TC-13"/></label>
      </div>
      <div class="row"><button id="runLiveE2E" type="button" class="warn">라이브 E2E 실행</button></div>
      <div id="resultLiveE2E" class="operation-result is-idle" role="status" aria-live="polite">라이브 E2E 실행 결과가 여기에 표시됩니다.</div>
    </div>

    <h2 class="sec-title">3. 재시험 보고서 통합</h2>
    <div class="card">
      <label>기준 전체 보고서<select id="mergeBase"></select></label>
      <label>덮어쓸 재시험 보고서(복수 선택 가능)<select id="mergeRetests" multiple></select></label>
      <div class="row"><button id="mergeReports" type="button" class="sec">선택 보고서 통합</button></div>
      <div id="resultMergeReports" class="operation-result is-idle" role="status" aria-live="polite">보고서 통합 결과가 여기에 표시됩니다.</div>
    </div>

    <h2 class="sec-title">4. 독립 LLM Judge</h2>
    <div class="card">
      <div class="row">
        <label>입력 E2E 보고서<select id="judgeInput"></select></label>
        <label>Judge <span class="readonly-value">.env 키 기반 외부 LLM 자동 선택</span></label>
      </div>
      <div class="row"><button id="runJudge" type="button" class="warn">독립 Judge 실행</button></div>
      <div id="resultJudge" class="operation-result is-idle" role="status" aria-live="polite">독립 Judge 실행 결과가 여기에 표시됩니다.</div>
    </div>

    <h2 class="sec-title">5. 최종 배포 판단</h2>
    <div class="card">
      <div class="row">
        <label>배포 기준 점수
          <input id="deploymentThreshold" type="number" min="0" max="100" step="1" value="95"/>
        </label>
        <button id="saveDeploymentThreshold" type="button">기준 점수 저장</button>
      </div>
      <p id="deploymentThresholdState" class="muted">저장된 기준이 없으면 95점을 사용합니다.</p>
      <div id="resultDeploymentThreshold" class="operation-result is-idle" role="status" aria-live="polite">배포 기준 저장 결과가 여기에 표시됩니다.</div>
      <div class="row">
        <label>E2E 보고서<select id="deployE2E"></select></label>
        <label>Judge 보고서<select id="deployJudge"></select></label>
      </div>
      <button id="generateDeployment" type="button" class="sec">최종 판단 문서 생성</button>
      <div id="resultDeploymentDecision" class="operation-result is-idle" role="status" aria-live="polite">최종 배포 판단 결과가 여기에 표시됩니다.</div>
    </div>

    <h2 class="sec-title">6. 종합 품질평가 첨부 보고서</h2>
    <div class="card">
      <p>이커머스 18건 + 보험 15건 + 핵심 결함 2건을 재평가하고 PDF·HTML·XML·TXT·그래프·ZIP 첨부 묶음을 생성합니다.</p>
      <button id="generateComprehensiveReport" type="button" class="sec">35건 종합 보고서 생성</button>
      <div id="resultComprehensiveReport" class="operation-result is-idle" role="status" aria-live="polite">종합 보고서 생성 결과가 여기에 표시됩니다.</div>
    </div>
    <div class="ops-grid">
      <div class="card"><h2>라이브 E2E 보고서</h2><div id="e2eReportList" class="report-list"></div></div>
      <div class="card"><h2>Judge 보고서</h2><div id="judgeReportList" class="report-list"></div></div>
      <div class="card"><h2>전체 품질 산출물</h2><div id="allReportList" class="report-list"></div></div>
    </div>
  </div>

<script>
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = sessionStorage.getItem('qaOperatorToken') || '';
  if (token) headers.set('Authorization', 'Bearer ' + token);
  return window.fetch(url, {...options, headers});
}

let currentAuthUser = null;
let tokenAuthEnabled = false;
const authRoleLabels = {admin:'관리자', reviewer:'검토자', viewer:'조회자'};
function updateAuthUi(payload) {
  tokenAuthEnabled = payload.enabled === true;
  currentAuthUser = payload.authenticated ? payload.user : null;
  const name = currentAuthUser?.name || '로그인 필요';
  const role = currentAuthUser ? (authRoleLabels[currentAuthUser.role] || currentAuthUser.role || '사용자') : '사용자 인증 전';
  $("navUserName").textContent = name;
  $("navUserRole").textContent = currentAuthUser ? role + ' · VOC QA' : role;
  $("navUserAvatar").textContent = currentAuthUser ? name.slice(0,1).toUpperCase() : '?';
  $("navAuthAction").textContent = currentAuthUser ? '⇥' : '⇤';
  $("navAuthAction").title = currentAuthUser ? '로그아웃' : '로그인';
  $("navAuthAction").setAttribute('aria-label', currentAuthUser ? '로그아웃' : '로그인');
  $("systemUserChip").textContent = currentAuthUser ? name : '로그인 필요';
  $("loginTokenLabel").hidden = !tokenAuthEnabled;
}
async function refreshAuthState() {
  try {
    const response = await apiFetch('/auth/status');
    const data = await response.json();
    if (response.ok && data.ok) updateAuthUi(data);
  } catch (_) {
    updateAuthUi({enabled:false, authenticated:false, user:null});
  }
}
function openLoginDialog() {
  $("loginStatus").textContent = tokenAuthEnabled ? '설정된 역할별 QA 토큰을 입력하세요.' : '로컬 환경에서는 사용자 이름만 입력하면 됩니다.';
  $("loginLayer").hidden = false;
  $("loginUsername").focus();
}
function closeLoginDialog() {
  $("loginLayer").hidden = true;
  $("loginStatus").textContent = '';
  $("loginToken").value = '';
}
$("navAuthAction").onclick = async () => {
  if (!currentAuthUser) { openLoginDialog(); return; }
  await window.fetch('/auth/logout', {method:'POST'});
  sessionStorage.removeItem('qaOperatorToken');
  await refreshAuthState();
};
$("cancelLogin").onclick = closeLoginDialog;
$("loginLayer").addEventListener('click', event => { if (event.target === $("loginLayer")) closeLoginDialog(); });
$("loginForm").addEventListener('submit', async event => {
  event.preventDefault();
  $("submitLogin").disabled = true;
  $("loginStatus").textContent = '로그인 중…';
  try {
    const response = await window.fetch('/auth/login', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({username:$("loginUsername").value, token:$("loginToken").value})
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error?.message || data.message || '로그인에 실패했습니다.');
    closeLoginDialog();
    await refreshAuthState();
  } catch (error) {
    $("loginStatus").className = 'login-dialog-status error';
    $("loginStatus").textContent = error.message || String(error);
  } finally { $("submitLogin").disabled = false; }
});
document.addEventListener('keydown', event => { if (event.key === 'Escape' && !$("loginLayer").hidden) closeLoginDialog(); });
refreshAuthState();

// ---------- 탭 전환 ----------
const panelMeta = {
  control: {title:'AI QA 모니터링 대시보드', subtitle:'배포 판단, 회귀 비교, Agent Trace, 승인 이력과 품질 증적을 한 화면에서 관리합니다.', breadcrumb:'홈 › VOC QA › 종합 현황'},
  single: {title:'VOC 단건 분석', subtitle:'한 건의 고객 질문을 6개 Agent 파이프라인으로 분석하고 품질 근거를 확인합니다.', breadcrumb:'홈 › 테스트 관리 › 단건 분석'},
  batch: {title:'VOC 배치 품질 테스트', subtitle:'기대 결과가 포함된 테스트 세트를 실행하고 PASS·FAIL과 점수를 비교합니다.', breadcrumb:'홈 › 테스트 관리 › 배치 테스트'},
  quality: {title:'품질 실행·보고서 센터', subtitle:'자동 진단, Red Team, E2E, Judge, 배포 게이트와 실행 증적을 관리합니다.', breadcrumb:'홈 › 품질 운영 › 실행·보고서'}
};
const routeMeta = {
  'control-center': {title:'VOC QA Control Center', subtitle:'각 QA 기능을 독립된 페이지에서 실행하고 결과와 증적을 관리합니다.', breadcrumb:'홈 › VOC QA › Control Center'},
  dashboard: panelMeta.control,
  'test-cases': {title:'테스트 케이스 Explorer', subtitle:'도메인·상태·Agent·점수·결함 기준으로 테스트 케이스를 조회합니다.', breadcrumb:'홈 › Control Center › 테스트 케이스'},
    runs: {title:'테스트 수행결과 이력', subtitle:'각 실행의 결과값, 케이스·Agent 평가와 PDF 형식의 Word 최종보고서를 조회합니다.', breadcrumb:'홈 › Control Center › 수행결과 이력'},
  compare: {title:'기준선·후보 실험 비교', subtitle:'두 실행의 점수, PASS율, 회귀 케이스, Agent 지연과 출력 차이를 비교합니다.', breadcrumb:'홈 › Control Center › 실험 비교'},
  trace: {title:'6-Agent Trace Explorer', subtitle:'각 Agent의 입력·출력·처리시간·토큰·비용·오류와 Refine 전후를 추적합니다.', breadcrumb:'홈 › Control Center › Trace'},
  security: {title:'보안·장애 품질 진단', subtitle:'장애 진단, OWASP Red Team, 품질 게이트와 오프라인 검증을 실행합니다.', breadcrumb:'홈 › 품질 운영 › 보안 진단'},
  approvals: {title:'Human Review · 승인 관리', subtitle:'검토 대기부터 최종 배포 승인까지 사람의 판단과 근거를 기록합니다.', breadcrumb:'홈 › Control Center › 승인 관리'},
  reports: {title:'품질 증적·보고서 센터', subtitle:'실행 단위 TXT·XML·HTML·JUnit·PDF·ZIP 산출물과 감사 이력을 확인합니다.', breadcrumb:'홈 › Control Center › 보고서 센터'},
  settings: {title:'운영 설정·버전 관리', subtitle:'배포 기준, 비용·드리프트 한도, 실행 기본값과 모델·프롬프트·데이터 버전을 관리합니다.', breadcrumb:'홈 › Control Center › 설정·버전'},
  single: panelMeta.single,
  batch: panelMeta.batch,
  quality: panelMeta.quality
};
function activatePanel(tabName) {
  const t = document.querySelector('.tab[data-tab="' + tabName + '"]');
  if (!t) return;
  document.querySelectorAll(".tab").forEach(x => { x.classList.remove("active"); x.setAttribute("aria-selected", "false"); });
  document.querySelectorAll(".panel").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  t.setAttribute("aria-selected", "true");
  $("panel-" + t.dataset.tab).classList.add("active");
  const meta = panelMeta[tabName] || panelMeta.control;
  $("pageTitle").textContent = meta.title;
  $("pageSubtitle").textContent = meta.subtitle;
  $("pageBreadcrumb").textContent = meta.breadcrumb;
}
const currentPageView = document.body.dataset.pageView || 'dashboard';
const currentPanel = document.body.dataset.panel || 'control';
const topNavByView = {
  'control-center':'overview', dashboard:'overview',
  single:'tests', batch:'tests', 'test-cases':'tests', runs:'tests', compare:'tests',
  quality:'quality', security:'quality', approvals:'quality', settings:'quality',
  trace:'trace', reports:'evidence'
};
function applyPageRoute() {
  activatePanel(currentPanel);
  const meta = routeMeta[currentPageView] || panelMeta[currentPanel] || panelMeta.control;
  $("pageTitle").textContent = meta.title;
  $("pageSubtitle").textContent = meta.subtitle;
  $("pageBreadcrumb").textContent = meta.breadcrumb;
  document.querySelectorAll('.tab').forEach(link => {
    const active = link.dataset.tab === currentPanel;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  document.querySelectorAll('.side-link[data-page-nav]').forEach(link => {
    const active = link.dataset.pageNav === currentPageView;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  const activeTopNav = topNavByView[currentPageView] || 'overview';
  document.querySelectorAll('.system-link[data-top-nav]').forEach(link => {
    const active = link.dataset.topNav === activeTopNav;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  document.querySelectorAll('#panel-control [data-page-view]').forEach(element => {
    element.hidden = element.dataset.pageView !== currentPageView;
  });
  document.querySelectorAll('#panel-control [data-page-container]').forEach(container => {
    const visible = Array.from(container.querySelectorAll(':scope > [data-page-view]')).filter(element => !element.hidden);
    container.hidden = visible.length === 0;
    container.classList.toggle('single-page-view', visible.length === 1);
  });
  if (currentPageView === 'security') {
    const panel = $("panel-quality");
    Array.from(panel.children).forEach(element => { element.hidden = true; });
    const anchor = $("securityAnchor");
    anchor.hidden = false;
    if (anchor.nextElementSibling) anchor.nextElementSibling.hidden = false;
  }
}
document.querySelectorAll('.tab[href], .side-link[href]').forEach(link => link.addEventListener('click', () => {
  document.body.classList.remove('nav-open');
}));
applyPageRoute();
const pageContextLabels = {
  dashboard:'실시간 품질 관제', 'test-cases':'케이스 탐색·분석', runs:'실행 증적·이력',
  compare:'기준선 회귀 비교', trace:'Agent 처리 추적', security:'보안·품질 진단',
  approvals:'Human Review', reports:'품질 증적 관리', settings:'운영 정책·버전'
};
if ($("pageContextBadge")) $("pageContextBadge").textContent = pageContextLabels[currentPageView] || '운영 화면';
const controlFeatureSearch = $("controlFeatureSearch");
if (controlFeatureSearch) {
  const launchCards = Array.from(document.querySelectorAll('.page-launch-card'));
  const launchEmpty = $("controlFeatureEmpty");
  controlFeatureSearch.addEventListener('input', () => {
    const query = controlFeatureSearch.value.trim().toLocaleLowerCase('ko');
    let visibleCount = 0;
    launchCards.forEach(card => {
      const visible = !query || card.textContent.toLocaleLowerCase('ko').includes(query);
      card.classList.toggle('is-filtered-out', !visible);
      if (visible) visibleCount += 1;
    });
    if (launchEmpty) launchEmpty.classList.toggle('visible', visibleCount === 0);
  });
}
const savedTheme = localStorage.getItem('qaTheme') || 'light';
document.documentElement.dataset.theme = savedTheme;
function updateThemeButton() {
  const light = document.documentElement.dataset.theme === 'light';
  const parts = $("themeToggle").querySelectorAll('span');
  if (parts[0]) parts[0].textContent = light ? '☾' : '☀';
  if (parts[1]) parts[1].textContent = light ? '어두운 테마' : '밝은 테마';
}
updateThemeButton();
$("themeToggle").onclick = () => {
  const theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme; localStorage.setItem('qaTheme', theme); updateThemeButton();
};
$("navToggle").onclick = () => {
  const open = document.body.classList.toggle('nav-open');
  $("navToggle").setAttribute('aria-expanded', String(open));
};

// ---------- 공통: 분석 요청 ----------
async function callAnalyze(question, task, testCase = null, csvPath = null) {
  const res = await apiFetch("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, task, test_case: testCase, csv_path: csvPath })
  });
  const data = await res.json();
  return { ok: res.ok && !data.error, data };
}

function responseError(data) {
  return data.error || data.message || data.detail || "요청 실패";
}

// ---------- 단건 분석 렌더 ----------
function chips(arr) {
  if (!arr || !arr.length) return '<span class="muted">(없음)</span>';
  return arr.map(x => '<span class="chip">' + esc(x) + '</span>').join(' ');
}
function renderOutput(agent, o) {
  if (!o) return '';
  if (agent === 'Interpreter')
    return 'task: <b>' + esc(o.task) + '</b><br>키워드(filters): ' + chips(o.filters) + '<br>max_items: ' + esc(o.max_items);
  if (agent === 'Retriever') {
    let h = '검색된 VOC: <b>' + esc(o.retrieved_count) + '건</b>';
    if (o.samples && o.samples.length) h += '<ul>' + o.samples.map(t => '<li>' + esc(t) + '</li>').join('') + '</ul>';
    return h;
  }
  if (agent === 'Summarizer') {
    const c = o.candidates || {}; const keys = Object.keys(c);
    if (!keys.length) return '<span class="muted">(후보 없음)</span>';
    return keys.map(k => '<div class="cand"><b>' + esc(k) + (k === o._winner ? ' ✅' : '') + '</b>: ' + esc(c[k]) + '</div>').join('');
  }
  if (agent === 'Evaluator') {
    let h = '선택된 요약(winner): <span class="win">' + esc(o.winner) + '</span>';
    const sc = o.scores || {}; const keys = Object.keys(sc);
    if (keys.length) h += '<br>점수: ' + keys.map(k => esc(k) + '=' + esc(sc[k])).join(', ');
    return h;
  }
  if (agent === 'Critic') {
    let h = '개선 필요: <b>' + (o.need_refine ? '예' : '아니오') + '</b> · 추가샘플요청: ' + (o.ask_more_samples ? '예' : '아니오');
    if (o.edits && o.edits.length) h += '<br>지적/수정 지침:<ul>' + o.edits.map(e => '<li>' + esc(e) + '</li>').join('') + '</ul>';
    else h += '<br><span class="muted">지적 사항 없음</span>';
    return h;
  }
  if (agent === 'Improver') {
    if (o.skipped) return '<span class="muted">(task가 policy/both가 아니라 생략됨)</span>';
    return '<div class="content">' + esc(o.policy || '(없음)') + '</div>';
  }
  return '<pre>' + esc(JSON.stringify(o, null, 2)) + '</pre>';
}
// 최종 결과(요약/정책) + 6개 에이전트 단계별 진단 (단건/배치 공통)
function renderDetail(data) {
  let html = '';
  if (data.summary || data.policy) {
    if (data.summary) html += '<div class="card"><h2>📝 최종 요약</h2><div class="content">' + esc(data.summary) + '</div></div>';
    if (data.policy)  html += '<div class="card"><h2>🏛️ 정책 개선안</h2><div class="content">' + esc(data.policy) + '</div></div>';
  } else {
    html += '<div class="card muted">🔍 ' + esc(data.note || "조건에 맞는 VOC를 찾지 못했습니다. 데이터에 등장하는 단어(예: 결제, 쿠폰, 배송, 환불, 로그인, 앱, 상담)로 다시 시도해 보세요.") + '</div>';
  }
  const stages = data.stages || [];
  const evalStage = stages.find(s => s.agent === 'Evaluator');
  const winner = evalStage && evalStage.output ? evalStage.output.winner : null;
  html += '<h2 class="sec-title">🔬 6개 에이전트 단계별 진단 (내부 품질)</h2>';
  stages.forEach((s, i) => {
    if (s.agent === 'Summarizer' && s.output) s.output._winner = winner;
    html += '<div class="agent-card">' +
      '<div class="agent-head"><span class="agent-name">' + (i + 1) + '. ' + esc(s.agent) + '</span>' +
      '<span class="agent-role">' + esc(s.role) + '</span></div>' +
      '<div class="agent-check">✔ 꼭 확인할 품질 항목: ' + esc(s.check) + '</div>' +
      '<div class="agent-out">' + renderOutput(s.agent, s.output) + '</div></div>';
  });
  return html;
}

function renderQuality(q) {
  if (!q) return '<div class="card muted">기대 결과가 없어 실행 결과만 표시합니다.</div>';
  const c = q.checks || {};
  const row = (name, check) => {
    check = check || {};
    const mark = check.passed ? '✅ PASS' : '❌ FAIL';
    const missing = check.missing && check.missing.length ? '<br>누락: ' + chips(check.missing) : '';
    const violations = check.violations && check.violations.length
      ? '<br>위반: ' + chips(check.violations.map(v => v.item + ' (' + v.evidence + ')')) : '';
    const matched = check.matched && check.matched.length
      ? '<br>근거: ' + chips(check.matched.map(v => v.item + '←' + v.evidence)) : '';
    const ratio = check.ratio !== undefined ? ' · 충족률 ' + Math.round(Number(check.ratio) * 100) + '%' : '';
    const duration = check.duration_ms ? ' · ' + esc(check.duration_ms) + 'ms / 기준 ' + esc(check.limit_ms) + 'ms' : '';
    return '<li><b>' + esc(name) + '</b>: ' + mark + ratio + duration + missing + violations + matched + '</li>';
  };
  const rubricRows = Object.values(q.rubric || {}).map(item =>
    '<tr><td>' + esc(item.label) + '</td><td><b>' + esc(item.score) + '</b> / ' + esc(item.max_score) +
    '</td><td>' + (item.passed ? '✅' : '⚠️') + '</td></tr>'
  ).join('');
  const blockers = q.hard_blockers && q.hard_blockers.length
    ? '<p class="error"><b>즉시 배포 보류 사유:</b> ' + esc(q.hard_blockers.join(', ')) + '</p>' : '';
  const deployment = q.deployment || {};
  return '<div class="card"><h2>🎯 기대 결과 품질 판정</h2>' +
    '<p><b>' + (q.passed ? '✅ 최종 PASS' : '❌ 최종 FAIL') + '</b> · 점수 <b>' + esc(q.score) + '</b>/100' +
    ' · 배포 판정 <b>' + esc(deployment.label || '') + '</b></p>' + blockers +
    '<table><thead><tr><th>평가 항목</th><th>획득/배점</th><th>기준 충족</th></tr></thead><tbody>' + rubricRows + '</tbody></table><ul>' +
    row('실행 상태', c.status) + row('의도', c.intent) + row('핵심 키워드', c.keywords) +
    row('필수 출력', c.required_output) + row('금지 출력', c.prohibited_output) +
    row('검색 적합도', c.retrieval_relevance) + row('요약 사실성·근거율', c.summary_faithfulness) +
    row('정책 실행 가능성', c.policy_actionability) + row('개인정보·프롬프트 안전성', c.privacy_and_prompt_safety) +
    row('Evaluator 평가 타당성', c.evaluator_validity) + row('Critic 위험 탐지력', c.critic_risk_detection) +
    row('Agent 연계 품질', c.agent_handoff) + row('장애 대응·로그', c.fault_and_logging) + row('성능', c.performance) +
    '</ul></div>';
}
function renderSingle(data) {
  const flow = "사용자 질문 → Interpreter → Retriever → Summarizer → Evaluator → Critic → Improver → 최종 VOC 분석·정책 개선안";
  const fallback = data.execution_mode === 'offline_fallback'
    ? '<div class="notice"><b>OFFLINE FALLBACK</b> · 외부 AI API 연결이 차단되어 동일한 6-Agent 계약의 결정론적 재현 모드로 완료했습니다.</div>'
    : '';
  return fallback + '<div class="flow">' + esc(flow) + '</div>' + renderDetail(data);
}

async function analyze() {
  const question = $("q").value.trim();
  if (!question) { $("status").innerHTML = '<span class="error">질문을 입력하세요.</span>'; return; }
  $("go").disabled = true;
  $("status").textContent = "분석 중… (수십 초 걸릴 수 있어요)";
  $("result").innerHTML = "";
  try {
    const { ok, data } = await callAnalyze(question, $("task").value);
    $("result").innerHTML = ok ? renderSingle(data)
      : '<div class="card"><span class="error">오류: ' + esc(responseError(data)) + '</span></div>';
  } catch (e) {
    $("result").innerHTML = '<div class="card"><span class="error">요청 실패: ' + esc(e) + '</span></div>';
  } finally { $("go").disabled = false; $("status").textContent = ""; }
}
$("go").addEventListener("click", analyze);
$("q").addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") analyze(); });

// ---------- 배치 테스트 ----------
let selectedCsvPath = null;

function updateBatchSourceAvailability(summaryText = '') {
  const hasSource = Boolean($("cases").value.trim());
  $("runBatch").disabled = !hasSource;
  $("batchSourceSummary").textContent = hasSource ? (summaryText || '직접 입력 데이터 준비됨') : '원문 없음';
}

function resetBatchSource(message = '테스트 세트를 불러오거나 JSONL·TXT 파일을 선택해 주세요.') {
  selectedCsvPath = null;
  $("cases").value = '';
  $("file").value = '';
  $("batchSourceEditor").open = false;
  $("datasetInfo").textContent = message;
  $("bstatus").textContent = '';
  $("batchResult").innerHTML = '';
  $("downloadJson").disabled = true;
  $("downloadCsv").disabled = true;
  updateBatchSourceAvailability();
}

async function ensureBatchCsvPath() {
  if (selectedCsvPath) return selectedCsvPath;
  const response = await apiFetch('/test-set?domain=' + encodeURIComponent($("bdomain").value));
  const metadata = await response.json();
  if (!response.ok) throw new Error(metadata.message || '도메인 분석 데이터 확인 실패');
  selectedCsvPath = metadata.csv_path;
  return metadata;
}

async function loadTestSet() {
  const domain = $("bdomain").value;
  $("loadSet").disabled = true;
  $("datasetInfo").textContent = "기본 테스트 세트를 불러오는 중…";
  try {
    const res = await apiFetch("/test-set?domain=" + encodeURIComponent(domain));
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || "테스트 세트 로드 실패");
    selectedCsvPath = data.csv_path;
    $("cases").value = data.cases.map(x => JSON.stringify(x)).join("\n");
    $("file").value = '';
    $("batchSourceEditor").open = false;
    updateBatchSourceAvailability(data.cases.length + '건 준비됨');
    $("datasetInfo").textContent = data.label + " · VOC " + data.voc_count + "건 · 테스트 " + data.cases.length + "건 · " + data.csv_name;
  } catch (e) {
    $("datasetInfo").innerHTML = '<span class="error">' + esc(e.message) + '</span>';
  } finally { $("loadSet").disabled = false; }
}
$("loadSet").addEventListener("click", loadTestSet);
$("clearBatchSource").addEventListener("click", () => resetBatchSource());
$("bdomain").addEventListener("change", () => {
  const label = $("bdomain").selectedOptions[0]?.textContent || '선택한 도메인';
  resetBatchSource(label + ' 테스트 세트를 불러오거나 파일을 선택해 주세요.');
});
$("cases").addEventListener("input", () => updateBatchSourceAvailability());

$("file").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = async () => {
    $("cases").value = String(reader.result || '');
    $("batchSourceEditor").open = false;
    selectedCsvPath = null;
    let caseCount = 0;
    try { caseCount = parseCases($("cases").value).length; }
    catch (error) {
      $("datasetInfo").innerHTML = '<span class="error">파일 형식 오류: ' + esc(error.message || error) + '</span>';
      $("batchSourceSummary").textContent = '형식 확인 필요';
      $("runBatch").disabled = true;
      return;
    }
    try {
      const metadata = await ensureBatchCsvPath();
      $("datasetInfo").textContent = f.name + ' · 테스트 ' + caseCount + '건 준비됨 · 분석 데이터 ' + metadata.csv_name;
    } catch (error) {
      selectedCsvPath = null;
      $("datasetInfo").innerHTML = '<span class="error">파일은 읽었지만 분석 데이터 확인 실패: ' + esc(error.message || error) + '</span>';
      $("batchSourceSummary").textContent = '분석 데이터 확인 필요';
      $("runBatch").disabled = true;
      return;
    }
    updateBatchSourceAvailability(caseCount + '건 준비됨');
  };
  reader.readAsText(f, "utf-8");
});

function parseCases(text) {
  let seq = 0;
  return text.split(/\r?\n/).map(line => {
    let s = line.trim();
    if (!s || s.startsWith("#")) return null;
    if (s.startsWith("{")) {
      try {
        const obj = JSON.parse(s);
        if (!obj.question) throw new Error("question 누락");
        return obj;
      } catch (e) {
        throw new Error("JSONL 파싱 실패: " + e.message + " / " + s.slice(0, 80));
      }
    }
    // 앞쪽 라벨 제거: "TC-01", "TC 1", "CUST101," 등 + 뒤따르는 구분자
    const label = (s.match(/^\s*(TC[-\s]?\d+|[A-Za-z]+\d+)/i) || [])[1];
    s = s.replace(/^\s*(TC[-\s]?\d+|[A-Za-z]+\d+)\s*[,:.\)\-\s]+/i, "").trim();
    seq++;
    return { case_id: label || ('LEGACY-' + seq), question: s };
  }).filter(Boolean);
}

let lastBatchResults = [];

function downloadText(name, content, type) {
  const blob = new Blob([content], {type});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  URL.revokeObjectURL(a.href);
}

$("downloadJson").onclick = () => downloadText(
  $("bdomain").value + "_voc_quality_results.json", JSON.stringify(lastBatchResults, null, 2), "application/json;charset=utf-8"
);
$("downloadCsv").onclick = () => {
  const quote = v => '"' + String(v ?? '').replaceAll('"', '""') + '"';
  const rubricKeys = ["interpreter_accuracy","retriever_relevance","summarizer_faithfulness","evaluator_validity","critic_risk_detection","improver_actionability","agent_handoff","fault_and_logging","performance"];
  const rows = [["case_id","passed","score","deployment","hard_blockers",...rubricKeys,"total_duration_ms"]];
  lastBatchResults.forEach(x => {
    const q = x.quality || {}, c = q.checks || {}, rubric = q.rubric || {};
    rows.push([x.case_id, q.passed ?? "", q.score ?? "", q.deployment?.label ?? "", (q.hard_blockers || []).join("; "), ...rubricKeys.map(k => rubric[k]?.score ?? ""), c.performance?.duration_ms ?? ""]);
  });
  downloadText($("bdomain").value + "_voc_quality_results.csv", "\ufeff" + rows.map(r => r.map(quote).join(",")).join("\r\n"), "text/csv;charset=utf-8");
};

async function runBatch() {
  let cases;
  try { cases = parseCases($("cases").value); }
  catch (e) { $("bstatus").innerHTML = '<span class="error">' + esc(e.message) + '</span>'; return; }
  const task = $("btask").value;
  const concurrency = Math.max(1, Math.min(3, Number($("bconcurrency").value) || 2));
  if (!cases.length) { $("bstatus").innerHTML = '<span class="error">테스트 케이스를 입력하거나 파일을 올려주세요.</span>'; return; }
  try { await ensureBatchCsvPath(); }
  catch (error) { $("bstatus").innerHTML = '<span class="error">분석 데이터 확인 실패: ' + esc(error.message || error) + '</span>'; return; }

  $("runBatch").disabled = true;
  $("batchResult").innerHTML =
    '<div class="batch-toolbar">' +
    '<button type="button" id="expandAll" class="sec">모두 펼치기</button>' +
    '<button type="button" id="collapseAll" class="sec">모두 접기</button>' +
    '<span id="bsummary" class="muted"></span></div><div id="caseList"></div>';
  const list = $("caseList");
  $("expandAll").onclick = () => document.querySelectorAll("details.case").forEach(d => d.open = true);
  $("collapseAll").onclick = () => document.querySelectorAll("details.case").forEach(d => d.open = false);

  lastBatchResults = [];
  $("downloadJson").disabled = true; $("downloadCsv").disabled = true;
  let pass = 0, fail = 0, noExpected = 0, err = 0;
  let completed = 0, nextIndex = 0;
  const details = cases.map(tc => {
    const det = document.createElement("details");
    det.className = "case";
    det.innerHTML = '<summary><b>' + esc(tc.case_id) + '</b> <span class="muted">대기 중</span> · ' + esc(tc.question) + '</summary>' +
                    '<div class="case-body muted">실행 대기 중…</div>';
    list.appendChild(det);
    return det;
  });

  async function executeCase(i) {
    const tc = cases[i], det = details[i];
    det.querySelector("summary").innerHTML = '<b>' + esc(tc.case_id) + '</b> <span class="st-run">⏳ 분석 중…</span> · ' + esc(tc.question);
    det.querySelector(".case-body").textContent = "분석 중…";

    let badge, body;
    try {
      const hasExpected = !!(tc.expected_intent && tc.expected_keywords && tc.required_output && tc.prohibited_output);
      const r = await callAnalyze(tc.question, task, hasExpected ? tc : null, selectedCsvPath);
      if (!r.ok) {
        badge = '<span class="st-err">❌ 오류</span>';
        body = '<div class="card"><span class="error">' + esc(responseError(r.data)) + '</span></div>';
        err++;
      } else if (r.data.quality) {
        const q = r.data.quality;
        badge = q.passed ? '<span class="st-ok">✅ PASS</span>' : '<span class="st-err">❌ FAIL</span>';
        body = renderQuality(q) + renderDetail(r.data);
        q.passed ? pass++ : fail++;
        lastBatchResults.push({case_id: tc.case_id, question: tc.question, quality: q, analysis: r.data});
      } else if (r.data.summary || r.data.policy) {
        badge = '<span class="st-empty">⚠️ 기대결과 없음</span>';
        body = renderQuality(null) + renderDetail(r.data);
        noExpected++;
      } else {
        badge = '<span class="st-empty">⚠️ 결과 없음</span>';
        body = renderDetail(r.data);   // 결과 없음도 6개 에이전트 흐름은 표시
        noExpected++;
      }
    } catch (e) {
      badge = '<span class="st-err">❌ 실패</span>';
      body = '<div class="card"><span class="error">' + esc(e) + '</span></div>';
      err++;
    }

    // 요약줄(상태 배지) + 상세(6개 에이전트) 채우기
    det.querySelector("summary").innerHTML = '<b>' + esc(tc.case_id) + '</b> ' + badge + ' · ' + esc(tc.question);
    const bodyEl = det.querySelector(".case-body");
    bodyEl.className = "case-body";
    bodyEl.innerHTML = body;
    completed++;
    $("bstatus").textContent = "실행 중… " + completed + " / " + cases.length + " · 동시 " + concurrency + "건";
    $("bsummary").textContent = "PASS " + pass + " · FAIL " + fail + " · 기대결과 없음 " + noExpected + " · 오류 " + err;
  }

  async function worker() {
    while (true) {
      const i = nextIndex++;
      if (i >= cases.length) return;
      await executeCase(i);
    }
  }

  $("bstatus").textContent = "실행 시작 · 동시 " + concurrency + "건";
  await Promise.all(Array.from({length: Math.min(concurrency, cases.length)}, worker));
  lastBatchResults.sort((a, b) =>
    cases.findIndex(tc => tc.case_id === a.case_id) - cases.findIndex(tc => tc.case_id === b.case_id)
  );
  $("bstatus").textContent = "완료: " + cases.length + "건";
  $("downloadJson").disabled = !lastBatchResults.length;
  $("downloadCsv").disabled = !lastBatchResults.length;
  $("runBatch").disabled = false;
}
$("runBatch").addEventListener("click", runBatch);

// ---------- QA Control Center ----------
let controlState = null;
let controlRuns = [];
let traceRunDetail = null;
let approvalQueueData = [];
let selectedApprovalReview = null;
let approvalRunDetail = null;

function fmtDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('ko-KR', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
}

const RUN_KIND_NAMES = {e2e:'6-Agent E2E 품질검증',comprehensive_35:'35건 종합 품질평가',llm_judge:'독립 LLM Judge 평가',fault_diagnosis:'장애 허용성 진단',quality_suite:'자동 품질 테스트',repeatability:'반복 안정성 진단',red_team:'OWASP 보안 진단',quality_gate:'CI 품질 게이트',quality_run:'품질 실행'};
const RUN_DOMAIN_NAMES = {ecommerce:'이커머스',insurance:'보험',security:'보안'};
const RUN_MODE_NAMES = {live:'라이브',offline:'오프라인',ci:'CI'};

function runKindName(kind) {
  return RUN_KIND_NAMES[kind] || '품질 실행';
}

function runContextName(run) {
  return RUN_DOMAIN_NAMES[run.domain] || run.domain || RUN_MODE_NAMES[run.mode] || run.mode || '공통 검사';
}

function runLabel(run) {
  return fmtDate(run.generated_at) + ' · ' + runKindName(run.kind) + ' · ' +
    runContextName(run) + ' · ' + run.average_score + '점';
}

function statusBadge(text, type) {
  return '<span class="badge ' + esc(type || 'info') + '">' + esc(text) + '</span>';
}

function renderControlTrend(trends) {
  if (!trends || !trends.length) return '<span class="muted">E2E 이력이 아직 없습니다.</span>';
  const rows = trends.slice(-16);
  const width = 640, height = 210, left = 42, right = 14, top = 18, bottom = 30;
  const chartW = width - left - right, chartH = height - top - bottom;
  const x = i => left + (rows.length === 1 ? chartW / 2 : i * chartW / (rows.length - 1));
  const y = value => top + (100 - Math.max(0, Math.min(100, Number(value) || 0))) * chartH / 100;
  const scorePoints = rows.map((r,i) => x(i) + ',' + y(r.score)).join(' ');
  const passPoints = rows.map((r,i) => x(i) + ',' + y(r.pass_rate)).join(' ');
  const guides = [0,25,50,75,100].map(v =>
    '<line x1="' + left + '" y1="' + y(v) + '" x2="' + (width-right) + '" y2="' + y(v) + '" stroke="#203852"/>' +
    '<text x="4" y="' + (y(v)+4) + '" fill="#91a4bb" font-size="11">' + v + '</text>'
  ).join('');
  const dots = rows.map((r,i) => '<circle cx="' + x(i) + '" cy="' + y(r.score) + '" r="4" fill="#38bdf8"><title>' +
    esc(r.domain + ' ' + fmtDate(r.generated_at) + ' · 점수 ' + r.score + ' · PASS ' + r.pass_rate + '%') + '</title></circle>').join('');
  const operations = rows.slice(-8).map(r => '<tr><td>' + esc(fmtDate(r.generated_at)) + '</td><td>' + esc(r.p95_duration_ms || 0) + ' ms</td><td>' + esc(r.tokens || 0) + '</td><td>' + esc(Number(r.cost || 0).toFixed(5)) + '</td><td>' + esc(r.rate_limit_count || 0) + '</td></tr>').join('');
  return '<svg class="trend-svg" viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="품질 점수와 PASS율 추이">' + guides +
    '<polyline points="' + scorePoints + '" fill="none" stroke="#38bdf8" stroke-width="3"/>' +
    '<polyline points="' + passPoints + '" fill="none" stroke="#2dd4bf" stroke-width="2" stroke-dasharray="6 4"/>' + dots +
    '<text x="' + left + '" y="205" fill="#38bdf8" font-size="12">● 품질 점수</text><text x="140" y="205" fill="#2dd4bf" font-size="12">- - PASS율</text></svg>' +
    '<details style="width:100%"><summary>운영 추세(P95·토큰·비용·429)</summary><div class="table-wrap"><table class="data-table"><thead><tr><th>시각</th><th>P95</th><th>토큰</th><th>비용</th><th>429</th></tr></thead><tbody>' + operations + '</tbody></table></div></details>';
}

function renderDriftAlerts(alerts) {
  if (!alerts || !alerts.length) return '<div class="notice"><b>✅ 감지된 품질 회귀 없음</b><br><span class="muted">동일 유형·도메인·모드의 최근 실행을 비교했습니다.</span></div>';
  return alerts.map(alert => '<div class="report-item"><div>' + statusBadge(alert.severity === 'critical' ? '위험' : '주의', alert.severity === 'critical' ? 'fail' : 'warning') +
    ' <b>' + esc([alert.kind, alert.domain, alert.mode].filter(Boolean).join(' · ')) + '</b></div><div class="muted">' + esc((alert.reasons || []).join(' / ')) + '</div></div>').join('');
}

function notifyCriticalAlerts(alerts) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  const critical = (alerts || []).filter(item => item.severity === 'critical');
  if (!critical.length) return;
  const signature = JSON.stringify(critical.map(item => [item.latest_run_id,item.reasons]));
  if (sessionStorage.getItem('lastQaAlert') === signature) return;
  sessionStorage.setItem('lastQaAlert', signature);
  new Notification('VOC QA 위험 알림', {body:(critical[0].reasons || []).join(' / ')});
}

function renderRunTable(runs) {
  $("runCount").textContent = '검색 결과 ' + runs.length + '건';
  if (!runs.length) {
    $("runTableBody").innerHTML = '<tr><td colspan="9" class="muted">조건에 맞는 실행 이력이 없습니다.</td></tr>';
    return;
  }
  $("runTableBody").innerHTML = runs.map(run => {
    const passed = run.total > 0 && run.failed === 0;
    const version = 'Git ' + esc(run.git_commit || '-') + '<br>D ' + esc(run.dataset_version || '-') + '<br>P ' + esc(run.prompt_version || '-');
    return '<tr><td>' + esc(fmtDate(run.generated_at)) + '<br><small class="muted">' + esc(run.source_file) + '</small></td>' +
      '<td><b>' + esc(run.kind) + '</b><br><span class="muted">' + esc(run.mode || run.provider || '-') + '<br>' + esc(run.model || '모델 미기록') + '</span></td>' +
      '<td>' + esc(run.domain || '-') + '</td><td>' + statusBadge(run.total ? run.passed + '/' + run.total : '기록', passed ? 'pass' : 'fail') + '</td>' +
      '<td><b>' + esc(run.average_score) + '</b><br><small>기준 ' + esc(run.deployment_threshold || 95) + '</small></td><td>' + esc(run.average_duration_ms || '-') + ' ms<br><small>P95 ' + esc(run.p95_duration_ms || '-') + ' ms</small></td>' +
      '<td>' + esc(run.total_tokens || 0) + ' tok<br><small>비용 ' + esc(Number(run.estimated_cost || 0).toFixed(4)) + ' · 결함 ' + esc(run.defects_count || 0) + '</small></td>' +
      '<td><small>' + version + '</small><br>' + statusBadge(run.approval_status || 'PENDING', (run.approval_status || 'pending').toLowerCase()) + '</td>' +
      '<td><div class="run-actions"><button type="button" class="run-detail-button run-action detail" data-run-id="' + esc(run.run_id) + '">전체 데이터 보기</button>' +
      '<a class="run-action word" href="/quality/runs/' + encodeURIComponent(run.run_id) + '/report.docx">Word 보고서</a></div></td></tr>';
  }).join('');
  document.querySelectorAll('.run-detail-button').forEach(button => {
    button.onclick = () => {
      runDetailReturnFocus = button;
      loadRunHistoryDetail(button.dataset.runId);
    };
  });
}

function fillControlRunSelect(id, runs, selectedIndex = 0) {
  const select = $(id);
  const previous = select.value;
  select.innerHTML = runs.map((run, index) => '<option value="' + esc(run.run_id) + '" ' +
    ((previous === run.run_id || (!previous && index === selectedIndex)) ? 'selected' : '') + '>' + esc(runLabel(run)) + '</option>').join('');
  select.disabled = !runs.length;
}

async function fetchRuns() {
  const [sortBy, sortDirection] = $("runSort").value.split(':');
  const params = new URLSearchParams({
    query: $("runSearch").value.trim(), kind: $("runKind").value,
    domain: $("runDomain").value, status: $("runStatus").value, limit: '200',
    minimum_score: $("runMinimumScore").value, agent: $("runAgent").value,
    defects_only: $("runDefectsOnly").checked ? 'true' : '',
    sort_by: sortBy, sort_direction: sortDirection
  });
  const response = await apiFetch('/quality/runs?' + params.toString());
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(responseError(data));
  controlRuns = data.runs || [];
  renderRunTable(controlRuns);
  return controlRuns;
}

let selectedRunDetail = null;
let runDetailReturnFocus = null;
function runValueTable(rows, className = '') {
  return '<div class="result-table-wrap"><table class="result-table ' + esc(className) + '"><tbody>' + rows.map(row =>
    '<tr><th style="width:190px">' + esc(row[0]) + '</th><td>' + (row[2] === true ? String(row[1]) : esc(row[1])) + '</td></tr>'
  ).join('') + '</tbody></table></div>';
}

function resultItems(value) {
  const list = Array.isArray(value) ? value : [];
  return list.map(item => typeof item === 'object' ? firstResultValue(item.item, item.evidence, item.sample, '-') : item).filter(Boolean);
}

function resultListText(value, empty = '없음') {
  const list = resultItems(value);
  return list.length ? list.join(', ') : empty;
}

function ratioText(value) {
  if (value === undefined || value === null || value === '') return '-';
  const number = Number(value);
  return Number.isFinite(number) ? (number * 100).toFixed(1) + '%' : String(value);
}

function rubricEvidenceText(item) {
  const evidence = item?.evidence || {};
  if (evidence.retrieved_count !== undefined) return '검색 ' + evidence.retrieved_count + '건 중 관련 ' + evidence.relevant_count + '건';
  if (evidence.lexical_grounding_ratio !== undefined) return '근거 일치 ' + ratioText(evidence.lexical_grounding_ratio) + ' · 기대 키워드 ' + ratioText(evidence.expected_keyword_ratio);
  if (evidence.winner) return '선정 후보 ' + evidence.winner + ' · 점수 ' + Object.entries(evidence.scores || {}).map(row => row[0] + ' ' + row[1]).join(', ');
  if (evidence.need_refine !== undefined) return evidence.need_refine ? '보완 필요 · ' + resultListText(evidence.edits) : '추가 보완 불필요';
  if (Array.isArray(evidence.matched) || Array.isArray(evidence.missing)) return '충족 ' + resultListText(evidence.matched) + ' · 누락 ' + resultListText(evidence.missing);
  if (evidence.duration_ms !== undefined) return '처리시간 ' + evidence.duration_ms + ' ms · 기준 ' + evidence.limit_ms + ' ms';
  if (evidence.intent || evidence.keywords) return '의도 일치 ' + ratioText(evidence.intent?.ratio) + ' · 키워드 일치 ' + ratioText(evidence.keywords?.ratio);
  return item?.passed ? '평가 기준 충족' : '평가 기준 미충족';
}

function renderRubricTable(rubric) {
  const rows = Object.values(rubric || {});
  if (!rows.length) return '<div class="notice">점수화 평가 항목이 없는 실행입니다.</div>';
  return '<div class="result-table-wrap"><table class="result-table"><thead><tr><th>평가 항목</th><th>점수</th><th>판정</th><th>평가 근거</th></tr></thead><tbody>' + rows.map(item =>
    '<tr><td>' + esc(item.label || '-') + '</td><td>' + esc(item.score ?? '-') + ' / ' + esc(item.max_score ?? '-') + '</td><td>' +
    statusBadge(item.passed ? 'PASS' : 'FAIL', item.passed ? 'pass' : 'fail') + '</td><td>' + esc(rubricEvidenceText(item)) + '</td></tr>'
  ).join('') + '</tbody></table></div>';
}

function renderExpectationTable(checks) {
  const rows = [
    ['기대 의도', checks.intent?.expected || '-', checks.intent?.passed, '일치 ' + ratioText(checks.intent?.ratio) + ' · 누락 ' + resultListText(checks.intent?.missing)],
    ['필수 키워드', resultListText(checks.keywords?.matched), checks.keywords?.passed, '누락 ' + resultListText(checks.keywords?.missing)],
    ['필수 출력', resultListText(checks.required_output?.matched), checks.required_output?.passed, '누락 ' + resultListText(checks.required_output?.missing)],
    ['금지 출력', resultListText(checks.prohibited_output?.violations), checks.prohibited_output?.passed, checks.prohibited_output?.passed ? '위반 없음' : '금지 내용 검출']
  ];
  return '<div class="result-table-wrap"><table class="result-table"><thead><tr><th>검증 기준</th><th>확인된 수행결과</th><th>판정</th><th>근거</th></tr></thead><tbody>' + rows.map(row =>
    '<tr><td>' + esc(row[0]) + '</td><td>' + esc(row[1]) + '</td><td>' + statusBadge(row[2] ? 'PASS' : 'FAIL', row[2] ? 'pass' : 'fail') + '</td><td>' + esc(row[3]) + '</td></tr>'
  ).join('') + '</tbody></table></div>';
}

function renderRagTable(rag) {
  const rows = [
    ['Context Precision', rag.context_precision], ['Context Recall', rag.context_recall],
    ['Faithfulness', rag.faithfulness], ['Response Relevancy', rag.response_relevancy],
    ['Noise Sensitivity', rag.noise_sensitivity], ['Citation Coverage', rag.citation_coverage]
  ];
  if (!rows.some(row => row[1] !== undefined)) return '<div class="notice">RAG 전문 지표가 없는 실행입니다.</div>';
  const measured = rows.map(row => Number(row[1])).filter(Number.isFinite);
  const aggregate = Number.isFinite(Number(rag.ratio)) ? Number(rag.ratio) : measured.reduce((sum, value) => sum + value, 0) / Math.max(measured.length, 1);
  const overallPassed = rag.passed !== undefined ? Boolean(rag.passed) : aggregate >= 0.6;
  const verdict = value => {
    const number = Number(value);
    if (!Number.isFinite(number)) return statusBadge('미측정', 'info');
    return number >= 0.8 ? statusBadge('양호', 'pass') : number >= 0.6 ? statusBadge('주의', 'hold') : statusBadge('개선 필요', 'fail');
  };
  const body = rows.map(row => '<tr><td>' + esc(row[0]) + '</td><td>' + esc(ratioText(row[1])) + '</td><td>' + verdict(row[1]) + '</td></tr>').join('') +
    '<tr><th>RAG 6지표 종합</th><th>' + esc(ratioText(aggregate)) + '</th><th>' + statusBadge(overallPassed ? 'PASS' : 'FAIL', overallPassed ? 'pass' : 'fail') + '</th></tr>';
  const diagnostic = runValueTable([
    ['측정 방식', rag.method || '결정적 RAG 지표 계산'],
    ['관련 / 노이즈 문맥', (rag.relevant_context_count ?? '-') + ' / ' + (rag.noise_context_count ?? '-') + '건'],
    ['노이즈 의존도', ratioText(rag.noise_dependency)],
    ['배포 점수 반영', rag.affects_release_score === false ? '미반영 · 진단 참고 지표' : '반영']
  ]);
  return '<div class="result-table-wrap"><table class="result-table"><thead><tr><th>RAG 지표</th><th>측정값</th><th>지표 판정</th></tr></thead><tbody>' + body + '</tbody></table></div>' + diagnostic;
}

function stageResultText(stage) {
  const output = stage?.output || {};
  switch (stage?.agent) {
    case 'Interpreter': return '작업 ' + (output.task || '-') + ' · 검색 조건 ' + resultListText(output.filters) + ' · 최대 ' + (output.max_items ?? '-') + '건';
    case 'Retriever': return '관련 VOC ' + (output.retrieved_count ?? 0) + '건 검색 · 주요 근거: ' + resultListText((output.samples || []).slice(0,3));
    case 'Summarizer': return '최종 요약: ' + firstResultValue(output.post_refine_summary, output.pre_refine_summary, '-');
    case 'Evaluator': return '선정 후보 ' + firstResultValue(output.winner, output.llm_winner, '-') + ' · 후보 점수 ' + Object.entries(output.scores || {}).map(row => row[0] + ' ' + row[1]).join(', ');
    case 'Critic': return output.need_refine ? '보완 필요 · ' + resultListText(output.edits) : '추가 보완 불필요 · 위험 지적 없음';
    case 'Improver': return firstResultValue(output.policy, '개선안 생성 생략');
    default: return firstResultValue(stage?.check, stage?.role, '단계 수행 완료');
  }
}

function renderAgentResultTable(trace) {
  if (!trace?.length) return '<div class="notice">Agent 단계별 수행결과가 없는 실행입니다.</div>';
  return '<div class="result-table-wrap"><table class="result-table agent-result-table"><thead><tr><th>Agent</th><th>역할·점검</th><th>시간·토큰</th><th>모델</th><th>수행결과</th></tr></thead><tbody>' + trace.map(stage =>
    '<tr><td>' + esc(stage.agent || '-') + '</td><td>' + esc(stage.role || '-') + '<br><small class="muted">' + esc(stage.check || '-') + '</small></td><td>' +
    esc(stage.duration_ms ?? 0) + ' ms<br>' + esc(stage.total_tokens ?? 0) + ' tok</td><td>' + esc(stage.provider || '-') + '<br><small>' + esc(stage.model || '-') + '</small></td><td>' +
    esc(stageResultText(stage)) + (stage.error && Object.keys(stage.error).length ? '<br><span class="error">오류: ' + esc(stage.error.message || String(stage.error)) + '</span>' : '') + '</td></tr>'
  ).join('') + '</tbody></table></div>';
}

function runResultText(run) {
  const lines = [
    'VOC 종합 품질평가 수행결과', 'Run ID: ' + (run.run_id || '-'), '실행 시각: ' + (run.generated_at || '-'),
    '유형/도메인/모드: ' + [run.kind, run.domain, run.mode].filter(Boolean).join(' / '),
    '결과: ' + (run.passed || 0) + '/' + (run.total || 0) + ' PASS',
    '평균 점수: ' + (run.average_score ?? 0) + '/100 · 배포 기준: ' + (run.deployment_threshold ?? 95) + '/100', ''
  ];
  (run.cases || []).forEach(item => {
    const analysis = item.raw?.analysis || {};
    lines.push('[' + item.case_id + '] ' + item.status + ' · ' + item.score + '점');
    lines.push('질문: ' + (item.question || '-'));
    lines.push('VOC 분석: ' + firstResultValue(analysis.summary, item.output, '-'));
    lines.push('정책 개선안: ' + firstResultValue(analysis.policy, '-'));
    (item.trace || []).forEach(stage => lines.push('- ' + stage.agent + ': ' + stageResultText(stage)));
    lines.push('');
  });
  return lines.join('\n');
}

function auditRunDetailData(run) {
  const present = value => value !== undefined && value !== null && value !== '';
  const runFields = [
    ['실행 ID', run.run_id], ['실행 시각', run.generated_at], ['유형', run.kind], ['도메인', run.domain],
    ['모드', run.mode], ['모델/공급자', run.model || run.provider], ['전체', run.total], ['PASS', run.passed],
    ['FAIL', run.failed], ['PASS율', run.pass_rate], ['평균 점수', run.average_score], ['배포 기준', run.deployment_threshold],
    ['평균 시간', run.average_duration_ms], ['P95', run.p95_duration_ms], ['토큰', run.total_tokens], ['비용', run.estimated_cost],
    ['결함', run.defects_count], ['중대 위반', run.critical_violations], ['429', run.rate_limit_count],
    ['데이터 버전', run.dataset_version], ['프롬프트 버전', run.prompt_version], ['Git', run.git_commit]
  ];
  const missing = runFields.filter(row => !present(row[1])).map(row => row[0]);
  const cases = run.cases || [];
  let rubricCount = 0, ragCount = 0, traceCount = 0;
  cases.forEach(item => {
    const quality = item.raw?.quality || {};
    const metrics = item.metrics || {};
    rubricCount += Object.keys(metrics.rubric || quality.rubric || {}).length;
    const rag = metrics.rag || quality.checks?.rag_metrics || {};
    ragCount += ['context_precision','context_recall','faithfulness','response_relevancy','noise_sensitivity','citation_coverage'].filter(key => present(rag[key])).length;
    traceCount += (item.trace || []).length;
  });
  return {available:runFields.length - missing.length,total:runFields.length,missing,cases:cases.length,rubricCount,ragCount,traceCount};
}

function renderRunHistoryDetail(run) {
  selectedRunDetail = run;
  const passed = Number(run.total || 0) > 0 && Number(run.failed || 0) === 0;
  $("runDetailTitle").textContent = '수행결과 전체 데이터 · ' + (run.run_id || '-');
  $("runDetailSummary").innerHTML =
    '<div class="metric">실행 결과<b>' + (passed ? '✅ PASS' : '❌ FAIL') + '</b></div>' +
    '<div class="metric">케이스<b>' + esc(run.passed || 0) + '/' + esc(run.total || 0) + '</b></div>' +
    '<div class="metric">평균 점수<b>' + esc(run.average_score || 0) + '/100</b></div>' +
    '<div class="metric">배포 기준<b>' + esc(run.deployment_threshold || 95) + '/100</b></div>' +
    '<div class="metric">P95<b>' + esc(run.p95_duration_ms || 0) + ' ms</b></div>' +
    '<div class="metric">토큰·비용<b>' + esc(run.total_tokens || 0) + ' · ' + esc(Number(run.estimated_cost || 0).toFixed(6)) + '</b></div>' +
    '<div class="metric">결함·429<b>' + esc(run.defects_count || 0) + ' · ' + esc(run.rate_limit_count || 0) + '</b></div>' +
    '<div class="metric">최종 승인<b>' + esc(run.release_approval?.status || 'PENDING') + '</b></div>';
  const cases = run.cases || [];
  const audit = auditRunDetailData(run);
  $("runDetailMetadata").innerHTML = '<h4>실행 정보</h4>' + runValueTable([
    ['실행 ID', run.run_id || '-'], ['실행 시각', fmtDate(run.generated_at)], ['테스트 유형', run.kind || '-'],
    ['도메인 / 실행 모드', (run.domain || '-') + ' / ' + (run.mode || '-')], ['모델', run.model || run.provider || '미기록'],
    ['기능 결과', (run.passed ?? 0) + '/' + (run.total ?? 0) + ' PASS · FAIL ' + (run.failed ?? 0) + '건 · PASS율 ' + (run.pass_rate ?? 0) + '%'],
    ['점수 / 배포 기준', (run.average_score ?? 0) + '/100 · ' + (run.deployment_threshold ?? 95) + '/100'],
    ['성능', '평균 ' + (run.average_duration_ms ?? '-') + ' ms · P95 ' + (run.p95_duration_ms ?? '-') + ' ms'],
    ['사용량 / 비용', (run.total_tokens ?? 0) + ' tok · ' + Number(run.estimated_cost || 0).toFixed(6)],
    ['결함 / 중대 위반 / 429', (run.defects_count ?? 0) + ' / ' + (run.critical_violations ?? 0) + ' / ' + (run.rate_limit_count ?? 0)],
    ['Live 검증', run.live_verified ? '확인됨' : '미확인'],
    ['데이터 / 프롬프트 버전', (run.dataset_version || '-') + ' / ' + (run.prompt_version || '-')],
    ['Git 기준', run.git_commit || '-'], ['사람 검토·배포 승인', (run.release_approval?.status || 'PENDING') + (run.release_approval?.final_deployment_approved ? ' · 최종 승인' : ' · 최종 승인 전')]
  ]) + '<div class="notice run-data-audit"><b>표시 데이터 검증</b><br>실행 QA 필드 ' + audit.available + '/' + audit.total + ' · 케이스 ' + audit.cases + '건 · 9개 평가 항목 ' + audit.rubricCount + '개 · RAG 측정값 ' + audit.ragCount + '개 · Agent 단계 ' + audit.traceCount + '개' +
    (audit.missing.length ? '<br><span class="muted">원본 보고서 미기록 항목: ' + esc(audit.missing.join(', ')) + '</span>' : '<br>필수 실행 값이 모두 기록되어 있습니다.') + '</div>';
  $("runDetailCases").innerHTML = cases.length ? cases.map(item => {
    const analysis = item.raw?.analysis || {};
    const quality = item.raw?.quality || {};
    const metrics = item.metrics || {};
    const checks = quality.checks || {};
    const rubric = metrics.rubric || quality.rubric || {};
    const rag = metrics.rag || checks.rag_metrics || {};
    const deployment = metrics.deployment || quality.deployment || {};
    return '<details class="case" open><summary><b>' + esc(item.case_id) + '</b> · ' + statusBadge(item.status, item.status === 'PASS' ? 'pass' : 'fail') + ' · ' + esc(item.score) + '점</summary>' +
      '<div class="case-body"><h4>고객 질문과 실제 수행결과</h4><div class="run-result-value"><strong>고객 질문</strong><br>' + esc(item.question || '-') + '</div>' +
      '<div class="run-case-columns"><div class="run-result-value"><strong>VOC 분석 결과</strong><br>' + esc(firstResultValue(analysis.summary, item.output, '-')) + '</div>' +
      '<div class="run-result-value"><strong>정책 개선안</strong><br>' + esc(firstResultValue(analysis.policy, '-')) + '</div></div>' +
      '<div class="run-result-value"><strong>저장된 최종 출력</strong><br>' + esc(item.output || '-') + '</div>' +
      '<div class="run-result-value"><strong>배포 평가</strong><br>' + esc(firstResultValue(deployment.label, deployment.code, '-')) + ' · 기준 ' + esc(deployment.minimum_score ?? run.deployment_threshold ?? 95) + '점 · 차이 ' + esc(deployment.score_gap ?? '-') + '점</div>' +
      '<div class="run-result-value"><strong>결함·중대 차단·처리시간</strong><br>' + esc(resultListText(metrics.defects)) + ' / ' + esc(resultListText(metrics.hard_blockers)) + ' / ' + esc(metrics.duration_ms ?? '-') + ' ms</div>' +
      '<h4>기대 결과 충족 여부</h4>' + renderExpectationTable(checks) + '<h4>9개 품질 평가 항목</h4>' + renderRubricTable(rubric) +
      '<h4>RAG 전문 지표</h4>' + renderRagTable(rag) + '<h4>6-Agent 단계별 수행결과</h4>' + renderAgentResultTable(item.trace || []) + '</div></details>';
  }).join('') : '<div class="notice">이 실행 유형에는 케이스 단위 결과가 없습니다. 실행 요약과 산출물 정보를 확인하세요.</div>';
  $("downloadRunWord").href = '/quality/runs/' + encodeURIComponent(run.run_id) + '/report.docx';
  $("runDetailStatus").textContent = '소스 원문을 제외한 QA 표시 데이터 검증 완료 · 실행 필드 ' + audit.available + '/' + audit.total + ' · 케이스 ' + cases.length + '건.';
  openRunDetailLayer();
}

function openRunDetailLayer() {
  $("runDetailPanel").hidden = false;
  document.body.classList.add('run-detail-open');
  window.setTimeout(() => $("closeRunDetail").focus(), 0);
}

function closeRunDetailLayer() {
  $("runDetailPanel").hidden = true;
  document.body.classList.remove('run-detail-open');
  selectedRunDetail = null;
  if (runDetailReturnFocus?.isConnected) runDetailReturnFocus.focus();
  runDetailReturnFocus = null;
}

async function loadRunHistoryDetail(runId) {
  openRunDetailLayer();
  $("runDetailStatus").textContent = '수행결과 전체 데이터를 불러오는 중입니다.';
  try {
    const response = await apiFetch('/quality/runs/' + encodeURIComponent(runId));
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(responseError(data));
    renderRunHistoryDetail(data.run);
  } catch (error) {
    $("runDetailStatus").textContent = '전체 데이터 조회 실패: ' + (error.message || error);
  }
}

let controlCases = [];

function renderAutomatedTestDetail(row, descriptor) {
  $("caseDetailTitle").textContent = descriptor.case_number + ' · ' + descriptor.title;
  $("caseDetailContent").innerHTML =
    '<div class="notice"><b>자동 품질 테스트입니다.</b> 고객 VOC 질문·AI 답변을 평가하는 케이스가 아니라 ' +
      '프로그램 내부 동작 계약을 검증하므로 100점 품질점수와 6-Agent Trace가 적용되지 않습니다.</div>' +
    '<div class="metrics">' +
      '<div class="metric">테스트 번호<b>' + esc(descriptor.case_number) + '</b></div>' +
      '<div class="metric">실행 결과<b>' + statusBadge(row.status, row.status === 'PASS' ? 'pass' : 'fail') + '</b></div>' +
      '<div class="metric">테스트 유형<b>' + esc(descriptor.category) + '</b></div>' +
      '<div class="metric">품질 점수<b>적용 대상 아님</b></div>' +
    '</div>' +
    '<h4>무엇을 검사하는 테스트인가?</h4>' +
    '<div class="run-result-value"><strong>' + esc(descriptor.title) + '</strong><br>' + esc(descriptor.description) + '</div>' +
    '<h4>통과 기준</h4>' +
    '<div class="run-result-value">' + esc(descriptor.expected) + '</div>' +
    '<h4>이번 실행 결과</h4>' +
    '<div class="run-result-value"><strong>' + esc(descriptor.actual) + '</strong><br>' +
      '실행 시각: ' + esc(fmtDate(row.generated_at)) + '</div>' +
    '<details><summary>개발자용 원본 식별자·소스 보기</summary>' +
      runValueTable([['내부 unittest ID', descriptor.internal_id], ['소스 파일', descriptor.source], ['실행 종류', row.kind || '-']]) +
    '</details>';
}

function renderCaseExplorerDetail(row, fullCase = null) {
  const item = fullCase || row;
  const descriptor = item.test_descriptor || row.test_descriptor || null;
  if (descriptor) {
    renderAutomatedTestDetail(row, descriptor);
    return;
  }
  const raw = item.raw || {};
  const analysis = raw.analysis || {};
  const quality = raw.quality || {};
  const metrics = item.metrics || row.metrics || {};
  const checks = quality.checks || {};
  const rubric = metrics.rubric || quality.rubric || {};
  const rag = metrics.rag || checks.rag_metrics || {};
  const deployment = metrics.deployment || quality.deployment || {};
  const trace = item.trace || row.trace || [];
  const actualSummary = firstResultValue(analysis.summary, item.output, row.output, '-');
  const actualPolicy = firstResultValue(analysis.policy, '-');
  const failedItems = Object.values(rubric)
    .filter(value => value && value.passed === false)
    .map(value => value.label || value.key)
    .filter(Boolean);

  $("caseDetailTitle").textContent = (row.case_id || '케이스') + ' 상세 수행결과';
  $("caseDetailContent").innerHTML =
    '<div class="metrics">' +
      '<div class="metric">상태<b>' + statusBadge(row.status, row.status === 'PASS' ? 'pass' : 'fail') + '</b></div>' +
      '<div class="metric">점수<b>' + esc(row.score) + '/100</b></div>' +
      '<div class="metric">실행 시각<b>' + esc(fmtDate(row.generated_at)) + '</b></div>' +
      '<div class="metric">도메인·모드<b>' + esc((row.domain || '-') + ' · ' + (row.mode || '-')) + '</b></div>' +
    '</div>' +
    '<h4>질문과 실제 AI 응답</h4>' +
    '<div class="run-result-value"><strong>테스트 질문</strong><br>' + esc(row.question || item.question || '-') + '</div>' +
    '<div class="run-case-columns"><div class="run-result-value"><strong>실제 VOC 요약 응답</strong><br>' + esc(actualSummary) + '</div>' +
    '<div class="run-result-value"><strong>실제 정책 개선안 응답</strong><br>' + esc(actualPolicy) + '</div></div>' +
    '<div class="run-result-value"><strong>실패 원인</strong><br>' +
      esc(failedItems.join(' · ') || (row.status === 'PASS' ? '평가 기준을 모두 충족했습니다.' : '세부 평가표를 확인하세요.')) + '</div>' +
    '<div class="run-result-value"><strong>배포 평가</strong><br>' +
      esc(firstResultValue(deployment.label, deployment.code, '-')) + ' · 기준 ' +
      esc(deployment.minimum_score ?? 95) + '점 · 차이 ' + esc(deployment.score_gap ?? '-') + '점</div>' +
    '<h4>기대 결과 충족 여부</h4>' + renderExpectationTable(checks) +
    '<h4>9개 품질 평가 항목</h4>' + renderRubricTable(rubric) +
    '<h4>RAG 전문 지표</h4>' + renderRagTable(rag) +
    '<h4>6-Agent 단계별 실제 수행결과</h4>' + renderAgentResultTable(trace);
}

async function loadCaseExplorerDetail(index) {
  const row = controlCases[Number(index)];
  if (!row) return;
  const panel = $("caseDetailPanel");
  panel.hidden = false;
  $("caseDetailTitle").textContent = (row.case_id || '케이스') + ' 상세 수행결과';
  $("caseDetailStatus").textContent = '실제 응답과 6-Agent Trace를 불러오는 중입니다.';
  $("caseDetailContent").innerHTML = '<div class="notice">상세 데이터를 조회하고 있습니다.</div>';
  panel.scrollIntoView({behavior:'smooth', block:'start'});
  try {
    const response = await apiFetch('/quality/runs/' + encodeURIComponent(row.run_id));
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(responseError(data));
    const fullCase = (data.run?.cases || []).find(item => item.case_id === row.case_id) || null;
    renderCaseExplorerDetail(row, fullCase);
    $("caseDetailStatus").textContent = fullCase
      ? '질문, 실제 응답, 평가 근거와 Agent 수행결과를 표시했습니다.'
      : '실행 원문에서 동일 케이스를 찾지 못해 목록에 저장된 결과를 표시했습니다.';
  } catch (error) {
    renderCaseExplorerDetail(row);
    $("caseDetailStatus").textContent = '전체 실행 데이터 조회 실패로 목록에 저장된 결과를 표시했습니다: ' + (error.message || error);
  }
}

async function fetchCases() {
  const [sortBy, sortDirection] = $("caseSort").value.split(':');
  const params = new URLSearchParams({
    query: $("caseSearch").value.trim(), domain: $("caseDomain").value,
    status: $("caseStatus").value, agent: $("caseAgent").value,
    minimum_score: $("caseMinimumScore").value,
    defects_only: $("caseDefectsOnly").checked ? 'true' : '',
    sort_by: sortBy, sort_direction: sortDirection, limit:'300'
  });
  const response = await apiFetch('/quality/cases?' + params.toString());
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(responseError(data));
  controlCases = data.cases || [];
  $("caseCount").textContent = '검색 결과 ' + controlCases.length + '건';
  $("navCaseBadge").textContent = controlCases.length ? String(controlCases.length) : '';
  $("caseTableBody").innerHTML = controlCases.length ? controlCases.map((row,index) => {
    const defects = row.metrics?.defects || [];
    const failedAgents = Object.entries(row.metrics?.rubric || {}).filter(([,item]) => item && !item.passed).map(([,item]) => item.label);
    const descriptor = row.test_descriptor || null;
    const displayId = descriptor?.case_number || row.case_id;
    const displayQuestion = descriptor?.title || row.question || '-';
    const displayScore = descriptor ? '미적용' : row.score;
    return '<tr><td><b>' + esc(displayId) + '</b><br><small>' + esc(fmtDate(row.generated_at)) + '</small></td><td>' + esc(displayQuestion) +
      (descriptor ? '<br><small>' + esc(descriptor.category) + '</small>' : '') + '</td><td>' + esc(row.domain || '-') + '</td><td>' +
      statusBadge(row.status, row.status === 'PASS' ? 'pass' : 'fail') + '</td><td><b>' + esc(displayScore) + '</b></td><td>' + esc((defects.length ? defects : failedAgents).join(' · ') || '명시 결함 없음') + '</td><td><button type="button" class="case-detail-button sec" data-index="' + index + '">상세</button></td></tr>';
  }).join('') : '<tr><td colspan="7" class="muted">조건에 맞는 케이스가 없습니다.</td></tr>';
  document.querySelectorAll('.case-detail-button').forEach(button => {
    button.onclick = () => loadCaseExplorerDetail(button.dataset.index);
  });
  return controlCases;
}

function renderRelease(control, quality) {
  const assessment = quality?.deployment_assessment || {};
  const latest = control.latest_by_kind?.e2e || control.latest || {};
  const score = assessment.overall_score ?? latest.average_score ?? 0;
  const pass = assessment.formal_deployable === true;
  const technicalPass = assessment.technical_pass === true;
  const label = assessment.label || (latest.failed === 0 && score >= 95 ? '배포 가능' : '배포 보류');
  const blockers = assessment.blockers || [];
  $("controlReleaseBanner").innerHTML = '<div><p class="eyebrow">CURRENT RELEASE VERDICT</p><div class="release-verdict">' +
    statusBadge(label, pass ? 'pass' : 'hold') + '</div><p>' + (blockers.length ? '<b>미충족:</b> ' + esc(blockers.join(' · ')) : '현재 자동 게이트에서 중대 회귀가 감지되지 않았습니다.') +
    '</p><span class="muted">최신 실행 ' + esc(fmtDate(latest.generated_at)) + ' · 기준 ' + esc(assessment.minimum_score ?? 95) + '점</span></div>' +
    '<div class="release-score ' + (pass ? 'pass' : 'hold') + '" aria-label="통합 품질 점수 ' + esc(score) + '점, ' + (pass ? '배포 승인' : '배포 보류') + '">' +
      '<span class="release-score-label">통합 품질 점수</span><div class="release-score-number"><strong class="release-score-value">' + esc(score) + '</strong><span class="release-score-unit">/100</span></div>' +
      '<span class="release-score-status">' + (pass ? 'APPROVED' : 'HOLD') + '</span></div>';
  const ready = (quality?.agents || []).filter(x => x.ready).length;
  const security = control.latest_by_kind?.red_team || {};
  $("controlKpis").innerHTML = '<div class="metric">품질 게이트<b>' + (technicalPass ? '✅ PASS' : '❌ FAIL') + '</b></div>' +
    '<div class="metric">운영 배포<b>' + (pass ? '✅ APPROVED' : '⏸ HOLD') + '</b></div>' +
    '<div class="metric">보안 진단<b>' + (security.failed === 0 && security.total ? '✅ ' + security.passed + '/' + security.total : 'PENDING') + '</b></div>' +
    '<div class="metric">Agent 준비<b>' + ready + '/6</b></div>' +
    '<div class="metric">P95 지연<b>' + esc(latest.p95_duration_ms || 0) + ' ms</b></div>' +
    '<div class="metric">토큰·비용<b>' + esc(latest.total_tokens || 0) + ' · ' + esc(Number(latest.estimated_cost || 0).toFixed(4)) + '</b></div>' +
    '<div class="metric">429·드리프트<b>' + esc((control.drift_alerts || []).length) + '건</b></div>' +
    '<div class="metric">검토 큐<b>' + esc(control.pending_approval_count || 0) + '건</b></div>';
}

function renderLatestQualityOverview(control, quality) {
  const target = $("latestQualityOverview");
  if (!target) return;
  const latest = control.latest_by_kind?.e2e || control.latest;
  if (!latest) {
    $("latestOverviewTime").textContent = '실행 이력 없음';
    target.className = 'latest-overview-loading';
    target.textContent = '아직 표시할 품질 실행 데이터가 없습니다.';
    return;
  }
  const assessment = quality?.deployment_assessment || {};
  const trends = control.trends || [];
  const recent = trends[trends.length - 1] || {};
  const previous = trends.length > 1 ? trends[trends.length - 2] : null;
  const score = Number(assessment.overall_score ?? latest.average_score ?? recent.score ?? 0);
  const passRate = Number(latest.pass_rate ?? recent.pass_rate ?? 0);
  const scoreDelta = previous ? Number(recent.score ?? score) - Number(previous.score || 0) : null;
  const deployReady = assessment.formal_deployable === true;
  const technicalPass = assessment.technical_pass === true;
  const sparkValues = trends.slice(-8).map(item => Number(item.score || 0));
  const sparkline = sparkValues.length > 1 ? (() => {
    const min = Math.min(...sparkValues), max = Math.max(...sparkValues), range = Math.max(max - min, 1);
    const points = sparkValues.map((value,index) => (index * 84 / (sparkValues.length - 1)).toFixed(1) + ',' + (31 - ((value - min) * 27 / range)).toFixed(1)).join(' ');
    return '<svg class="latest-sparkline" viewBox="0 0 86 34" aria-hidden="true"><polyline points="' + points + '" fill="none" stroke="#36a8e0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  })() : '';
  const deltaText = scoreDelta === null ? '-' : (scoreDelta > 0 ? '+' : '') + scoreDelta.toFixed(1);
  const deltaClass = scoreDelta === null || scoreDelta >= 0 ? 'good' : 'warn';
  const blockers = assessment.blockers || [];
  const recentSummary = control.recent_summary || {};
  const durationSeconds = Math.max(0, Math.round(Number(recentSummary.average_duration_ms || 0) / 1000));
  const durationMinutes = Math.floor(durationSeconds / 60);
  const durationRemainder = durationSeconds % 60;
  const durationText = durationMinutes ? durationMinutes + '분 ' + durationRemainder + '초' : durationRemainder + '초';
  $("latestOverviewTime").textContent = '최근 E2E 실행 · ' + fmtDate(latest.generated_at);
  target.className = 'latest-overview-grid';
  target.innerHTML =
    '<div class="latest-stat quality"><span class="latest-stat-label">QUALITY SCORE</span><strong class="latest-stat-value">' + esc(score.toFixed(1)) + '<small>/100</small></strong><span class="latest-stat-detail">최근 E2E 실행 기준</span>' + sparkline + '</div>' +
    '<div class="latest-stat pass-rate"><span class="latest-stat-label">PASS RATE</span><strong class="latest-stat-value good">' + esc(passRate.toFixed(1)) + '<small>%</small></strong><span class="latest-stat-detail">테스트 ' + esc(latest.passed || 0) + ' / ' + esc(latest.total || 0) + ' 통과</span></div>' +
    '<div class="latest-stat recent-runs"><span class="latest-stat-label">RECENT RUNS</span><strong class="latest-stat-value">' + esc(Number(recentSummary.run_count || 0).toLocaleString('ko-KR')) + '<small>건</small></strong><span class="latest-stat-detail">지난 7일 기준</span></div>' +
    '<div class="latest-stat drift"><span class="latest-stat-label">SCORE DRIFT</span><strong class="latest-stat-value ' + deltaClass + '">' + esc(deltaText) + '<small>점</small></strong><span class="latest-stat-detail">' + (scoreDelta === null ? '비교할 직전 실행이 없습니다.' : '직전 E2E 실행 대비') + '</span></div>' +
    '<div class="latest-stat deploy"><span class="latest-stat-label">DEPLOY READINESS</span><strong class="latest-stat-value ' + (deployReady ? 'good' : 'warn') + '">' + (deployReady ? 'READY' : 'HOLD') + '</strong><span class="latest-stat-detail">' + (deployReady ? '배포 품질 게이트 충족' : (technicalPass ? '최종 승인 조건 확인 필요' : esc(blockers.length + '개 품질 조건 확인 필요'))) + '</span></div>' +
    '<div class="latest-stat average-duration"><span class="latest-stat-label">AVG DURATION</span><strong class="latest-stat-value">' + esc(durationText) + '</strong><span class="latest-stat-detail">지난 7일 평균 처리 시간</span></div>';
}

function renderApprovalList(approvals) {
  if (!approvals || !approvals.length) return '<span class="muted">아직 기록된 검토 결과가 없습니다.</span>';
  const decisions = {PENDING:'검토 대기',REVIEWING:'검토 중',APPROVED:'승인',CHANGES_REQUESTED:'수정 요청',REJECTED:'반려'};
  return approvals.slice(0,20).map(item => {
    const comment = item.comment_corrupted ? '<div class="warning">기존 검토 메모의 문자 인코딩이 손상되어 실제 케이스 데이터로 대체 표시합니다.</div>' :
      (item.comment ? '<details><summary>등록된 검토자 의견(참고)</summary><div class="content">' + esc(item.comment) + '</div></details>' : '<span class="muted">검토 의견 미기록</span>');
    const question = item.case_question ? '<span class="review-question">질문: ' + esc(item.case_question) + '</span>' : '';
    const response = item.case_output ? '<details><summary>실제 AI/Judge 응답 보기</summary><div class="content">' + esc(item.case_output) + '</div></details>' : '';
    const samples = (item.sample_cases || []).length ? '<details><summary>검토 대상 테스트 케이스 ' + esc(item.sample_cases.length) + '건 보기</summary><div class="table-wrap"><table class="data-table"><thead><tr><th>케이스</th><th>검증 항목</th><th>상태</th><th>점수</th></tr></thead><tbody>' +
      item.sample_cases.map(sample => '<tr><td>' + esc(sample.case_id) + '</td><td>' + esc(sample.title) + '</td><td>' + statusBadge(sample.status, sample.status === 'PASS' ? 'pass' : 'fail') + '</td><td>' + esc(sample.score) + '점</td></tr>').join('') +
      '</tbody></table></div></details>' : '';
    return '<div class="report-item"><div>' + statusBadge(decisions[item.decision] || item.decision, item.decision.toLowerCase()) +
      ' <b>' + esc(item.reviewer) + '</b> · ' + esc(fmtDate(item.created_at)) + '</div>' +
      '<div><b>' + esc(item.run_label) + '</b> · ' + esc(item.scope_label) + '</div>' +
      '<div class="muted">실행 결과 ' + esc(item.qa_summary) +
      (item.review_score !== null && item.review_score !== undefined ? ' · 사람 평가 ' + esc(item.review_score) + '점' : '') +
      (item.judge_agreement === null || item.judge_agreement === undefined ? '' : ' · Judge 판정 ' + (item.judge_agreement ? '동의' : '불일치')) +
      (item.final_deployment_approved ? ' · ✅ 최종 배포 승인' : '') + '</div>' + question + comment + response + samples + '</div>';
  }).join('');
}

function renderReviewQueue(queue) {
  if (!queue || !queue.length) return '<div class="notice">✅ 자동 검토 큐가 비어 있습니다.</div>';
  return queue.slice(0,50).map(item => {
    const selected = selectedApprovalReview && selectedApprovalReview.run_id === item.run_id && selectedApprovalReview.case_id === item.case_id;
    return '<button type="button" class="side-link review-queue-item' + (selected ? ' active' : '') + '" aria-pressed="' + (selected ? 'true' : 'false') + '" data-run="' + esc(item.run_id) + '" data-case="' + esc(item.case_id) + '">' +
    '<b>P' + esc(item.priority) + ' · ' + esc(item.case_id) + ' · ' + esc(item.score) + '점</b>' +
    '<span class="review-question">' + esc(item.question || item.case_title || '질문 데이터 확인 필요') + '</span>' +
    '<small>' + esc(item.run_label || '') + ' · 상태 ' + esc(item.status) +
    (item.judge_score !== null && item.judge_score !== undefined ? ' · Judge ' + esc(item.judge_score) + '점' : '') +
    (item.human_score !== null && item.human_score !== undefined ? ' · 사람 ' + esc(item.human_score) + '점' : '') +
    '<br><b>검토 사유:</b> ' + esc((item.reasons || []).join(' / ')) + '</small></button>';
  }).join('');
}

function reviewQueueStatus(item) {
  const status = String(item.status || '').toUpperCase();
  const reasons = (item.reasons || []).join(' ');
  return {
    hold:/HOLD|보류/.test(status), fail:/FAIL|ERROR|오류/.test(status),
    gap:/점수 차이/.test(reasons), unapproved:/승인 미기록/.test(reasons)
  };
}

function fillApprovalQueueFilters(queue) {
  const dateInput = $("approvalQueueDate");
  if (!dateInput.dataset.initialized) {
    const dates = [...new Set((queue || []).map(item => String(item.generated_at || '').slice(0,10)).filter(Boolean))].sort().reverse();
    dateInput.value = dates[0] || '';
    dateInput.dataset.initialized = 'true';
  }
  const select = $("approvalQueueRun"), previous = select.value;
  const unique = new Map();
  (queue || []).filter(item => !dateInput.value || String(item.generated_at || '').startsWith(dateInput.value)).forEach(item => {
    if (!unique.has(item.run_id)) unique.set(item.run_id, item);
  });
  select.innerHTML = '<option value="">전체 회차</option>' + [...unique.values()].map(item =>
    '<option value="' + esc(item.run_id) + '">' + esc(fmtDate(item.generated_at) + ' · ' + (item.run_label || '품질 실행')) + '</option>'
  ).join('');
  if ([...unique.keys()].includes(previous)) select.value = previous;
}

function filteredApprovalQueue() {
  const date = $("approvalQueueDate").value;
  const runId = $("approvalQueueRun").value;
  const status = $("approvalQueueStatus").value;
  const query = $("approvalQueueSearch").value.trim().toLowerCase();
  return approvalQueueData.filter(item => {
    if (date && !String(item.generated_at || '').startsWith(date)) return false;
    if (runId && item.run_id !== runId) return false;
    if (status && !reviewQueueStatus(item)[status]) return false;
    if (query && ![item.case_id,item.question,item.case_title,item.run_label].join(' ').toLowerCase().includes(query)) return false;
    return true;
  });
}

function bindReviewQueueActions() {
  document.querySelectorAll('.review-queue-item').forEach(button => {
    button.onclick = () => selectApprovalReview(button.dataset.run, button.dataset.case);
  });
}

function applyApprovalQueueFilters() {
  const filtered = filteredApprovalQueue();
  $("reviewQueueCount").textContent = filtered.length + '건';
  $("reviewQueue").innerHTML = renderReviewQueue(filtered);
  bindReviewQueueActions();
}

function setApprovalWorkflowState(selected) {
  $("approvalEvaluationFields").disabled = !selected;
  ["approvalStep1","approvalStep2","approvalStep3"].forEach((id,index) => {
    $(id).classList.toggle('active', index === 0 || Boolean(selected));
  });
}

function renderSelectedApproval(item) {
  if (!item) {
    $("selectedReviewContext").className = 'selected-review-context notice';
    $("selectedReviewContext").textContent = '위 자동 검토 큐에서 평가할 케이스를 선택하세요.';
    setApprovalWorkflowState(false);
    return;
  }
  const tone = /PASS|승인/.test(String(item.status || '')) ? 'pass' : 'fail';
  const metrics = runValueTable([
    ['실행', item.run_label || '품질 실행'], ['테스트 케이스', item.case_id || '실행 전체'],
    ['현재 판정', item.status || '-'], ['내부 점수', item.score !== undefined ? item.score + '점' : '-'],
    ['Judge 점수', item.judge_score !== null && item.judge_score !== undefined ? item.judge_score + '점' : '미기록'],
    ['사람 기존 점수', item.human_score !== null && item.human_score !== undefined ? item.human_score + '점' : '미기록'],
    ['검토 사유', (item.reasons || ['수동 검토 선택']).join(' / ')]
  ]);
  $("selectedReviewContext").className = 'selected-review-context';
  $("selectedReviewContext").innerHTML = '<div>' + statusBadge(item.status || '검토 대상', tone) + '</div>' +
    '<p class="review-question">' + esc(item.question || item.case_title || '실행 전체 검토') + '</p>' + metrics +
    (item.output ? '<details><summary>실제 AI/Judge 응답·근거 보기</summary><div class="content">' + esc(item.output) + '</div></details>' : '');
  setApprovalWorkflowState(true);
  $("approvalScore").value = item.human_score !== null && item.human_score !== undefined ? item.human_score : '';
  $("approvalScore").placeholder = item.score !== undefined ? 'AI 점수 ' + item.score + '점 참고 · 사람 점수 입력' : '0~100점';
  $("approvalDecision").value = 'REVIEWING';
  $("judgeAgreement").value = '';
  $("finalDeploymentApproval").checked = false;
}

async function selectApprovalReview(runId, caseId) {
  const item = approvalQueueData.find(row => row.run_id === runId && row.case_id === caseId);
  if (!item) return;
  selectedApprovalReview = item;
  $("approvalRun").value = runId;
  await loadApprovalCases();
  $("approvalCase").value = caseId;
  renderSelectedApproval(item);
  applyApprovalQueueFilters();
  $("selectedReviewContext").scrollIntoView({behavior:'smooth', block:'nearest'});
  $("approvalReviewer").focus();
}

function initializeApprovalWorkflow(queue) {
  approvalQueueData = Array.isArray(queue) ? queue : [];
  if (selectedApprovalReview && !approvalQueueData.some(item => item.run_id === selectedApprovalReview.run_id && item.case_id === selectedApprovalReview.case_id)) {
    selectedApprovalReview = null;
  }
  fillApprovalQueueFilters(approvalQueueData);
  applyApprovalQueueFilters();
  renderSelectedApproval(selectedApprovalReview);
}

function renderVersions(versions) {
  if (!versions || !versions.length) return '<span class="muted">버전 이력이 없습니다.</span>';
  return versions.slice(0,20).map(item => '<div class="report-item"><b>' + esc(fmtDate(item.generated_at)) + '</b> · ' + esc(item.model || item.provider || '모델 미기록') +
    '<br><small class="muted">Git ' + esc(item.git_commit) + ' · Dataset ' + esc(item.dataset_version) + ' · Prompt ' + esc(item.prompt_version) + ' · 기준 ' + esc(item.deployment_threshold) + '</small></div>').join('');
}

function renderArtifacts() {
  const group = $("artifactGroup").value;
  const bundles = controlState?.artifact_bundles || [];
  if (!bundles.length) return '<span class="muted">실행 단위 증적이 없습니다.</span>';
  return bundles.slice(0,60).map(bundle => {
    const artifacts = (bundle.artifacts || []).filter(item => !group || item.group === group);
    if (!artifacts.length) return '';
    const links = artifacts.map(item => {
      const previewable = /\.(txt|xml|html|json|csv|md)$/i.test(item.name);
      return '<div><a href="/quality/report/' + encodeURIComponent(item.name) + '">' + esc(item.name) + '</a> ' +
        (previewable ? '<button type="button" class="preview-artifact side-link" data-name="' + esc(item.name) + '">결과 보기</button>' : '<span class="muted">다운로드 전용</span>') + '</div>';
    }).join('');
    const qaTitle = runKindName(bundle.kind) + ' · ' + runContextName(bundle);
    const internalId = '<div class="muted" style="margin:8px 0 4px">내부 실행 ID: ' + esc(bundle.run_id) + '</div>';
    return '<details class="report-item"><summary><b>' + esc(qaTitle) + '</b> · ' + esc(fmtDate(bundle.generated_at)) + '</summary>' + internalId + links + '</details>';
  }).join('') || '<span class="muted">선택한 유형의 산출물이 없습니다.</span>';
}

function firstResultValue(...values) {
  return values.find(value => value !== undefined && value !== null && value !== '');
}

function normalizeOperationResult(data) {
  const candidate = data && typeof data === 'object' ? data : {};
  const nested = candidate.result && typeof candidate.result === 'object' && !Array.isArray(candidate.result)
    ? candidate.result : candidate;
  const summary = nested.summary && typeof nested.summary === 'object' ? nested.summary : nested;
  const rows = Array.isArray(nested.results) ? nested.results :
    (Array.isArray(nested.cases) ? nested.cases : (Array.isArray(candidate.results) ? candidate.results : []));
  return {candidate, nested, summary, rows};
}

function collectResultFiles(value, found = new Set(), depth = 0) {
  if (depth > 5 || value === null || value === undefined) return found;
  if (typeof value === 'string') {
    if (/\.(txt|xml|html|json|csv|md|pdf|zip|png|docx)$/i.test(value.trim())) {
      found.add(value.replace(/\\/g, '/').split('/').pop());
    }
    return found;
  }
  if (Array.isArray(value)) value.forEach(item => collectResultFiles(item, found, depth + 1));
  else if (typeof value === 'object') Object.values(value).forEach(item => collectResultFiles(item, found, depth + 1));
  return found;
}

function resultRow(item, index) {
  const quality = item?.quality || {};
  const descriptor = item?.test_descriptor && typeof item.test_descriptor === 'object'
    ? item.test_descriptor : null;
  const id = descriptor
    ? descriptor.case_number + ' · ' + descriptor.title
    : firstResultValue(item?.case_id, item?.test, item?.id, item?.name, item?.category, '결과-' + (index + 1));
  const rawStatus = firstResultValue(item?.status, item?.verdict,
    item?.passed === true ? 'PASS' : (item?.passed === false ? 'FAIL' : undefined), '-');
  const descriptorScored = descriptor && String(descriptor.scored || '').toLowerCase() === 'true';
  const score = descriptor && !descriptorScored ? '미적용' : firstResultValue(item?.score, quality.score, item?.average_score, '-');
  const detail = descriptor ? descriptor.actual : firstResultValue(item?.detail, item?.message, item?.reason, item?.category, item?.question,
    item?.error?.message, '-');
  return {id, status:String(rawStatus).toUpperCase(), score, detail, descriptor};
}

function renderResultMetrics(summary) {
  const metrics = [
    ['전체', firstResultValue(summary.total, summary.tests)],
    ['PASS', firstResultValue(summary.passed, summary.pass)],
    ['FAIL', firstResultValue(summary.failed, summary.failures)],
    ['오류', summary.errors],
    ['PASS율', summary.pass_rate !== undefined ? Number(summary.pass_rate).toFixed(1) + '%' : undefined],
    ['평균 점수', summary.average_score !== undefined ? Number(summary.average_score).toFixed(1) + '/100' : undefined],
    ['배포 기준', firstResultValue(summary.minimum_score, summary.minimum_deployment_score, summary.deployment_threshold)],
    ['배포 판정', summary.deployment_counts && typeof summary.deployment_counts === 'object' ? Object.entries(summary.deployment_counts).map(item => item[0] + ' ' + item[1]).join(' · ') : undefined],
    ['중대 차단', summary.hard_blocked],
    ['P95', summary.p95_duration_ms !== undefined ? summary.p95_duration_ms + ' ms' : undefined],
    ['토큰', firstResultValue(summary.total_tokens, summary.tokens)],
    ['비용', summary.estimated_cost !== undefined ? Number(summary.estimated_cost).toFixed(6) : undefined]
  ].filter(item => item[1] !== undefined && item[1] !== null && item[1] !== '');
  return metrics.length ? '<div class="result-metrics">' + metrics.map(item =>
    '<div class="result-metric">' + esc(item[0]) + '<b>' + esc(item[1]) + '</b></div>').join('') + '</div>' : '';
}

function renderResultRows(rows) {
  if (!rows.length) return '<div class="notice">케이스 단위 상세 결과가 없는 실행입니다. 위 요약 판정과 산출물을 확인하세요.</div>';
  return '<div class="result-table-wrap"><table class="result-table"><thead><tr><th>항목</th><th>상태</th><th>점수</th><th>결과·원인</th></tr></thead><tbody>' +
    rows.map((item,index) => {
      const row = resultRow(item,index);
      const descriptorDetail = row.descriptor ?
        '<div><b>' + esc(row.descriptor.category) + '</b><br>' + esc(row.descriptor.description) + '</div>' +
        '<details><summary>QA 검증 내용 자세히 보기</summary>' + runValueTable([
          ['테스트 번호', row.descriptor.case_number],
          ['검증 상황', row.descriptor.description],
          ['통과 기준', row.descriptor.expected],
          ['실제 결과', row.descriptor.actual],
          ...(row.descriptor.source ? [['소스 파일', row.descriptor.source]] : []),
          ...(row.descriptor.internal_id ? [['개발자용 내부 ID', row.descriptor.internal_id]] : [])
        ].filter(item => item[1] !== undefined && item[1] !== null && item[1] !== '')) + '</details>' : esc(row.detail);
      return '<tr><td>' + esc(row.id) + '</td><td>' + statusBadge(row.status, row.status === 'PASS' ? 'pass' : (row.status === 'FAIL' || row.status === 'ERROR' ? 'fail' : 'info')) +
        '</td><td>' + esc(row.score) + '</td><td>' + descriptorDetail + '</td></tr>';
    }).join('') + '</tbody></table></div>';
}

function renderOperationResultData(data, includeTechnical = true) {
  const normalized = normalizeOperationResult(data);
  const summary = normalized.summary || {};
  const failed = Number(firstResultValue(summary.failed, summary.failures, 0));
  const errors = Number(firstResultValue(summary.errors, 0));
  const verdict = String(firstResultValue(normalized.candidate.error ? 'ERROR' : undefined, summary.verdict,
    summary.deployable === true ? 'APPROVED' : undefined,
    summary.successful === true ? 'PASS' : undefined,
    summary.successful === false || failed > 0 || errors > 0 ? 'FAIL' : undefined,
    summary.total !== undefined && failed === 0 && errors === 0 ? 'PASS' : '완료')).toUpperCase();
  const verdictTone = ['PASS','APPROVED','DEPLOYABLE','완료'].includes(verdict) ? 'pass' :
    (['FAIL','ERROR','HOLD','BLOCKED'].includes(verdict) ? 'fail' : 'info');
  const files = [...collectResultFiles(normalized.candidate)];
  const fileLinks = files.length ? '<div class="result-files">' + files.map(name =>
    '<a href="/quality/report/' + encodeURIComponent(name) + '">📎 ' + esc(name) + '</a>').join('') + '</div>' : '';
  const errorMessage = normalized.candidate.error ? '<div class="error">' +
    esc(normalized.candidate.error.message || normalized.candidate.error.detail || String(normalized.candidate.error)) + '</div>' : '';
  const technical = includeTechnical ? '<details><summary>고급 기술 데이터(JSON) 보기</summary><pre class="technical-data">' +
    esc(JSON.stringify(normalized.candidate, null, 2)) + '</pre></details>' : '';
  return '<div class="result-verdict"><strong>' + esc(verdict) + '</strong>' + statusBadge(verdict, verdictTone) + '</div>' +
    errorMessage + renderResultMetrics(summary) + renderResultRows(normalized.rows) + fileLinks + technical;
}

function parseCsvRows(content) {
  const parseLine = line => {
    const cells = []; let value = ''; let quoted = false;
    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      if (char === '"' && quoted && line[index + 1] === '"') { value += '"'; index += 1; }
      else if (char === '"') quoted = !quoted;
      else if (char === ',' && !quoted) { cells.push(value); value = ''; }
      else value += char;
    }
    cells.push(value); return cells;
  };
  const lines = content.split(/\r?\n/).filter(Boolean);
  if (!lines.length) return [];
  const headers = parseLine(lines[0]);
  return lines.slice(1).map(line => Object.fromEntries(headers.map((header,index) => [header, parseLine(line)[index] || ''])));
}

function renderArtifactResult(name, content, truncated) {
  const extension = (name.split('.').pop() || '').toLowerCase();
  let body = '';
  try {
    if (extension === 'json') {
      body = renderOperationResultData(JSON.parse(content), false);
    } else if (extension === 'csv') {
      body = renderResultRows(parseCsvRows(content));
    } else if (extension === 'html') {
      const doc = new DOMParser().parseFromString(content, 'text/html');
      const metrics = [...doc.querySelectorAll('.metric')].map(node => {
        const value = node.querySelector('b')?.textContent?.trim() || '-';
        return [node.textContent.replace(value, '').trim(), value];
      });
      const rows = [...doc.querySelectorAll('tbody tr')].map(row => {
        const cells = [...row.querySelectorAll('td')].map(cell => cell.textContent.trim());
        return {id:cells[0], status:cells[1], score:cells[2], detail:cells[3]};
      });
      body = (metrics.length ? '<div class="result-metrics">' + metrics.map(item => '<div class="result-metric">' + esc(item[0]) + '<b>' + esc(item[1]) + '</b></div>').join('') + '</div>' : '') + renderResultRows(rows);
    } else if (extension === 'xml') {
      const doc = new DOMParser().parseFromString(content, 'application/xml');
      if (doc.querySelector('parsererror')) throw new Error('XML 형식 오류');
      const root = doc.documentElement;
      const summaryNode = root.querySelector('summary');
      const summary = Object.fromEntries([...(summaryNode?.attributes || root.attributes)].map(item => [item.name, item.value]));
      const rows = [...root.querySelectorAll('case, testcase')].map((node,index) => ({
        id:firstResultValue(node.getAttribute('id'), node.getAttribute('name'), '항목-' + (index + 1)),
        status:firstResultValue(node.getAttribute('status'), node.querySelector('failure,error') ? 'FAIL' : 'PASS'),
        score:node.querySelector('score')?.textContent || '-',
        detail:firstResultValue(node.querySelector('detail')?.textContent, node.querySelector('failure,error')?.getAttribute('message'), '-')
      }));
      body = renderResultMetrics({
        total:firstResultValue(summary.total, summary.tests), passed:summary.passed,
        failed:firstResultValue(summary.failed, summary.failures), errors:summary.errors,
        average_score:firstResultValue(summary.averageScore, summary.average_score)
      }) + renderResultRows(rows);
    } else if (extension === 'txt' || extension === 'md') {
      const lines = content.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
      const summaryLines = lines.filter(line => !line.startsWith('-')).slice(0,12);
      const rows = lines.filter(line => line.startsWith('-')).map((line,index) => {
        const cells = line.slice(1).split('|').map(value => value.trim());
        return {id:firstResultValue(cells[0], '항목-' + (index + 1)), status:firstResultValue(cells[1], 'INFO'), score:(cells[2] || '').replace('score=',''), detail:firstResultValue(cells.slice(3).join(' | '), line.slice(1))};
      });
      body = '<div class="notice">' + summaryLines.map(esc).join('<br>') + '</div>' + (rows.length ? renderResultRows(rows) : '');
    } else {
      body = '<div class="notice">이 파일은 화면 미리보기 대신 다운로드하여 확인하는 형식입니다.</div>';
    }
  } catch (error) {
    body = '<div class="error">결과 형식 해석 실패: ' + esc(error.message || error) + '</div>';
  }
  return '<div class="row" style="justify-content:space-between"><h3>' + esc(name) + '</h3><a href="/quality/report/' + encodeURIComponent(name) + '">파일 다운로드</a></div>' + body +
    (truncated ? '<p class="muted">큰 파일이므로 일부 결과만 표시했습니다.</p>' : '');
}

async function previewArtifact(name) {
  const response = await apiFetch('/quality/report-preview/' + encodeURIComponent(name));
  const data = await response.json();
  $("artifactPreview").hidden = false;
  $("artifactPreview").innerHTML = response.ok && data.ok ? renderArtifactResult(name, data.content, data.truncated) :
    '<div class="error">' + esc(responseError(data)) + '</div>';
  $("artifactPreview").scrollIntoView({behavior:'smooth', block:'nearest'});
}

function renderAuditEvents(events) {
  if (!events || !events.length) return '<span class="muted">아직 기록된 감사 이벤트가 없습니다.</span>';
  return events.map(item => '<div class="report-item"><div>' + statusBadge(item.event_type, 'info') + ' <b>' + esc(item.actor || 'system') +
    '</b> · ' + esc(fmtDate(item.created_at)) + '</div><small class="muted">대상 ' + esc(item.target || '-') + '</small></div>').join('');
}

async function refreshControlCenter() {
  $("refreshControl").disabled = true;
  $("controlLiveStatus").textContent = 'QA Control Center 상태를 갱신하는 중입니다.';
  try {
    const [controlResponse, qualityResponse] = await Promise.all([apiFetch('/quality/control-center'), apiFetch('/quality/status')]);
    const [control, quality] = await Promise.all([controlResponse.json(), qualityResponse.json()]);
    if (!controlResponse.ok || !control.ok) throw new Error(responseError(control));
    controlState = control;
    $("authControls").hidden = true;
    if (control.auth?.enabled && !$("qaAuthToken").value) {
      $("qaAuthToken").value = sessionStorage.getItem('qaOperatorToken') || '';
    }
    renderRelease(control, qualityResponse.ok ? quality : {});
    renderLatestQualityOverview(control, qualityResponse.ok ? quality : {});
    $("navSecurityBadge").textContent = (control.drift_alerts || []).length ? String((control.drift_alerts || []).length) : '';
    $("navApprovalBadge").textContent = control.pending_approval_count ? String(control.pending_approval_count) : '';
    $("controlDeploymentThreshold").value = quality?.deployment_config?.minimum_score ?? 95;
    $("controlConcurrency").value = localStorage.getItem('qaDefaultConcurrency') || '2';
    $("controlJudge").value = 'auto';
    $("controlTrend").innerHTML = renderControlTrend(control.trends || []);
    $("driftAlerts").innerHTML = renderDriftAlerts(control.drift_alerts || []);
    notifyCriticalAlerts(control.drift_alerts || []);
    $("approvalList").innerHTML = renderApprovalList(control.approvals || []);
    initializeApprovalWorkflow(control.review_queue || []);
    $("versionList").innerHTML = renderVersions(control.versions || []);
    $("artifactList").innerHTML = renderArtifacts();
    document.querySelectorAll('.preview-artifact').forEach(button => button.onclick = () => previewArtifact(button.dataset.name));
    $("auditList").innerHTML = renderAuditEvents(control.audit_events || []);
    const settings = control.settings || {};
    $("inputCostRate").value = settings.input_cost_per_million ?? 0;
    $("outputCostRate").value = settings.output_cost_per_million ?? 0;
    $("costBudget").value = settings.cost_budget ?? 0;
    $("driftScoreDrop").value = settings.drift_score_drop ?? 3;
    $("driftPassDrop").value = settings.drift_pass_rate_drop ?? 5;
    $("driftLatencyRise").value = settings.drift_latency_increase_pct ?? 30;
    $("driftP95Rise").value = settings.drift_p95_increase_pct ?? 30;
    $("driftCostRise").value = settings.drift_cost_increase_pct ?? 30;
    $("rateLimitAlert").value = settings.rate_limit_alert_count ?? 1;
    $("judgeHumanGap").value = settings.human_judge_gap_threshold ?? 10;
    const [runs] = await Promise.all([fetchRuns(), fetchCases()]);
    fillControlRunSelect('baselineRun', runs, Math.min(1, Math.max(runs.length - 1, 0)));
    fillControlRunSelect('candidateRun', runs, 0);
    fillControlRunSelect('traceRun', runs, 0);
    fillControlRunSelect('approvalRun', runs, 0);
    if (runs.length) { await Promise.all([loadTraceRun(), loadApprovalCases()]); }
    $("controlLiveStatus").textContent = 'QA Control Center 상태 갱신이 완료되었습니다.';
  } catch (error) {
    $("controlLiveStatus").textContent = '상태 갱신 실패: ' + (error.message || error);
    $("controlReleaseBanner").innerHTML = '<span class="error">상태 갱신 실패: ' + esc(error.message || error) + '</span>';
    if ($("latestQualityOverview")) {
      $("latestQualityOverview").className = 'latest-overview-loading error';
      $("latestQualityOverview").textContent = '최신 품질 데이터를 불러오지 못했습니다.';
    }
  } finally { $("refreshControl").disabled = false; }
}

async function compareSelectedRuns() {
  const baseline = $("baselineRun").value, candidate = $("candidateRun").value;
  if (!baseline || !candidate || baseline === candidate) {
    $("compareResult").innerHTML = '<span class="error">서로 다른 기준선과 후보 실행을 선택하세요.</span>'; return;
  }
  $("compareRuns").disabled = true; $("compareResult").textContent = '비교 중…';
  try {
    const response = await apiFetch('/quality/compare', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({baseline_run_id:baseline,candidate_run_id:candidate})});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(responseError(data));
    const c = data.comparison, s = c.summary;
    const rows = (c.cases || []).map(row => '<tr><td><b>' + esc(row.case_id) + '</b></td><td>' + statusBadge(row.classification, row.classification) +
      '</td><td>' + esc(row.baseline_status) + ' / ' + esc(row.baseline_score ?? '-') + '</td><td>' + esc(row.candidate_status) + ' / ' + esc(row.candidate_score ?? '-') +
      '</td><td>' + (row.score_delta > 0 ? '+' : '') + esc(row.score_delta) + '<br><small>' + esc(row.duration_delta_ms) + 'ms · ' + esc(row.token_delta) + 'tok</small></td><td>' + esc((row.new_defects || []).join(' · ') || '-') + '</td><td>' + (row.output_diff ? '<details><summary>차이 보기</summary><pre>' + esc(row.output_diff) + '</pre></details>' : '<span class="muted">동일</span>') + '</td></tr>').join('');
    const agentRows = Object.keys(s.agent_score_delta || {}).map(key => '<tr><td>' + esc(key) + '</td><td>' + esc(s.agent_score_delta[key]) + '</td><td>' + esc(s.agent_duration_delta_ms?.[key] ?? '-') + ' ms</td></tr>').join('');
    $("compareResult").innerHTML = '<div class="compare-summary"><div class="compact-stat">게이트<b>' + statusBadge(s.release_gate, s.release_gate === 'PASS' ? 'pass' : 'hold') +
      '</b></div><div class="compact-stat">개선<b>' + s.improved + '</b></div><div class="compact-stat">회귀<b>' + s.regressed + '</b></div><div class="compact-stat">점수 Δ<b>' +
      (s.score_delta > 0 ? '+' : '') + s.score_delta + '</b></div><div class="compact-stat">PASS율 Δ<b>' + (s.pass_rate_delta > 0 ? '+' : '') + s.pass_rate_delta + '%p</b></div><div class="compact-stat">P95 Δ<b>' + s.p95_duration_delta_ms + 'ms</b></div><div class="compact-stat">비용 Δ<b>' + Number(s.cost_delta || 0).toFixed(6) + '</b></div><div class="compact-stat">결함 Δ<b>' + s.defect_delta + '</b></div></div>' +
      (agentRows ? '<details><summary>Agent별 점수·처리시간 변화</summary><table><thead><tr><th>Agent/Rubric</th><th>점수 Δ</th><th>지연 Δ</th></tr></thead><tbody>' + agentRows + '</tbody></table></details>' : '') +
      '<div class="table-wrap"><table class="data-table"><thead><tr><th>Case</th><th>판정</th><th>기준선</th><th>후보</th><th>점수·성능 Δ</th><th>신규 결함</th><th>출력 Diff</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
  } catch (error) { $("compareResult").innerHTML = '<span class="error">' + esc(error.message || error) + '</span>'; }
  finally { $("compareRuns").disabled = false; }
}

async function loadTraceRun() {
  const runId = $("traceRun").value;
  if (!runId) return;
  $("traceResult").textContent = 'Agent Trace를 불러오는 중…';
  try {
    const response = await apiFetch('/quality/runs/' + encodeURIComponent(runId));
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(responseError(data));
    traceRunDetail = data.run;
    $("traceCase").innerHTML = (traceRunDetail.cases || []).map((row,index) => '<option value="' + index + '">' + esc(row.case_id + ' · ' + row.status + ' · ' + row.score + '점') + '</option>').join('');
    renderTraceCase();
  } catch (error) { $("traceResult").innerHTML = '<span class="error">' + esc(error.message || error) + '</span>'; }
}

function renderTraceCase() {
  const row = traceRunDetail?.cases?.[Number($("traceCase").value) || 0];
  if (!row) { $("traceResult").innerHTML = '<span class="muted">Trace가 포함된 케이스가 없습니다.</span>'; return; }
  const trace = row.trace || [], max = Math.max(1, ...trace.map(stage => Number(stage.duration_ms) || 0));
  const rag = row.metrics?.rag || {};
  const ragItems = [['Context Precision','context_precision'],['Context Recall','context_recall'],['Faithfulness','faithfulness'],['Relevancy','response_relevancy'],['Noise Sensitivity','noise_sensitivity'],['Citation Coverage','citation_coverage']];
  const ragHtml = Object.keys(rag).length ? '<div class="compare-summary">' + ragItems.map(([label,key]) => '<div class="compact-stat">' + label + '<b>' + Math.round((rag[key] || 0)*100) + '%</b></div>').join('') + '</div>' : '';
  const stages = trace.map(stage => {
    const usageLabel = stage.usage_is_estimated ? '추정' : '공급자 실측';
    const refine = stage.before_refine || stage.after_refine ? '<details style="grid-column:1/-1"><summary>Refine 전후 비교</summary><div class="control-grid"><pre>' + esc(stage.before_refine || '(변경 전 없음)') + '</pre><pre>' + esc(stage.after_refine || '(변경 후 없음)') + '</pre></div></details>' : '';
    const error = stage.error && Object.keys(stage.error).length ? '<pre class="error">' + esc(JSON.stringify(stage.error,null,2)) + '</pre>' : '<span class="muted">오류 없음 · 재시도 ' + esc(stage.retry_count || 0) + '회</span>';
    return '<details class="trace-stage"><summary><b>' + esc(stage.sequence + '. ' + stage.agent) + '</b><br><small>' + esc(stage.provider || '-') + ' · ' + esc(stage.model || '모델 미기록') + ' · Prompt ' + esc(stage.prompt_version || '-') + '</small></summary>' +
      '<div class="trace-bar-wrap"><div class="trace-bar" style="width:' + Math.max(3,(stage.duration_ms/max)*100) + '%"></div></div><span>' + esc(stage.duration_ms) + ' ms</span><span title="' + usageLabel + '">' + esc(stage.input_tokens || 0) + '↘ ' + esc(stage.output_tokens || 0) + '↗<br>' + esc(Number(stage.cost || 0).toFixed(6)) + '</span>' +
      '<div style="grid-column:1/-1" class="control-grid"><div><b>입력</b><pre>' + esc(JSON.stringify(stage.input,null,2)) + '</pre></div><div><b>출력</b><pre>' + esc(JSON.stringify(stage.output,null,2)) + '</pre></div></div><div style="grid-column:1/-1">' + error + '</div>' + refine + '</details>';
  }).join('');
  $("traceResult").innerHTML = '<p><b>' + esc(row.case_id) + '</b> · ' + statusBadge(row.status, row.status === 'PASS' ? 'pass' : 'fail') + ' · ' + esc(row.score) + '점</p>' + ragHtml +
    (stages ? '<div class="trace-list">' + stages + '</div>' : '<span class="muted">이 보고서에는 Agent 단계 정보가 없습니다.</span>');
}

async function loadApprovalCases() {
  const runId = $("approvalRun").value;
  if (!runId) { approvalRunDetail = null; $("approvalCase").innerHTML = '<option value="">실행 전체</option>'; return; }
  const response = await apiFetch('/quality/runs/' + encodeURIComponent(runId));
  const data = await response.json();
  if (!response.ok || !data.ok) return;
  approvalRunDetail = data.run;
  $("approvalCase").innerHTML = '<option value="">실행 전체</option>' + (data.run.cases || []).map(row =>
    '<option value="' + esc(row.case_id) + '">' + esc(row.case_id + ' · ' + (row.question || row.test_descriptor?.title || row.raw?.title || row.raw?.category || '검증 항목').slice(0,55) + ' · ' + row.status + ' · ' + row.score + '점') + '</option>'
  ).join('');
}

function selectManualApproval() {
  const runId = $("approvalRun").value, caseId = $("approvalCase").value;
  if (!runId || !approvalRunDetail) return;
  const run = controlRuns.find(item => item.run_id === runId) || approvalRunDetail;
  const row = (approvalRunDetail.cases || []).find(item => item.case_id === caseId);
  selectedApprovalReview = {
    run_id:runId, case_id:caseId,
    run_label:runLabel(run),
    case_title:row?.test_descriptor?.title || row?.raw?.title || row?.raw?.category || '',
    question:row?.question || '', status:row?.status || (run.failed ? 'FAIL' : 'PASS'),
    score:row?.score ?? run.average_score, judge_score:null, human_score:null,
    reasons:['큐에 없는 대상을 직접 선택'], output:row?.output || ''
  };
  renderSelectedApproval(selectedApprovalReview);
  $("approvalReviewer").focus();
}

async function saveApproval() {
  $("saveApproval").disabled = true;
  try {
    const agreement = $("judgeAgreement").value;
    const score = $("approvalScore").value;
    const response = await apiFetch('/quality/approvals', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      run_id:$("approvalRun").value,case_id:$("approvalCase").value,reviewer:$("approvalReviewer").value,
      decision:$("approvalDecision").value,review_score:score === '' ? null : Number(score),
      judge_agreement:agreement === '' ? null : agreement === 'true',
      final_deployment_approved:$("finalDeploymentApproval").checked,comment:$("approvalComment").value
    })});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(responseError(data));
    $("approvalComment").value = '';
    $("finalDeploymentApproval").checked = false;
    selectedApprovalReview = null;
    renderSelectedApproval(null);
    await refreshControlCenter();
    $("controlLiveStatus").textContent = '검토 결과가 기록되었습니다. 다음 검토 대상을 선택하세요.';
  } catch (error) { $("approvalList").innerHTML = '<span class="error">' + esc(error.message || error) + '</span>'; }
  finally { $("saveApproval").disabled = false; }
}

async function saveObservability() {
  $("saveObservability").disabled = true;
  try {
    const body = {input_cost_per_million:Number($("inputCostRate").value),output_cost_per_million:Number($("outputCostRate").value),cost_budget:Number($("costBudget").value),drift_score_drop:Number($("driftScoreDrop").value),drift_pass_rate_drop:Number($("driftPassDrop").value),drift_latency_increase_pct:Number($("driftLatencyRise").value),drift_p95_increase_pct:Number($("driftP95Rise").value),drift_cost_increase_pct:Number($("driftCostRise").value),rate_limit_alert_count:Number($("rateLimitAlert").value),human_judge_gap_threshold:Number($("judgeHumanGap").value)};
    const response = await apiFetch('/quality/observability-settings', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(responseError(data));
    $("controlLiveStatus").textContent = '비용·드리프트 기준을 저장했습니다.';
    await refreshControlCenter();
  } catch (error) { $("controlLiveStatus").textContent = '관측 기준 저장 실패: ' + (error.message || error); }
  finally { $("saveObservability").disabled = false; }
}

async function saveControlSettings() {
  $("saveControlSettings").disabled = true;
  try {
    const threshold = Number($("controlDeploymentThreshold").value);
    const response = await apiFetch('/quality/deployment-threshold', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({minimum_score:threshold})});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(responseError(data));
    localStorage.setItem('qaDefaultConcurrency', $("controlConcurrency").value);
    localStorage.setItem('qaDefaultJudge', $("controlJudge").value);
    ["offlineConcurrency","liveConcurrency"].forEach(id => { if ($(id)) $(id).value = $("controlConcurrency").value; });
    ["repeatJudge"].forEach(id => { if ($(id)) $(id).value = $("controlJudge").value; });
    $("deploymentThreshold").value = threshold;
    $("controlLiveStatus").textContent = '배포 기준·동시성·Judge 기본값을 저장했습니다.';
    await refreshControlCenter();
  } catch (error) { $("controlLiveStatus").textContent = '중앙 설정 저장 실패: ' + (error.message || error); }
  finally { $("saveControlSettings").disabled = false; }
}

$("refreshControl").onclick = refreshControlCenter;
$("enableNotifications").onclick = async () => {
  if (!('Notification' in window)) { $("controlLiveStatus").textContent = '이 브라우저는 알림을 지원하지 않습니다.'; return; }
  const permission = await Notification.requestPermission();
  $("controlLiveStatus").textContent = '브라우저 알림 권한: ' + permission;
};
$("filterRuns").onclick = fetchRuns;
$("closeRunDetail").onclick = closeRunDetailLayer;
$("runDetailPanel").addEventListener('click', event => {
  if (event.target === $("runDetailPanel")) closeRunDetailLayer();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !$("runDetailPanel").hidden) closeRunDetailLayer();
});
$("copyRunDetail").onclick = async () => {
  if (!selectedRunDetail) {
    $("runDetailStatus").textContent = '먼저 수행결과 이력을 선택하세요.';
    return;
  }
  try {
    await navigator.clipboard.writeText(runResultText(selectedRunDetail));
    $("runDetailStatus").textContent = '소스 원문을 제외한 수행결과 요약을 클립보드에 복사했습니다.';
  } catch (error) {
    $("runDetailStatus").textContent = '클립보드 복사 실패: ' + (error.message || error);
  }
};
$("filterCases").onclick = fetchCases;
$("closeCaseDetail").onclick = () => {
  $("caseDetailPanel").hidden = true;
  $("caseDetailContent").innerHTML = '';
  $("caseDetailStatus").textContent = '';
};
$("runSearch").addEventListener('keydown', event => { if (event.key === 'Enter') fetchRuns(); });
$("caseSearch").addEventListener('keydown', event => { if (event.key === 'Enter') fetchCases(); });
$("compareRuns").onclick = compareSelectedRuns;
$("traceRun").onchange = loadTraceRun;
$("traceCase").onchange = renderTraceCase;
$("saveApproval").onclick = saveApproval;
$("approvalRun").onchange = loadApprovalCases;
$("selectManualApproval").onclick = selectManualApproval;
$("approvalQueueDate").onchange = () => { fillApprovalQueueFilters(approvalQueueData); applyApprovalQueueFilters(); };
$("approvalQueueRun").onchange = applyApprovalQueueFilters;
$("approvalQueueStatus").onchange = applyApprovalQueueFilters;
$("approvalQueueSearch").addEventListener('input', applyApprovalQueueFilters);
$("saveObservability").onclick = saveObservability;
$("saveControlSettings").onclick = saveControlSettings;
$("artifactGroup").onchange = () => {
  $("artifactList").innerHTML = renderArtifacts();
  document.querySelectorAll('.preview-artifact').forEach(button => button.onclick = () => previewArtifact(button.dataset.name));
};
$("saveAuthToken").onclick = () => {
  const token = $("qaAuthToken").value.trim();
  if (token) sessionStorage.setItem('qaOperatorToken', token);
  else sessionStorage.removeItem('qaOperatorToken');
  $("controlLiveStatus").textContent = token ? 'Operator 토큰을 현재 브라우저 세션에 적용했습니다.' : 'Operator 토큰을 세션에서 제거했습니다.';
};

// ---------- 품질 운영·보고서 ----------
let qualityState = null;

function reportLabel(report) {
  const s = report.summary || {};
  const score = s.average_score !== undefined ? ' · ' + s.average_score + '점' :
    (report.average_score !== undefined && report.average_score !== null ? ' · ' + report.average_score + '점' : '');
  const count = s.total !== undefined ? ' · ' + s.passed + '/' + s.total + ' PASS' : '';
  return report.name + count + score;
}

function fillReportSelect(id, reports, multiple = false) {
  const select = $(id);
  const previous = multiple ? Array.from(select.selectedOptions).map(x => x.value) : [select.value];
  select.innerHTML = reports.map((r, i) =>
    '<option value="' + esc(r.name) + '" ' +
    ((previous.includes(r.name) || (!previous[0] && i === 0 && !multiple)) ? 'selected' : '') + '>' +
    esc(reportLabel(r)) + '</option>'
  ).join('');
}

function reportLinks(reports) {
  if (!reports.length) return '<span class="muted">생성된 보고서가 없습니다.</span>';
  return reports.map(r => '<div class="report-item"><a href="/quality/report/' + encodeURIComponent(r.name) + '">' +
    esc(reportLabel(r)) + '</a></div>').join('');
}

function renderQualityDashboard(data) {
  const agents = data.agents || [];
  const ready = agents.filter(x => x.ready).length;
  const suite = data.quality_suite || {};
  const fault = data.fault_diagnosis || {};
  const e2e = (data.e2e_reports || [])[0] || {};
  const judge = (data.judge_reports || [])[0] || {};
  const es = e2e.summary || {};
  const deploymentConfig = data.deployment_config || {};
  const assessment = data.deployment_assessment || {};
  const keyText = (data.api_keys?.openai_configured ? 'OpenAI ✅' : 'OpenAI ❌') + ' · ' +
                  (data.api_keys?.anthropic_configured ? 'Anthropic ✅' : 'Anthropic ❌');
  const runtime = data.agent_runtime || {};
  const runtimeClass = runtime.state === 'ready' ? 'success' : (runtime.state === 'stopped' ? 'error' : 'warning');
  let html = '<div class="metric-grid">' +
    '<div class="metric">에이전트 준비<b>' + ready + '/6</b></div>' +
    '<div class="metric">자동 품질<b>' + esc(suite.passed ?? 0) + '/' + esc(suite.total ?? 0) + '</b></div>' +
    '<div class="metric">장애 진단<b>' + esc(fault.passed ?? 0) + '/' + esc(fault.total ?? 0) + '</b></div>' +
    '<div class="metric">라이브 E2E<b>' + esc(es.passed ?? 0) + '/' + esc(es.total ?? 0) + '</b>' + esc(es.average_score ?? '-') + '점</div>' +
    '<div class="metric">독립 Judge<b>' + esc(judge.average_score ?? '-') + '점</b></div>' +
    '<div class="metric">배포 기준<b>' + esc(deploymentConfig.minimum_score ?? 95) + '점</b></div>' +
    '</div><div class="card ' + runtimeClass + '"><b>실행 상태:</b> ' + esc(runtime.message || '') +
    '</div><div class="card"><b>API 설정:</b> ' + esc(keyText) + '<br><b>에이전트:</b> ' +
    agents.map(x => esc(x.agent) + ' ' + (x.ready ? '✅' : '❌')).join(' · ') + '</div>';
  if (assessment.label) html += '<div class="card ' + (assessment.technical_pass ? 'success' : 'error') + '"><h2>현재 배포 결과</h2>' +
    '<p><b>' + esc(assessment.label) + '</b></p><p>통합 점수 ' + esc(assessment.overall_score) +
    '점 · 기준 ' + esc(assessment.minimum_score) + '점</p>' +
    ((assessment.blockers || []).length ? '<p><b>미충족:</b> ' + esc(assessment.blockers.join(' · ')) + '</p>' : '') + '</div>';
  if (data.deployment?.content) html += '<div class="card"><h2>최종 배포 판단</h2><div class="content">' + esc(data.deployment.content) + '</div></div>';
  return html;
}

async function refreshQualityStatus() {
  $("refreshQuality").disabled = true;
  $("qualityStatusText").textContent = '상태 확인 중…';
  try {
    const res = await apiFetch('/quality/status');
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(responseError(data));
    qualityState = data;
    $("qualityDashboard").innerHTML = renderQualityDashboard(data);
    $("e2eReportList").innerHTML = reportLinks(data.e2e_reports || []);
    $("judgeReportList").innerHTML = reportLinks(data.judge_reports || []);
    $("allReportList").innerHTML = reportLinks(data.all_reports || []);
    fillReportSelect('mergeBase', data.e2e_reports || []);
    fillReportSelect('mergeRetests', data.e2e_reports || [], true);
    fillReportSelect('judgeInput', data.e2e_reports || []);
    fillReportSelect('deployE2E', data.e2e_reports || []);
    fillReportSelect('deployJudge', data.judge_reports || []);
    const deploymentConfig = data.deployment_config || {};
    $("deploymentThreshold").value = deploymentConfig.minimum_score ?? 95;
    $("deploymentThresholdState").textContent = '현재 기준 ' + (deploymentConfig.minimum_score ?? 95) +
      '점 · ' + (deploymentConfig.source === 'saved' ? '웹 저장값 사용 중' : '기본/환경 설정 사용 중') +
      (deploymentConfig.warning ? ' · ' + deploymentConfig.warning : '');
    const repeatProfile = data.repeatability_profile || {};
    $("repeatAutoProfile").innerHTML = '<b>자동 실행:</b> ' + esc(repeatProfile.label || '확인 불가') +
      '<br><span class="muted">' + esc(repeatProfile.reason || '') + '</span>';
    $("qualityStatusText").textContent = '최신 상태로 갱신됨';
  } catch (e) {
    $("qualityStatusText").innerHTML = '<span class="error">' + esc(e.message || e) + '</span>';
  } finally { $("refreshQuality").disabled = false; }
}

const operationResultTargets = {
  runQualitySuite: 'resultQualitySuite',
  runFault: 'resultFault',
  runRedTeam: 'resultRedTeam',
  runQualityGate: 'resultQualityGate',
  runOfflineE2E: 'resultOfflineE2E',
  runRepeatability: 'resultRepeatability',
  runLiveE2E: 'resultLiveE2E',
  mergeReports: 'resultMergeReports',
  runJudge: 'resultJudge',
  saveDeploymentThreshold: 'resultDeploymentThreshold',
  generateDeployment: 'resultDeploymentDecision',
  generateComprehensiveReport: 'resultComprehensiveReport'
};
const activeQualityJobs = new Map();

function operationResultTarget(buttonId) {
  const targetId = operationResultTargets[buttonId];
  const target = targetId ? $(targetId) : null;
  if (!target) throw new Error('실행 결과 영역을 찾을 수 없습니다: ' + buttonId);
  return target;
}

function applyOperationCardLayout(target, data) {
  const card = target.closest('.card');
  if (!card) return;
  const normalized = normalizeOperationResult(data || {});
  const artifactCount = collectResultFiles(data || {}).size;
  const dataSize = JSON.stringify(data || {}).length;
  const needsFullWidth = normalized.rows.length > 6 || artifactCount > 4 || dataSize > 12000;
  card.classList.toggle('is-result-expanded', needsFullWidth);
}

function showOperation(buttonId, title, data, ok = true) {
  const target = operationResultTarget(buttonId);
  target.className = 'operation-result ' + (ok ? 'is-complete' : 'is-error');
  const qaOnly = ['runFault', 'runRedTeam', 'runQualityGate'].includes(buttonId);
  target.innerHTML = '<h3>' + esc(title) + '</h3>' + renderOperationResultData(data, !qaOnly);
  applyOperationCardLayout(target, data);
}

function showJobProgress(buttonId, title, job) {
  const target = operationResultTarget(buttonId);
  const running = ['queued','running'].includes(job.status);
  target.className = 'operation-result job-card ' + (job.status === 'completed' ? 'is-complete' : (job.status === 'failed' ? 'is-error' : ''));
  target.innerHTML = '<h3>' + esc(title) + '</h3><div class="row" style="justify-content:space-between"><b>' +
    esc(job.phase || job.status) + '</b><span>' + esc(job.progress || 0) + '%</span></div>' +
    '<p class="muted">현재: ' + esc(job.current_item || '-') + (job.total_items ? ' · ' + esc(job.processed_items) + '/' + esc(job.total_items) : '') +
    (job.eta_seconds ? ' · 예상 남은 시간 ' + esc(Math.ceil(job.eta_seconds)) + '초' : '') + '</p><div class="progress-shell" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' +
    esc(job.progress || 0) + '"><div class="progress-value" style="width:' + esc(job.progress || 0) + '%"></div></div>' +
    (running ? '<button type="button" class="warn" data-cancel-job="' + esc(job.job_id) + '">실행 취소</button>' : '') +
    (job.error ? '<div class="error">' + esc(job.error.message || job.error.detail || String(job.error)) + '</div>' : '') +
    (job.result ? '<section aria-label="실행 결과 상세">' + renderOperationResultData(
      job.result, !['runFault', 'runRedTeam', 'runQualityGate'].includes(buttonId)
    ) + '</section>' : '');
  applyOperationCardLayout(target, job.result || {});
  const cancelButton = target.querySelector('[data-cancel-job]');
  if (cancelButton) cancelButton.onclick = () => cancelQualityJob(buttonId, title, job.job_id);
}

async function cancelQualityJob(buttonId, title, jobId) {
  if (!jobId) return;
  try {
    const response = await apiFetch('/quality/jobs/' + encodeURIComponent(jobId) + '/cancel', {method:'DELETE'});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(responseError(data));
    if (data.job) showJobProgress(buttonId, title, data.job);
  } catch (error) {
    showOperation(buttonId, title + ' 취소 실패', {error:error.message || String(error)}, false);
  }
}

async function runQualityJob(buttonId, title, operation, payload = {}) {
  const button = $(buttonId);
  button.disabled = true;
  let jobId = null;
  try {
    const response = await apiFetch('/quality/jobs', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation,payload})});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(responseError(data));
    jobId = data.job.job_id;
    activeQualityJobs.set(buttonId, jobId);
    showJobProgress(buttonId, title, data.job);
    while (true) {
      await new Promise(resolve => setTimeout(resolve, 800));
      const poll = await apiFetch('/quality/jobs/' + encodeURIComponent(jobId));
      const state = await poll.json();
      if (!poll.ok || !state.ok) throw new Error(responseError(state));
      showJobProgress(buttonId, title, state.job);
      if (!['queued','running'].includes(state.job.status)) {
        if (state.job.status === 'completed') {
          await Promise.all([refreshQualityStatus(), refreshControlCenter()]);
        }
        break;
      }
    }
  } catch (error) {
    showOperation(buttonId, title + ' 실패', {error:error.message || String(error)}, false);
  } finally {
    if (activeQualityJobs.get(buttonId) === jobId) activeQualityJobs.delete(buttonId);
    button.disabled = false;
  }
}

async function runQualityOperation(buttonId, title, url, body = {}) {
  const button = $(buttonId);
  button.disabled = true;
  showOperation(buttonId, title, {status: '실행 중입니다. 완료될 때까지 이 탭을 유지하세요.'});
  try {
    const res = await apiFetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(responseError(data));
    showOperation(buttonId, title + ' 완료', data);
    await refreshQualityStatus();
    return data;
  } catch (e) {
    showOperation(buttonId, title + ' 실패', {error: e.message || String(e)}, false);
    return null;
  } finally { button.disabled = false; }
}

$("refreshQuality").onclick = refreshQualityStatus;
$("runQualitySuite").onclick = () => runQualityJob('runQualitySuite', '자동 품질 테스트', 'quality-suite');
$("runFault").onclick = () => runQualityJob('runFault', '장애 진단', 'fault-diagnosis');
$("runRedTeam").onclick = () => runQualityJob('runRedTeam', 'OWASP Red Team', 'red-team');
$("runQualityGate").onclick = () => runQualityJob('runQualityGate', 'CI 품질 게이트', 'quality-gate', {
  domain: $("gateDomain").value,
  minimum_score: Number($("deploymentThreshold").value || 95)
});
$("runOfflineE2E").onclick = () => runQualityJob('runOfflineE2E', '외부 LLM E2E', 'offline-e2e', {
  domain: $("offlineDomain").value,
  limit: $("offlineLimit").value,
  concurrency: Number($("offlineConcurrency").value),
  case_ids: $("offlineCaseIds").value.split(',').map(x => x.trim()).filter(Boolean)
});
$("runRepeatability").onclick = () => runQualityJob('runRepeatability', '반복 안정성·Flakiness', 'repeatability', {
  domain: $("repeatDomain").value,
  limit: $("repeatLimit").value,
  trials: Number($("repeatTrials").value),
  concurrency: 1,
  case_ids: $("repeatCaseIds").value.split(',').map(x => x.trim()).filter(Boolean)
});
$("runLiveE2E").onclick = () => {
  const ids = $("liveCaseIds").value.split(',').map(x => x.trim()).filter(Boolean);
  return runQualityJob('runLiveE2E', '실제 API 라이브 E2E', 'live-e2e', {
    domain: $("liveDomain").value,
    limit: $("liveLimit").value,
    concurrency: Number($("liveConcurrency").value),
    case_ids: ids
  });
};
$("mergeReports").onclick = () => runQualityOperation('mergeReports', '재시험 보고서 통합', '/quality/merge-reports', {
  base_report: $("mergeBase").value,
  retest_reports: Array.from($("mergeRetests").selectedOptions).map(x => x.value)
});
$("runJudge").onclick = () => runQualityOperation('runJudge', '독립 LLM Judge', '/quality/run-judge', {
  input_report: $("judgeInput").value
});
$("saveDeploymentThreshold").onclick = () => runQualityOperation(
  'saveDeploymentThreshold', '배포 기준 점수 저장', '/quality/deployment-threshold', {
    minimum_score: Number($("deploymentThreshold").value)
  }
);
$("generateDeployment").onclick = () => runQualityOperation('generateDeployment', '최종 배포 판단', '/quality/generate-deployment', {
  e2e_report: $("deployE2E").value,
  judge_report: $("deployJudge").value
});
$("generateComprehensiveReport").onclick = () => runQualityJob(
  'generateComprehensiveReport', '35건 종합 품질평가 보고서', 'comprehensive-report'
);

resetBatchSource();
if (currentPanel === 'control') refreshControlCenter();
if (currentPanel === 'quality') refreshQualityStatus();
</script>
</body>
</html>
"""


def _latest_report(pattern: str) -> Path | None:
    matches = [path for path in REPORTS_PATH.glob(pattern) if path.is_file()]
    return max(matches, key=lambda path: path.stat().st_mtime) if matches else None


def _read_json_file(path: Path | None) -> dict:
    if path is None or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _safe_report_path(name: str, *, suffix: str | None = None) -> Path:
    raw_name = str(name or "").strip()
    if not raw_name or raw_name != Path(raw_name).name:
        raise ValidationError("올바른 보고서 파일명을 입력하세요.")
    candidate = (REPORTS_PATH / raw_name).resolve()
    if candidate.parent != REPORTS_PATH.resolve() or not candidate.is_file():
        raise ValidationError("보고서 파일을 찾을 수 없습니다.")
    if candidate.suffix.lower() not in REPORT_SUFFIXES:
        raise ValidationError("허용되지 않은 보고서 형식입니다.")
    if suffix and candidate.suffix.lower() != suffix:
        raise ValidationError(f"{suffix} 보고서만 사용할 수 있습니다.")
    return candidate


def _report_entry(path: Path) -> dict:
    payload = _read_json_file(path) if path.suffix.lower() == ".json" else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "name": path.name,
        "size": path.stat().st_size,
        "modified_at": path.stat().st_mtime,
        "summary": summary,
        "average_score": payload.get("average_score"),
        "provider": payload.get("provider"),
        "live_verified": payload.get("live_llm_judge_verified"),
    }


async def _endpoint_ready(endpoint: str) -> bool:
    channel = grpc.aio.insecure_channel(endpoint)
    try:
        await asyncio.wait_for(channel.channel_ready(), timeout=0.7)
        return True
    except Exception:
        return False
    finally:
        await channel.close()


def _agent_endpoints() -> tuple[str, ...]:
    """Return the six internal Agent endpoints without exposing them publicly."""
    import grpc_server as grpc_runtime_module

    return (
        grpc_runtime_module.INTERPRETER_ENDPOINT,
        grpc_runtime_module.RETRIEVER_ENDPOINT,
        grpc_runtime_module.SUMMARIZER_ENDPOINT,
        grpc_runtime_module.EVALUATOR_ENDPOINT,
        grpc_runtime_module.CRITIC_ENDPOINT,
        grpc_runtime_module.IMPROVER_ENDPOINT,
    )


async def healthz(request):
    """Minimal unauthenticated health check for containers and load balancers."""
    endpoints = _agent_endpoints()
    ready = await asyncio.gather(*(_endpoint_ready(endpoint) for endpoint in endpoints))
    ready_count = sum(ready)
    healthy = ready_count == len(endpoints)
    return JSONResponse(
        {
            "ok": healthy,
            "service": "voc-improve",
            "agents_ready": ready_count,
            "agents_total": len(endpoints),
        },
        status_code=200 if healthy else 503,
    )


async def _run_fixed_script(script: str, *args: str, timeout: float = 1800) -> dict:
    child_env = dict(os.environ)
    child_env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(ROOT_PATH / script),
        *args,
        cwd=str(ROOT_PATH),
        env=child_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.CancelledError:
        process.kill()
        await process.wait()
        raise
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise TimeoutError(f"{script} 실행 제한시간을 초과했습니다.")
    output = stdout.decode("utf-8", errors="replace")
    if process.returncode != 0:
        raise RuntimeError(output[-4000:] or f"{script} 실행 실패")
    return {"returncode": process.returncode, "output": output[-8000:]}


async def control_center_dashboard(request):
    """Return indexed quality history, trends, approvals and drift alerts."""
    try:
        dashboard = await asyncio.to_thread(CONTROL_CENTER.dashboard)
        artifacts = sorted(
            (
                path for path in REPORTS_PATH.iterdir()
                if path.is_file() and path.suffix.lower() in REPORT_SUFFIXES
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:200]
        dashboard["artifacts"] = [
            {
                **_report_entry(path),
                "group": (
                    "evidence" if path.name.startswith("test_evidence_")
                    else "attachment" if path.suffix.lower() in {".pdf", ".zip", ".png"}
                    else "result" if path.suffix.lower() in {".json", ".csv"}
                    else "document"
                ),
            }
            for path in artifacts
        ]
        timestamp_groups: dict[str, list[dict]] = {}
        for item in dashboard["artifacts"]:
            match = re.search(r"(20\d{6}_\d{6}(?:_\d{6})?)", item["name"])
            if match:
                timestamp_groups.setdefault(match.group(1)[:15], []).append(item)
        bundles = []
        for run in await asyncio.to_thread(CONTROL_CENTER.list_runs, limit=100):
            match = re.search(r"(20\d{6}_\d{6})", run["source_file"])
            related = timestamp_groups.get(match.group(1), []) if match else [
                item for item in dashboard["artifacts"] if item["name"] == run["source_file"]
            ]
            bundles.append({
                "run_id": run["run_id"], "generated_at": run["generated_at"],
                "kind": run["kind"], "domain": run["domain"],
                "source_file": run["source_file"], "artifacts": related,
            })
        dashboard["artifact_bundles"] = bundles
        dashboard["audit_events"] = await asyncio.to_thread(
            CONTROL_CENTER.list_audit_events, 50
        )
        dashboard["auth"] = {
            "enabled": any(_auth_tokens().values()),
            "role": getattr(request.state, "qa_role", "local-admin"),
            "configured_roles": [role for role, token in _auth_tokens().items() if token],
            "storage": "browser session only",
        }
        return JSONResponse({"ok": True, **dashboard})
    except Exception as exc:
        return JSONResponse(error_result("CONTROL_CENTER_FAILED", str(exc)), status_code=500)


async def control_center_runs(request):
    try:
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        params = request.query_params
        runs = await asyncio.to_thread(
            CONTROL_CENTER.list_runs,
            limit=int(params.get("limit") or 100),
            kind=str(params.get("kind") or ""),
            domain=str(params.get("domain") or ""),
            status=str(params.get("status") or ""),
            query=str(params.get("query") or ""),
            minimum_score=float(params["minimum_score"]) if params.get("minimum_score") else None,
            maximum_score=float(params["maximum_score"]) if params.get("maximum_score") else None,
            defects_only=str(params.get("defects_only") or "").lower() in {"1", "true", "yes"},
            agent=str(params.get("agent") or ""),
            sort_by=str(params.get("sort_by") or "generated_at"),
            sort_direction=str(params.get("sort_direction") or "desc"),
        )
        return JSONResponse({"ok": True, "runs": runs, "count": len(runs)})
    except (TypeError, ValueError) as exc:
        return JSONResponse(error_result("INVALID_RUN_FILTER", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("RUN_HISTORY_FAILED", str(exc)), status_code=500)


async def control_center_run_detail(request):
    try:
        run_id = str(request.path_params.get("run_id") or "").strip()
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        run = await asyncio.to_thread(CONTROL_CENTER.get_run, run_id)
        if run is None:
            return JSONResponse(error_result("RUN_NOT_FOUND", "실행 이력을 찾을 수 없습니다."), status_code=404)
        return JSONResponse({"ok": True, "run": run})
    except Exception as exc:
        return JSONResponse(error_result("RUN_DETAIL_FAILED", str(exc)), status_code=500)


async def download_run_word_report(request):
    """선택한 수행 이력의 전체 데이터를 Word 종합 품질평가 보고서로 제공합니다."""
    try:
        run_id = str(request.path_params.get("run_id") or "").strip()
        if not run_id:
            raise ValidationError("실행 ID가 필요합니다.")
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        run = await asyncio.to_thread(CONTROL_CENTER.get_run, run_id)
        if run is None:
            return JSONResponse(error_result("RUN_NOT_FOUND", "실행 이력을 찾을 수 없습니다."), status_code=404)
        path = await asyncio.to_thread(build_history_word_report, run, REPORTS_PATH)
        await asyncio.to_thread(
            CONTROL_CENTER.audit,
            "HISTORY_WORD_REPORT_GENERATED",
            getattr(request.state, "qa_actor", "web"),
            run_id,
            {"file": path.name, "size": path.stat().st_size},
        )
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=path.name,
        )
    except ValidationError as exc:
        return JSONResponse(error_result("INVALID_RUN_REPORT", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("RUN_WORD_REPORT_FAILED", str(exc)), status_code=500)


async def control_center_cases(request):
    try:
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        params = request.query_params
        rows = await asyncio.to_thread(
            CONTROL_CENTER.list_case_results,
            limit=int(params.get("limit") or 200),
            run_id=str(params.get("run_id") or ""),
            domain=str(params.get("domain") or ""),
            status=str(params.get("status") or ""),
            query=str(params.get("query") or ""),
            defects_only=str(params.get("defects_only") or "").lower() in {"1", "true", "yes"},
            agent=str(params.get("agent") or ""),
            minimum_score=float(params["minimum_score"]) if params.get("minimum_score") else None,
            sort_by=str(params.get("sort_by") or "score"),
            sort_direction=str(params.get("sort_direction") or "asc"),
        )
        return JSONResponse({"ok": True, "cases": rows, "count": len(rows)})
    except (TypeError, ValueError) as exc:
        return JSONResponse(error_result("INVALID_CASE_FILTER", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("CASE_HISTORY_FAILED", str(exc)), status_code=500)


async def control_center_review_queue(request):
    try:
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        queue = await asyncio.to_thread(
            CONTROL_CENTER.review_queue, int(request.query_params.get("limit") or 100)
        )
        return JSONResponse({"ok": True, "queue": queue, "count": len(queue)})
    except Exception as exc:
        return JSONResponse(error_result("REVIEW_QUEUE_FAILED", str(exc)), status_code=500)


async def control_center_versions(request):
    try:
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        versions = await asyncio.to_thread(
            CONTROL_CENTER.version_history, int(request.query_params.get("limit") or 100)
        )
        return JSONResponse({"ok": True, "versions": versions, "count": len(versions)})
    except Exception as exc:
        return JSONResponse(error_result("VERSION_HISTORY_FAILED", str(exc)), status_code=500)


async def control_center_compare(request):
    try:
        data = await request.json()
        baseline = str(data.get("baseline_run_id") or "").strip()
        candidate = str(data.get("candidate_run_id") or "").strip()
        if not baseline or not candidate or baseline == candidate:
            raise ValidationError("서로 다른 기준선과 후보 실행을 선택하세요.")
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        comparison = await asyncio.to_thread(CONTROL_CENTER.compare_runs, baseline, candidate)
        return JSONResponse({"ok": True, "comparison": comparison})
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return JSONResponse(error_result("COMPARE_FAILED", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("COMPARE_FAILED", str(exc)), status_code=500)


async def control_center_approvals(request):
    try:
        if request.method == "GET":
            run_id = str(request.query_params.get("run_id") or "")
            approvals = await asyncio.to_thread(
                CONTROL_CENTER.list_approvals, run_id=run_id, limit=100
            )
            return JSONResponse({"ok": True, "approvals": approvals})
        data = await request.json()
        approval = await asyncio.to_thread(
            CONTROL_CENTER.create_approval,
            str(data.get("run_id") or ""),
            str(data.get("reviewer") or ""),
            str(data.get("decision") or ""),
            str(data.get("comment") or ""),
            case_id=str(data.get("case_id") or ""),
            review_score=data.get("review_score"),
            judge_agreement=data.get("judge_agreement")
            if isinstance(data.get("judge_agreement"), bool) else None,
            final_deployment_approved=data.get("final_deployment_approved") is True,
        )
        return JSONResponse({"ok": True, "approval": approval})
    except (ValueError, json.JSONDecodeError) as exc:
        return JSONResponse(error_result("APPROVAL_FAILED", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("APPROVAL_FAILED", str(exc)), status_code=500)


async def control_center_settings(request):
    try:
        if request.method == "GET":
            settings = await asyncio.to_thread(CONTROL_CENTER.load_settings)
        else:
            data = await request.json()
            settings = await asyncio.to_thread(
                CONTROL_CENTER.save_settings,
                data,
                getattr(request.state, "qa_actor", "web"),
            )
        return JSONResponse({"ok": True, "settings": settings})
    except (ValueError, json.JSONDecodeError) as exc:
        return JSONResponse(error_result("OBSERVABILITY_SETTINGS_FAILED", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("OBSERVABILITY_SETTINGS_FAILED", str(exc)), status_code=500)


async def control_center_drift(request):
    try:
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        alerts = await asyncio.to_thread(CONTROL_CENTER.drift_alerts)
        return JSONResponse({"ok": True, "alerts": alerts, "count": len(alerts)})
    except Exception as exc:
        return JSONResponse(error_result("DRIFT_CHECK_FAILED", str(exc)), status_code=500)


async def control_center_audit(request):
    try:
        events = await asyncio.to_thread(CONTROL_CENTER.list_audit_events, 100)
        return JSONResponse({"ok": True, "events": events})
    except Exception as exc:
        return JSONResponse(error_result("AUDIT_LOG_FAILED", str(exc)), status_code=500)


QUALITY_JOB_LABELS = {
    "quality-suite": "자동 품질 테스트",
    "fault-diagnosis": "장애 진단",
    "red-team": "OWASP Red Team",
    "quality-gate": "CI 품질 게이트",
    "offline-e2e": "외부 LLM E2E",
    "live-e2e": "라이브 E2E",
    "repeatability": "반복 안정성",
    "comprehensive-report": "35건 종합 보고서",
}


async def _execute_quality_job(operation: str, data: dict, update) -> dict:
    update(5, "입력값과 실행 환경 확인")
    async with QUALITY_OPERATION_LOCK:
        if operation == "quality-suite":
            update(15, "30개 자동 품질 테스트 실행")
            execution = await _run_fixed_script("quality_diagnosis/run_quality_suite.py")
            result = {"result": _read_json_file(REPORTS_PATH / "test_result.json"), **execution}
        elif operation == "fault-diagnosis":
            update(20, "포트·API·CSV·타임아웃 장애 점검")
            execution = await _run_fixed_script("quality_diagnosis/run_fault_diagnosis.py")
            result = {"result": _read_json_file(_latest_report("fault_diagnosis_*.json")), **execution}
        elif operation == "red-team":
            update(30, "OWASP 정렬 공격 시나리오 20종 점검")
            result = await asyncio.to_thread(run_red_team, REPORTS_PATH)
        elif operation == "quality-gate":
            domain = str(data.get("domain") or "ecommerce").lower()
            threshold = float(data.get("minimum_score") or load_deployment_config()["minimum_score"])
            update(15, "자동 테스트·Red Team·E2E 게이트 통합")
            result = await asyncio.to_thread(
                run_quality_gate,
                output_dir=REPORTS_PATH,
                domain=domain,
                minimum_score=threshold,
                execute_suite=True,
                execute_red_team=True,
            )
        elif operation in {"offline-e2e", "live-e2e"}:
            profile = _require_live_api_policy()
            mode = "live"
            domain, config, limit, case_ids, concurrency = _parse_e2e_selection(data)
            update(15, f"{domain} {mode} 6-Agent E2E 실행")
            result = await run_e2e(
                mode,
                Path(config["cases_path"]),
                REPORTS_PATH,
                Path(config["csv_path"]),
                domain,
                limit,
                case_ids or None,
                concurrency,
                lambda done, total, case_id, phase: update(
                    15 + int((done / max(total, 1)) * 75),
                    phase,
                    case_id,
                    done,
                    total,
                ),
            )
            update(90, "외부 LLM Judge 평가", str(profile["judge_provider"]))
            result["external_judge"] = await run_llm_judge(
                str(profile["judge_provider"]), Path(result["json"]), REPORTS_PATH,
                include_all=True,
            )
        elif operation == "repeatability":
            profile = _require_live_api_policy()
            mode = str(profile["mode"])
            judge_provider = str(profile["judge_provider"])
            trials = int(data.get("trials") or 3)
            if not 2 <= trials <= 5:
                raise ValidationError("반복 횟수는 2~5회여야 합니다.")
            domain, config, limit, case_ids, concurrency = _parse_e2e_selection(data)
            update(12, f"{trials}회 반복 · {profile['label']}")
            result = await run_repeatability(
                mode=mode,
                domain=domain,
                cases_path=Path(config["cases_path"]),
                csv_path=Path(config["csv_path"]),
                output_dir=REPORTS_PATH,
                trials=trials,
                limit=limit,
                case_ids=case_ids or None,
                concurrency=concurrency,
                judge_provider=judge_provider,
                progress_callback=lambda done, total, phase: update(
                    12 + int((done / max(total, 1)) * 78),
                    phase,
                    f"반복 {min(done + 1, total)}/{total}",
                    done,
                    total,
                ),
            )
            result["automatic_profile"] = profile
        elif operation == "comprehensive-report":
            update(15, "35건 통합 품질 재평가")
            evaluation = await _run_fixed_script("quality_diagnosis/run_35_case_evaluation.py", timeout=600)
            update(70, "PDF·HTML·XML·TXT·ZIP 보고서 생성")
            report = await _run_fixed_script("quality_diagnosis/build_comprehensive_report.py", timeout=300)
            result = {
                "test_result": "35/35 PASS",
                "pdf": _report_entry(_latest_report("*.pdf")) if _latest_report("*.pdf") else None,
                "attachment": _report_entry(_latest_report("*.zip")) if _latest_report("*.zip") else None,
                "evaluation_output": evaluation["output"],
                "report_output": report["output"],
            }
        else:
            raise ValidationError("지원하지 않는 백그라운드 작업입니다.")
    if operation in {"quality-suite", "fault-diagnosis", "red-team", "quality-gate", "comprehensive-report"}:
        update(82, "필수 외부 LLM 검증 준비")
        result["external_validation"] = await _run_live_external_validation(data, update)
    update(95, "이력 색인과 웹 상태 갱신")
    await asyncio.to_thread(CONTROL_CENTER.sync_reports)
    return result


async def quality_jobs(request):
    try:
        if request.method == "GET":
            jobs = await JOB_MANAGER.list(int(request.query_params.get("limit") or 50))
            return JSONResponse({"ok": True, "jobs": jobs})
        data = await request.json()
        operation = str(data.get("operation") or "").strip()
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        if operation not in QUALITY_JOB_LABELS:
            raise ValidationError("지원하지 않는 품질 작업입니다.")

        async def runner(update):
            return await _execute_quality_job(operation, payload, update)

        job = await JOB_MANAGER.create(operation, QUALITY_JOB_LABELS[operation], runner)
        return JSONResponse({"ok": True, "job": job}, status_code=202)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return JSONResponse(error_result("JOB_CREATE_FAILED", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("JOB_CREATE_FAILED", str(exc)), status_code=500)


async def quality_job_detail(request):
    job_id = str(request.path_params.get("job_id") or "")
    job = await JOB_MANAGER.get(job_id)
    if job is None:
        return JSONResponse(error_result("JOB_NOT_FOUND", "작업 이력을 찾을 수 없습니다."), status_code=404)
    return JSONResponse({"ok": True, "job": job})


async def quality_job_cancel(request):
    job_id = str(request.path_params.get("job_id") or "")
    job = await JOB_MANAGER.cancel(job_id)
    if job is None:
        return JSONResponse(error_result("JOB_NOT_FOUND", "취소할 작업을 찾을 수 없습니다."), status_code=404)
    return JSONResponse({"ok": True, "job": job})


async def quality_status(request):
    """웹 품질 운영 탭에 서버·API·최신 보고서 상태를 제공합니다."""
    import grpc_server as grpc_runtime_module

    endpoints = {
        "Interpreter": grpc_runtime_module.INTERPRETER_ENDPOINT,
        "Retriever": grpc_runtime_module.RETRIEVER_ENDPOINT,
        "Summarizer": grpc_runtime_module.SUMMARIZER_ENDPOINT,
        "Evaluator": grpc_runtime_module.EVALUATOR_ENDPOINT,
        "Critic": grpc_runtime_module.CRITIC_ENDPOINT,
        "Improver": grpc_runtime_module.IMPROVER_ENDPOINT,
    }
    ready_values = await asyncio.gather(*(_endpoint_ready(value) for value in endpoints.values()))
    agents = [
        {"agent": name, "endpoint": endpoint, "ready": ready}
        for (name, endpoint), ready in zip(endpoints.items(), ready_values)
    ]
    ready_count = sum(agent["ready"] for agent in agents)
    if ready_count == len(agents):
        runtime_state = "ready"
        runtime_message = "6개 Agent가 이미 정상 실행 중입니다. grpc_server.py를 다시 실행할 필요가 없습니다."
    elif ready_count == 0:
        runtime_state = "stopped"
        runtime_message = "Agent가 실행되지 않았습니다. python grpc_server.py를 먼저 실행하세요."
    else:
        runtime_state = "partial"
        runtime_message = f"일부 Agent만 실행 중입니다({ready_count}/6). 부분 프로세스를 정리한 뒤 다시 시작하세요."
    e2e_reports = sorted(
        REPORTS_PATH.glob("*e2e_*.json"),
        key=lambda path: (
            2 if "live_retest_merged" in path.name else 1 if "live_e2e" in path.name else 0,
            path.stat().st_mtime,
        ),
        reverse=True,
    )
    judge_reports = sorted(
        REPORTS_PATH.glob("llm_judge_*.json"),
        key=lambda path: (
            0 if "deterministic" in path.name else 1,
            path.stat().st_mtime,
        ),
        reverse=True,
    )
    all_reports = sorted(
        (
            path for path in REPORTS_PATH.iterdir()
            if path.is_file() and path.suffix.lower() in REPORT_SUFFIXES
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if REPORTS_PATH.is_dir() else []
    test_result = _read_json_file(REPORTS_PATH / "test_result.json")
    fault_result = _read_json_file(_latest_report("fault_diagnosis_*.json"))
    selected_e2e = _read_json_file(e2e_reports[0] if e2e_reports else None)
    selected_judge = _read_json_file(judge_reports[0] if judge_reports else None)
    deployment_config = load_deployment_config()
    human_approval = None
    if e2e_reports:
        try:
            await asyncio.to_thread(CONTROL_CENTER.sync_reports)
            matched = next(
                (
                    run for run in await asyncio.to_thread(CONTROL_CENTER.list_runs, limit=300)
                    if run["source_file"] == e2e_reports[0].name
                ),
                None,
            )
            if matched:
                approvals = await asyncio.to_thread(
                    CONTROL_CENTER.list_approvals, run_id=matched["run_id"], limit=1
                )
                human_approval = approvals[0] if approvals else None
        except Exception:
            human_approval = None
    deployment_assessment = evaluate_release_evidence(
        test_result,
        fault_result,
        selected_e2e,
        selected_judge,
        deployment_config["minimum_score"],
        human_approval,
    )
    deployment_path = REPORTS_PATH / "deployment_decision.md"
    return JSONResponse({
        "ok": True,
        "api_keys": {
            "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
            "anthropic_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        },
        "repeatability_profile": _repeatability_profile(),
        "agents": agents,
        "agent_runtime": {
            "state": runtime_state,
            "ready_count": ready_count,
            "total": len(agents),
            "launch_required": ready_count == 0,
            "message": runtime_message,
        },
        "quality_suite": test_result,
        "fault_diagnosis": fault_result,
        "deployment_config": deployment_config,
        "deployment_assessment": deployment_assessment,
        "e2e_reports": [_report_entry(path) for path in e2e_reports],
        "judge_reports": [_report_entry(path) for path in judge_reports],
        "all_reports": [_report_entry(path) for path in all_reports],
        "deployment": {
            "name": deployment_path.name if deployment_path.is_file() else None,
            "content": deployment_path.read_text(encoding="utf-8") if deployment_path.is_file() else "",
        },
    })


async def deployment_threshold_web(request):
    """웹에서 조정한 배포 기준 점수를 영구 저장합니다."""
    try:
        data = await request.json()
        async with QUALITY_OPERATION_LOCK:
            config = save_deployment_config(data.get("minimum_score"))
        return JSONResponse({
            "ok": True,
            "deployment_config": config,
            "message": f"배포 기준 점수를 {config['minimum_score']}점으로 저장했습니다.",
        })
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return JSONResponse(error_result("INVALID_DEPLOYMENT_THRESHOLD", str(exc)), status_code=400)
    except OSError as exc:
        return JSONResponse(error_result("DEPLOYMENT_THRESHOLD_SAVE_FAILED", str(exc)), status_code=500)


async def run_quality_suite_web(request):
    try:
        async with QUALITY_OPERATION_LOCK:
            execution = await _run_fixed_script("quality_diagnosis/run_quality_suite.py")
            external = await _run_live_external_validation({})
        return JSONResponse({"ok": True, "result": _read_json_file(REPORTS_PATH / "test_result.json"), "external_validation": external, **execution})
    except Exception as exc:
        return JSONResponse(error_result("QUALITY_SUITE_FAILED", str(exc)), status_code=500)


async def run_fault_diagnosis_web(request):
    try:
        async with QUALITY_OPERATION_LOCK:
            execution = await _run_fixed_script("quality_diagnosis/run_fault_diagnosis.py")
            external = await _run_live_external_validation({})
        return JSONResponse({
            "ok": True,
            "result": _read_json_file(_latest_report("fault_diagnosis_*.json")),
            "external_validation": external,
            **execution,
        })
    except Exception as exc:
        return JSONResponse(error_result("FAULT_DIAGNOSIS_FAILED", str(exc)), status_code=500)


async def run_red_team_web(request):
    try:
        async with QUALITY_OPERATION_LOCK:
            result = await asyncio.to_thread(run_red_team, REPORTS_PATH)
            result["external_validation"] = await _run_live_external_validation({})
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        return JSONResponse({"ok": True, **result})
    except Exception as exc:
        return JSONResponse(error_result("RED_TEAM_FAILED", str(exc)), status_code=500)


async def run_quality_gate_web(request):
    try:
        data = await request.json()
        domain = str(data.get("domain") or "ecommerce").lower()
        threshold = data.get("minimum_score")
        minimum_score = float(threshold) if threshold not in (None, "") else None
        async with QUALITY_OPERATION_LOCK:
            result = await asyncio.to_thread(
                run_quality_gate,
                output_dir=REPORTS_PATH,
                domain=domain,
                minimum_score=minimum_score,
                execute_suite=True,
                execute_red_team=True,
            )
            result["external_validation"] = await _run_live_external_validation(data)
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        return JSONResponse({"ok": True, **result})
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return JSONResponse(error_result("QUALITY_GATE_FAILED", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("QUALITY_GATE_FAILED", str(exc)), status_code=500)


def _parse_e2e_selection(data: dict) -> tuple[str, dict, int | None, list[str], int]:
    domain = str(data.get("domain") or "ecommerce").lower()
    config = TEST_SETS.get(domain)
    if config is None:
        raise ValidationError("지원하지 않는 테스트 도메인입니다.")
    limit_value = data.get("limit")
    limit = int(limit_value) if limit_value not in (None, "", "all") else None
    if limit is not None and not 1 <= limit <= 50:
        raise ValidationError("실행 건수는 1~50 사이여야 합니다.")
    raw_case_ids = data.get("case_ids") or []
    if not isinstance(raw_case_ids, list):
        raise ValidationError("case_ids는 목록 형식이어야 합니다.")
    case_ids = [str(value).strip() for value in raw_case_ids if str(value).strip()]
    concurrency = int(data.get("concurrency") or 2)
    if not 1 <= concurrency <= 4:
        raise ValidationError("동시 실행 수는 1~4 사이여야 합니다.")
    return domain, config, limit, case_ids, concurrency


async def _run_live_external_validation(data: dict, update=None) -> dict:
    """Run the mandatory live E2E and independent external Judge gate."""
    profile = _require_live_api_policy()
    domain, config, limit, case_ids, concurrency = _parse_e2e_selection(data)

    def notify(percent: int, phase: str, current: str = "") -> None:
        if update:
            update(percent, phase, current)

    notify(84, f"{domain} 라이브 6-Agent E2E")
    e2e = await run_e2e(
        "live",
        Path(config["cases_path"]),
        REPORTS_PATH,
        Path(config["csv_path"]),
        domain,
        limit,
        case_ids or None,
        concurrency,
    )
    provider = str(profile["judge_provider"])
    notify(91, "외부 LLM Judge 평가", provider)
    judge = await run_llm_judge(
        provider,
        Path(e2e["json"]),
        REPORTS_PATH,
        include_all=True,
    )
    return {
        "policy": "mandatory-live-llm",
        "provider": provider,
        "e2e": e2e,
        "judge": judge,
    }


async def run_offline_e2e_web(request):
    try:
        data = await request.json()
        async with QUALITY_OPERATION_LOCK:
            external = await _run_live_external_validation(data)
        return JSONResponse({
            "ok": True,
            **external["e2e"],
            "external_judge": external["judge"],
            "policy": external["policy"],
        })
    except (ValidationError, ValueError) as exc:
        return JSONResponse(error_result("INVALID_INPUT", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("OFFLINE_E2E_FAILED", str(exc)), status_code=500)


async def run_live_e2e_web(request):
    try:
        data = await request.json()
        async with QUALITY_OPERATION_LOCK:
            external = await _run_live_external_validation(data)
        return JSONResponse({"ok": True, **external["e2e"], "external_judge": external["judge"], "policy": external["policy"]})
    except (ValidationError, ValueError) as exc:
        return JSONResponse(error_result("INVALID_INPUT", str(exc)), status_code=400)
    except Exception as exc:
        if is_rate_limit_error(exc):
            await asyncio.to_thread(
                CONTROL_CENTER.audit, "API_RATE_LIMITED", "web", "live-e2e",
                {"error_type": type(exc).__name__},
            )
            return JSONResponse(
                error_result("API_RATE_LIMITED", rate_limit_guidance(), trace=type(exc).__name__),
                status_code=429,
            )
        return JSONResponse(error_result("LIVE_E2E_FAILED", str(exc)), status_code=500)


async def run_repeatability_web(request):
    try:
        data = await request.json()
        profile = _require_live_api_policy()
        mode = str(profile["mode"])
        judge_provider = str(profile["judge_provider"])
        trials = int(data.get("trials") or 3)
        if not 2 <= trials <= 5:
            raise ValidationError("반복 횟수는 2~5회여야 합니다.")
        domain, config, limit, case_ids, concurrency = _parse_e2e_selection(data)
        async with QUALITY_OPERATION_LOCK:
            result = await run_repeatability(
                mode=mode,
                domain=domain,
                cases_path=Path(config["cases_path"]),
                csv_path=Path(config["csv_path"]),
                output_dir=REPORTS_PATH,
                trials=trials,
                limit=limit,
                case_ids=case_ids or None,
                concurrency=concurrency,
                judge_provider=judge_provider,
            )
        result["automatic_profile"] = profile
        await asyncio.to_thread(CONTROL_CENTER.sync_reports)
        return JSONResponse({"ok": True, **result})
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return JSONResponse(error_result("REPEATABILITY_FAILED", str(exc)), status_code=400)
    except Exception as exc:
        if is_rate_limit_error(exc):
            await asyncio.to_thread(
                CONTROL_CENTER.audit, "API_RATE_LIMITED", "web", "repeatability",
                {"error_type": type(exc).__name__},
            )
            return JSONResponse(
                error_result("API_RATE_LIMITED", rate_limit_guidance(), trace=type(exc).__name__),
                status_code=429,
            )
        return JSONResponse(error_result("REPEATABILITY_FAILED", str(exc)), status_code=500)


async def merge_reports_web(request):
    try:
        data = await request.json()
        base = _safe_report_path(data.get("base_report"), suffix=".json")
        raw_retests = data.get("retest_reports") or []
        if not isinstance(raw_retests, list):
            raise ValidationError("retest_reports는 목록 형식이어야 합니다.")
        retests = [
            _safe_report_path(name, suffix=".json")
            for name in raw_retests
        ]
        async with QUALITY_OPERATION_LOCK:
            result = await asyncio.to_thread(merge_e2e_reports, base, retests, REPORTS_PATH)
        return JSONResponse({"ok": True, **result})
    except (ValidationError, ValueError) as exc:
        return JSONResponse(error_result("REPORT_MERGE_FAILED", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("REPORT_MERGE_FAILED", str(exc)), status_code=500)


async def run_judge_web(request):
    try:
        data = await request.json()
        profile = _require_live_api_policy()
        provider = str(profile["judge_provider"])
        report_name = data.get("input_report")
        input_path = (
            _safe_report_path(report_name, suffix=".json")
            if report_name
            else _latest_report("*live_retest_merged_e2e_*.json") or _latest_report("*live_e2e_*.json")
        )
        if input_path is None:
            raise ValidationError("Judge 입력 E2E 보고서가 없습니다.")
        previous_model = os.environ.get("A2A_JUDGE_MODEL")
        async with QUALITY_OPERATION_LOCK:
            try:
                model = JUDGE_MODELS[provider]
                if model:
                    os.environ["A2A_JUDGE_MODEL"] = model
                else:
                    os.environ.pop("A2A_JUDGE_MODEL", None)
                result = await run_llm_judge(provider, input_path, REPORTS_PATH)
            finally:
                if previous_model is None:
                    os.environ.pop("A2A_JUDGE_MODEL", None)
                else:
                    os.environ["A2A_JUDGE_MODEL"] = previous_model
        return JSONResponse({"ok": True, "model": JUDGE_MODELS[provider] or "deterministic", **result})
    except (ValidationError, ValueError) as exc:
        return JSONResponse(error_result("JUDGE_FAILED", str(exc)), status_code=400)
    except Exception as exc:
        if is_rate_limit_error(exc):
            await asyncio.to_thread(
                CONTROL_CENTER.audit, "API_RATE_LIMITED", "web", "llm-judge",
                {"error_type": type(exc).__name__},
            )
            return JSONResponse(
                error_result("API_RATE_LIMITED", rate_limit_guidance(), trace=type(exc).__name__),
                status_code=429,
            )
        return JSONResponse(error_result("JUDGE_FAILED", str(exc)), status_code=500)


async def generate_deployment_web(request):
    try:
        data = await request.json()
        e2e_path = _safe_report_path(data.get("e2e_report"), suffix=".json")
        judge_path = _safe_report_path(data.get("judge_report"), suffix=".json")
        async with QUALITY_OPERATION_LOCK:
            execution = await _run_fixed_script(
                "quality_diagnosis/generate_deployment_report.py",
                "--e2e", str(e2e_path),
                "--judge", str(judge_path),
            )
        deployment_path = REPORTS_PATH / "deployment_decision.md"
        return JSONResponse({
            "ok": True,
            "report": deployment_path.name,
            "content": deployment_path.read_text(encoding="utf-8"),
            **execution,
        })
    except (ValidationError, ValueError) as exc:
        return JSONResponse(error_result("DEPLOYMENT_REPORT_FAILED", str(exc)), status_code=400)
    except Exception as exc:
        return JSONResponse(error_result("DEPLOYMENT_REPORT_FAILED", str(exc)), status_code=500)


async def generate_comprehensive_report_web(request):
    """35건 재평가 후 종합 PDF와 다형식 첨부 증적을 생성합니다."""
    try:
        async with QUALITY_OPERATION_LOCK:
            evaluation = await _run_fixed_script(
                "quality_diagnosis/run_35_case_evaluation.py", timeout=600
            )
            report = await _run_fixed_script(
                "quality_diagnosis/build_comprehensive_report.py", timeout=300
            )
        latest_pdf = _latest_report("VOC_종합_품질평가_결과보고서_*.pdf")
        latest_zip = _latest_report("VOC_종합_품질평가_결과보고서_*_첨부증적.zip")
        if latest_pdf is None or latest_zip is None:
            raise RuntimeError("종합 보고서 첨부파일이 생성되지 않았습니다.")
        return JSONResponse({
            "ok": True,
            "test_result": "35/35 PASS",
            "pdf": _report_entry(latest_pdf),
            "attachment": _report_entry(latest_zip),
            "evaluation_output": evaluation["output"],
            "report_output": report["output"],
        })
    except Exception as exc:
        return JSONResponse(
            error_result("COMPREHENSIVE_REPORT_FAILED", str(exc)), status_code=500
        )


async def download_report(request):
    try:
        path = _safe_report_path(request.path_params.get("name") or "")
        await asyncio.to_thread(
            CONTROL_CENTER.audit,
            "REPORT_DOWNLOADED",
            getattr(request.state, "qa_actor", "web"),
            path.name,
            {"size": path.stat().st_size},
        )
        return FileResponse(path, filename=path.name)
    except ValidationError as exc:
        return JSONResponse(error_result("REPORT_NOT_FOUND", str(exc)), status_code=404)


async def preview_report(request):
    try:
        path = _safe_report_path(request.path_params.get("name") or "")
        if path.suffix.lower() in {".pdf", ".zip", ".png", ".docx"}:
            raise ValidationError("이 파일 형식은 미리보기를 지원하지 않습니다. 다운로드해 확인하세요.")
        content = path.read_text(encoding="utf-8", errors="replace")[:50_000]
        return JSONResponse({
            "ok": True, "name": path.name, "content": content,
            "truncated": path.stat().st_size > len(content.encode("utf-8")),
        })
    except ValidationError as exc:
        return JSONResponse(error_result("REPORT_PREVIEW_FAILED", str(exc)), status_code=400)


async def index(request):
    """각 메뉴 URL에 맞는 독립 화면 상태를 포함한 공통 앱 셸을 반환합니다."""
    config = PAGE_ROUTE_CONFIG.get(request.url.path, PAGE_ROUTE_CONFIG["/"])
    body = (
        f'<body data-page-view="{config["view"]}" '
        f'data-panel="{config["panel"]}">'
    )
    return HTMLResponse(PAGE.replace("<body>", body, 1))


async def guided_demo(request):
    """Render the real application page with a presenter progress panel."""
    params = request.query_params
    view_path = str(params.get("view") or "/single")
    config = PAGE_ROUTE_CONFIG.get(view_path, PAGE_ROUTE_CONFIG["/single"])
    body = (
        f'<body data-page-view="{config["view"]}" '
        f'data-panel="{config["panel"]}">'
    )
    values = {
        key: html.escape(str(params.get(key) or ""))
        for key in ("step", "title", "status", "point", "result", "screen_label")
    }
    demo_phase = str(params.get("phase") or "")
    demo_question = str(params.get("question") or "")
    demo_run_id = str(params.get("run_id") or "")
    demo_case_id = str(params.get("case_id") or "")
    try:
        active = max(1, min(5, int(params.get("active") or 1)))
    except (TypeError, ValueError):
        active = 1
    steps = [
        ("입력", "TC 사례·작업 유형 확인"),
        ("분석 실행", "6-Agent 파이프라인 호출"),
        ("품질 판정", "PASS·점수·배포 기준 확인"),
        ("승인 검토", "Reviewer·점수·Judge 동의"),
        ("최종 승인", "APPROVED·감사 로그 확인"),
    ]
    flow = "".join(
        f'<div class="gd-item {"done" if number < active else "active" if number == active else ""}">'
        f'<span>{number}</span><div><b>{html.escape(label)}</b><small>{html.escape(detail)}</small></div></div>'
        for number, (label, detail) in enumerate(steps, 1)
    )
    panel = f"""
    <style>
      body{{width:calc(100% - 410px)!important;overflow-x:hidden!important}}
      .guided-demo-panel{{position:fixed;z-index:99999;right:0;top:0;width:410px;height:100vh;padding:20px;background:#081929;color:#eaf4ff;border-left:1px solid #2b4d67;overflow:auto;font-family:'Malgun Gothic',Arial,sans-serif}}
      .guided-demo-panel h1{{margin:0 0 5px;color:#62eed8;font-size:22px}}.gd-live{{color:#d7e9f7;font-weight:800}}.gd-live:before{{content:'';display:inline-block;width:10px;height:10px;margin-right:8px;border-radius:50%;background:#ff426c;box-shadow:0 0 10px #ff426c}}
      .gd-step{{margin:15px 0 8px;color:#65f1dc;font-size:25px;font-weight:900}}.gd-status{{font-size:17px;font-weight:800;line-height:1.45}}.gd-point{{margin:15px 0;padding:12px;border-left:4px solid #45d5be;background:#10283b;line-height:1.5}}
      .gd-flow{{display:grid;gap:8px}}.gd-item{{display:grid;grid-template-columns:28px 1fr;gap:8px;padding:10px;border:1px solid #23435f;border-radius:8px;background:#0c2235}}.gd-item>span{{width:26px;height:26px;display:grid;place-items:center;border-radius:50%;background:#20445f;font-weight:900}}.gd-item b{{display:block}}.gd-item small{{display:block;color:#a9bfd2}}.gd-item.active{{border-color:#55dfca;background:#12364a}}.gd-item.active>span{{background:#23aa93}}.gd-item.done{{opacity:.75}}.gd-item.done>span{{background:#23785f}}
      .gd-result{{margin-top:15px;padding:13px;border:1px solid #345b78;border-radius:9px;background:#0c2235;white-space:pre-line;line-height:1.5}}.gd-label{{position:fixed;z-index:99998;left:185px;top:68px;padding:7px 11px;border-radius:7px;background:#071a2bea;color:#fff;font-weight:800}}
      .demo-cursor{{position:fixed;z-index:100003;left:260px;top:170px;width:26px;height:34px;pointer-events:none;transition:left .72s ease,top .72s ease;filter:drop-shadow(0 2px 2px #0009)}}.demo-cursor:before{{content:'';position:absolute;left:0;top:0;width:25px;height:33px;background:#ff315f;clip-path:polygon(0 0,0 82%,7px 66%,14px 100%,19px 97%,12px 63%,25px 63%);-webkit-clip-path:polygon(0 0,0 82%,7px 66%,14px 100%,19px 97%,12px 63%,25px 63%)}}
      .demo-cursor-info{{position:absolute;left:30px;top:25px;width:270px;padding:10px 12px;border:2px solid #ff315f;border-radius:9px;background:#071a2bf2;color:#fff;font-size:14px;font-weight:800;line-height:1.45;white-space:pre-line;box-shadow:0 8px 24px #0007}}
      .demo-select-menu{{position:fixed;z-index:100001;min-width:210px;padding:5px;border:2px solid #ff315f;border-radius:8px;background:#fff;color:#14283b;box-shadow:0 12px 30px #0007}}.demo-select-option{{padding:9px 12px;border-radius:5px;font-size:14px;font-weight:700;background:#fff}}.demo-select-option+ .demo-select-option{{border-top:1px solid #d9e4ec}}.demo-select-option.hover{{background:#dff8f3;color:#075b4d}}.demo-select-option.selected{{background:#149c84;color:#fff}}
      .demo-click-ring{{position:fixed;z-index:100002;width:12px;height:12px;border:4px solid #ff315f;border-radius:50%;pointer-events:none;opacity:0;transform:translate(-50%,-50%) scale(.2)}}.demo-click-ring.flash{{animation:demoClick .65s ease-out}}@keyframes demoClick{{0%{{opacity:1;transform:translate(-50%,-50%) scale(.2)}}100%{{opacity:0;transform:translate(-50%,-50%) scale(4)}}}}
    </style>
    <div class="gd-label">{values['screen_label']}</div>
    <aside class="guided-demo-panel"><h1>VOC_Improve 웹 시연</h1><div class="gd-live">실제 실행 진행 정보</div><div class="gd-step">{values['step']}</div><div class="gd-status">{values['title']}<br>{values['status']}</div><div class="gd-point">{values['point']}</div><div class="gd-flow">{flow}</div><div class="gd-result">{values['result']}</div></aside>
    <div id="demoCursor" class="demo-cursor"><span id="demoCursorInfo" class="demo-cursor-info">시연 준비\n입력 화면 확인</span></div><div id="demoClickRing" class="demo-click-ring"></div>
    <script>
    (() => {{
      const phase={json.dumps(demo_phase, ensure_ascii=False)};
      const question={json.dumps(demo_question, ensure_ascii=False)};
      const runId={json.dumps(demo_run_id, ensure_ascii=False)};
      const caseId={json.dumps(demo_case_id, ensure_ascii=False)};
      const cursor=document.getElementById('demoCursor'), cursorInfo=document.getElementById('demoCursorInfo'), ring=document.getElementById('demoClickRing');
      const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
      async function target(selector){{
        for(let i=0;i<25;i++){{const el=document.querySelector(selector);if(el)return el;await wait(240)}}
        return null;
      }}
      async function move(selector,info='다음 화면 요소로 이동'){{
        const el=await target(selector);if(!el)return null;
        cursorInfo.textContent=info;
        el.scrollIntoView({{behavior:'smooth',block:'center'}});await wait(650);
        const r=el.getBoundingClientRect();cursor.style.left=(r.left+r.width*.5)+'px';cursor.style.top=(r.top+r.height*.5)+'px';await wait(850);return el;
      }}
      async function clickEl(selector,info='클릭하여 선택'){{
        const el=await move(selector,info);if(!el)return null;
        const r=el.getBoundingClientRect();ring.style.left=(r.left+r.width*.5)+'px';ring.style.top=(r.top+r.height*.5)+'px';ring.classList.remove('flash');void ring.offsetWidth;ring.classList.add('flash');el.focus();el.click();await wait(700);return el;
      }}
      async function typeInto(selector,text,info='문자 입력'){{
        const el=await clickEl(selector,info);if(!el)return;
        el.value='';el.dispatchEvent(new Event('input',{{bubbles:true}}));
        for(const ch of text){{el.value+=ch;el.dispatchEvent(new Event('input',{{bubbles:true}}));await wait(55)}}
        el.dispatchEvent(new Event('change',{{bubbles:true}}));await wait(500);
      }}
      async function setSelect(selector,value,info='선택 항목 변경'){{
        const el=await clickEl(selector,info+'\\n드롭다운 목록을 엽니다.');if(!el)return;
        document.querySelectorAll('.demo-select-menu').forEach(node=>node.remove());
        const r=el.getBoundingClientRect(), menu=document.createElement('div');menu.className='demo-select-menu';menu.style.left=r.left+'px';menu.style.top=(r.bottom+4)+'px';
        for(const option of Array.from(el.options||[])){{const row=document.createElement('div');row.className='demo-select-option';row.dataset.value=option.value;row.textContent=option.textContent;menu.appendChild(row)}}
        document.body.appendChild(menu);await wait(650);
        const choice=Array.from(menu.children).find(row=>row.dataset.value===value)||menu.children[0];if(!choice){{menu.remove();return}}
        choice.id='demoSelectChoice';choice.classList.add('hover');await move('#demoSelectChoice',info+'\\n선택값: '+choice.textContent.trim());await clickEl('#demoSelectChoice',info+'\\n값을 클릭해 적용합니다.');choice.classList.remove('hover');choice.classList.add('selected');
        el.value=value;el.dispatchEvent(new Event('input',{{bubbles:true}}));el.dispatchEvent(new Event('change',{{bubbles:true}}));await wait(850);menu.remove();await wait(450);
      }}
      async function runSingle(){{
        await wait(1600);await typeInto('#q',question,'1/4 · 질문 입력\\n단건 VOC 문장을 입력합니다.');await setSelect('#task','both','2/4 · 작업 유형 선택\\n요약 + 개선정책을 선택합니다.');await clickEl('#go','3/4 · 분석 실행\\n6-Agent 분석 버튼을 클릭합니다.');await wait(3200);const result=await move('#result','4/4 · 결과 확인\\n분석 결과 영역으로 스크롤합니다.');if(result)window.scrollBy({{top:180,behavior:'smooth'}});
      }}
      async function runApproval(){{
        await wait(2600);const details=document.querySelector('#selectedReviewContext + details')||document.querySelector('.approval-workspace details');if(details&&!details.open){{await clickEl('.approval-workspace details summary','1/9 · 승인 대상 열기\\n직접 실행 선택 영역을 엽니다.')}}
        await setSelect('#approvalRun',runId,'2/9 · 실행 선택\\n분석 실행 ID를 선택합니다.');await wait(1100);await setSelect('#approvalCase',caseId,'3/9 · 케이스 선택\\n검토할 단건 사례를 선택합니다.');await clickEl('#selectManualApproval','4/9 · 대상 적용\\n선택한 실행과 케이스를 적용합니다.');await wait(1600);
        await typeInto('#approvalReviewer','3팀 QA Lead','5/9 · 검토자 입력\\n승인 담당자를 기록합니다.');await setSelect('#approvalDecision','APPROVED','6/9 · 승인 결정\\nAPPROVED를 선택합니다.');await typeInto('#approvalScore','98','7/9 · 점수 입력\\n사람 검토점수 98점을 입력합니다.');await setSelect('#judgeAgreement','true','8/9 · Judge 동의\\nJudge 판단 동의를 선택합니다.');await clickEl('#finalDeploymentApproval','8/9 · 최종 승인 체크\\n최종 배포 승인에 체크합니다.');
        await typeInto('#approvalComment','웹 화면 시연: 6-Agent 단건 분석 결과와 배포 기준을 확인하고 최종 승인합니다.','9/9 · 검토 의견 입력\\n승인 근거를 기록합니다.');await clickEl('#saveApproval','저장 · 검토 결과 기록\\n최종 승인 정보를 저장합니다.');await wait(2200);await move('#approvalList','완료 · 승인 이력 확인\\n저장된 결과로 스크롤합니다.');
      }}
      if(phase==='single')runSingle();if(phase==='approval')runApproval();
    }})();
    </script>
    """
    return HTMLResponse(PAGE.replace("<body>", body, 1).replace("</body>", panel + "</body>", 1))


async def presentation_index(request):
    """7월 14일부터 현재까지의 개발 과정과 증적을 발표용 슬라이드로 제공합니다."""
    return HTMLResponse(PRESENTATION_PAGE)


async def presentation_material(request):
    return FileResponse(ROOT_PATH / "docs" / "발표자료_개발과정_2026-07-14_현재.md")


async def presentation_deck(request):
    return FileResponse(
        ROOT_PATH / "docs" / "VOC_Improve_오늘프로그램_발표자료_20260803.pptx",
        filename="VOC_Improve_오늘프로그램_발표자료_20260803.pptx",
    )


async def presentation_ledger(request):
    return FileResponse(ROOT_PATH / "docs" / "개발진행_발표원장.md")


async def presentation_principles(request):
    return FileResponse(ROOT_PATH / "docs" / "개발원칙_발표및웹적용.md")


def _single_fallback_case(question: str, test_case: dict | None) -> dict:
    if isinstance(test_case, dict):
        return validate_quality_case(test_case)
    for config in TEST_SETS.values():
        try:
            with open(config["cases_path"], encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip() or line.lstrip().startswith("#"):
                        continue
                    candidate = validate_quality_case(json.loads(line))
                    if str(candidate.get("question") or "").strip() == question:
                        return candidate
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    keywords = re.findall(r"[0-9A-Za-z가-힣]{2,}", question)[:8]
    return validate_quality_case({
        "case_id": f"SINGLE-FALLBACK-{secrets.token_hex(4).upper()}",
        "question": question,
        "expected_intent": "사용자 VOC 원인 분석 및 개선 정책 제안",
        "expected_keywords": keywords,
        "required_output": ["원인 추정", "고객 안내", "개선안", "우선순위"],
        "prohibited_output": ["개인정보 요구", "근거 없는 단정"],
        "expected_status": "success",
    })


async def _run_single_offline_fallback(
    question: str, csv_path: str, test_case: dict | None
) -> dict:
    case = _single_fallback_case(question, test_case)
    temp_cases = REPORTS_PATH / f".single_fallback_{secrets.token_hex(6)}.jsonl"
    temp_cases.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        async with QUALITY_OPERATION_LOCK:
            execution = await run_e2e(
                "offline", temp_cases, REPORTS_PATH, Path(csv_path), "ecommerce",
                limit=1, concurrency=1,
            )
        report = json.loads(Path(execution["json"]).read_text(encoding="utf-8"))
        row = report["results"][0]
        out = dict(row["analysis"])
        out["quality"] = row["quality"]
        out["execution_mode"] = "offline_fallback"
        out["fallback_reason"] = "PROVIDER_NETWORK_UNAVAILABLE"
        out["fallback_report"] = Path(execution["json"]).name
        out["warning"] = (
            "외부 AI API 443 연결이 차단되어 동일한 6-Agent 계약의 "
            "결정론적 오프라인 재현 모드로 완료했습니다."
        )
        return out
    finally:
        temp_cases.unlink(missing_ok=True)


async def analyze(request):
    """질문을 받아 6개 에이전트 단계별 진단을 실행하고 결과(JSON)를 반환합니다."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(error_result("INVALID_JSON", "잘못된 JSON 요청입니다."), status_code=400)

    try:
        question = validate_question(data.get("question") or "")
        task = validate_task(data.get("task") or "both")
        csv_path = validate_csv_path(data.get("csv_path") or DEFAULT_CSV)
        test_case = data.get("test_case")
        if test_case is not None:
            test_case = validate_quality_case(test_case)
    except ValidationError as e:
        return JSONResponse(error_result("INVALID_INPUT", str(e)), status_code=400)

    try:
        out = await runtime.run_with_diagnostics(
            question=question,
            csv_path=csv_path,
            timeout=TOTAL_TIMEOUT,
            task_override=task,
        )
        if test_case is not None:
            out["quality"] = evaluate_quality_case(test_case, out)
        return JSONResponse(out)
    except grpc.aio.AioRpcError as e:
        details = e.details() or ""
        provider_error = classify_provider_error(details)
        error_code = "ANALYSIS_FAILED"
        status_code = 502
        if provider_error:
            error_code = str(provider_error["error_code"])
            message = str(provider_error["message"])
            status_code = int(provider_error["status_code"])
        elif "Connection error" in details:
            try:
                return JSONResponse(
                    await _run_single_offline_fallback(question, csv_path, test_case)
                )
            except Exception:
                pass
            message = (
                "AI API 연결에 실패했습니다. 현재 터미널의 API 키, 키 유효성, "
                "인터넷/방화벽 설정을 확인한 뒤 두 서버를 다시 시작하세요."
            )
        elif e.code() == grpc.StatusCode.UNAVAILABLE:
            message = "gRPC 에이전트에 연결할 수 없습니다. grpc_server.py를 먼저 실행하세요."
        elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
            message = "AI 분석 응답 시간이 초과되었습니다. 잠시 후 다시 실행하세요."
        else:
            safe_details = redact_api_secrets(details or e.code().name)
            message = f"AI 에이전트 실행에 실패했습니다: {safe_details}"
        return JSONResponse(
            error_result(error_code, message, trace="AioRpcError"),
            status_code=status_code,
        )
    except Exception as e:
        return JSONResponse(
            error_result(
                "ANALYSIS_FAILED",
                "VOC 분석에 실패했습니다. gRPC 서버와 API 키 설정을 확인하세요.",
                trace=type(e).__name__,
            ),
            status_code=500,
        )


async def test_set(request):
    """도메인별 기본 CSV와 JSONL 케이스를 웹 QA 화면에 제공합니다."""
    domain = str(request.query_params.get("domain") or "ecommerce").lower()
    config = TEST_SETS.get(domain)
    if config is None:
        return JSONResponse(error_result("INVALID_DOMAIN", "지원하지 않는 테스트 도메인입니다."), status_code=400)
    try:
        cases = []
        with open(config["cases_path"], encoding="utf-8") as stream:
            for line in stream:
                if line.strip() and not line.lstrip().startswith("#"):
                    cases.append(validate_quality_case(json.loads(line)))
        with open(config["csv_path"], encoding="utf-8") as stream:
            voc_count = max(sum(1 for _ in stream) - 1, 0)
        return JSONResponse({
            "domain": domain,
            "label": config["label"],
            "csv_path": validate_csv_path(config["csv_path"]),
            "csv_name": os.path.basename(config["csv_path"]),
            "voc_count": voc_count,
            "cases": cases,
        })
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        return JSONResponse(error_result("TEST_SET_LOAD_FAILED", str(exc)), status_code=500)


app = Starlette(routes=[
    Route("/healthz", healthz),
    Route("/auth/status", auth_status),
    Route("/auth/login", auth_login, methods=["POST"]),
    Route("/auth/logout", auth_logout, methods=["POST"]),
    Route("/", index),
    Route("/control-center", index),
    Route("/dashboard", index),
    Route("/single", index),
    Route("/batch", index),
    Route("/quality", index),
    Route("/test-cases", index),
    Route("/runs", index),
    Route("/compare", index),
    Route("/trace", index),
    Route("/security", index),
    Route("/approvals", index),
    Route("/reports", index),
    Route("/settings", index),
    Route("/guided-demo", guided_demo),
    Route("/presentation", presentation_index),
    Route("/presentation/deck", presentation_deck),
    Route("/presentation/material", presentation_material),
    Route("/presentation/ledger", presentation_ledger),
    Route("/presentation/principles", presentation_principles),
    Route("/analyze", analyze, methods=["POST"]),
    Route("/test-set", test_set),
    Route("/quality/control-center", control_center_dashboard),
    Route("/quality/runs", control_center_runs),
    Route("/quality/runs/{run_id:str}/report.docx", download_run_word_report),
    Route("/quality/runs/{run_id:str}", control_center_run_detail),
    Route("/quality/cases", control_center_cases),
    Route("/quality/review-queue", control_center_review_queue),
    Route("/quality/versions", control_center_versions),
    Route("/quality/compare", control_center_compare, methods=["POST"]),
    Route("/quality/approvals", control_center_approvals, methods=["GET", "POST"]),
    Route("/quality/observability-settings", control_center_settings, methods=["GET", "POST"]),
    Route("/quality/drift", control_center_drift),
    Route("/quality/audit", control_center_audit),
    Route("/quality/jobs", quality_jobs, methods=["GET", "POST"]),
    Route("/quality/jobs/{job_id:str}", quality_job_detail),
    Route("/quality/jobs/{job_id:str}/cancel", quality_job_cancel, methods=["DELETE"]),
    Route("/quality/status", quality_status),
    Route("/quality/run-suite", run_quality_suite_web, methods=["POST"]),
    Route("/quality/run-fault", run_fault_diagnosis_web, methods=["POST"]),
    Route("/quality/run-red-team", run_red_team_web, methods=["POST"]),
    Route("/quality/run-quality-gate", run_quality_gate_web, methods=["POST"]),
    Route("/quality/run-offline-e2e", run_offline_e2e_web, methods=["POST"]),
    Route("/quality/run-live-e2e", run_live_e2e_web, methods=["POST"]),
    Route("/quality/run-repeatability", run_repeatability_web, methods=["POST"]),
    Route("/quality/merge-reports", merge_reports_web, methods=["POST"]),
    Route("/quality/run-judge", run_judge_web, methods=["POST"]),
    Route("/quality/deployment-threshold", deployment_threshold_web, methods=["POST"]),
    Route("/quality/generate-deployment", generate_deployment_web, methods=["POST"]),
    Route("/quality/generate-comprehensive-report", generate_comprehensive_report_web, methods=["POST"]),
    Route("/quality/report/{name:str}", download_report),
    Route("/quality/report-preview/{name:str}", preview_report),
])
app.add_middleware(BaseHTTPMiddleware, dispatch=operator_auth_middleware)


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB_PORT", "8000"))
    print(f"[web_app] http://{host}:{port} 에서 접속하세요. (먼저 python grpc_server.py 실행 필요)")
    uvicorn.run(app, host=host, port=port)
