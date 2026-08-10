import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from core.paths import K6_RUNS_DIR, PROJECT_DIR


@dataclass
class K6RunSettings:
    target_url: str
    vus: int = 10
    duration_seconds: int = 60
    ramp_up_seconds: int = 10
    p95_threshold_ms: int = 3000
    failure_rate_threshold_pct: float = 1.0
    checks_threshold_pct: float = 95.0
    think_time_seconds: float = 1.0


def get_k6_executable():
    return shutil.which("k6")


def get_k6_version():
    executable = get_k6_executable()
    if not executable:
        return ""

    try:
        completed = subprocess.run(
            [executable, "version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""

    return (completed.stdout or completed.stderr or "").strip()


def is_k6_available():
    return bool(get_k6_executable())


def run_k6_test(settings):
    validate_settings(settings)
    executable = get_k6_executable()
    if not executable:
        return {
            "ok": False,
            "error": "k6 실행 파일을 찾을 수 없습니다. k6를 설치한 뒤 다시 실행해주세요.",
            "settings": asdict(settings),
        }

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = K6_RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    script_path = run_dir / "script.js"
    summary_path = run_dir / "summary.json"
    record_path = run_dir / "run_record.json"
    script_path.write_text(build_k6_script(settings), encoding="utf-8")

    timeout_seconds = max(settings.duration_seconds + settings.ramp_up_seconds + 90, 120)
    command = [
        executable,
        "run",
        "--summary-export",
        str(summary_path),
        str(script_path),
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        record = build_run_record(
            run_id,
            settings,
            summary_path,
            script_path,
            return_code=-1,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + "\nk6 실행 시간이 초과되었습니다.",
        )
        write_json(record_path, record)
        return {**record, "ok": False, "error": "k6 실행 시간이 초과되었습니다."}
    except OSError as exc:
        record = build_run_record(
            run_id,
            settings,
            summary_path,
            script_path,
            return_code=-1,
            stdout="",
            stderr=str(exc),
        )
        write_json(record_path, record)
        return {**record, "ok": False, "error": str(exc)}

    raw_summary = load_json(summary_path)
    normalized = normalize_k6_summary(raw_summary)
    record = build_run_record(
        run_id,
        settings,
        summary_path,
        script_path,
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        normalized=normalized,
        raw_summary=raw_summary,
    )
    write_json(record_path, record)
    save_latest_summary(raw_summary, record)

    return {
        **record,
        "ok": completed.returncode == 0,
        "error": "" if completed.returncode == 0 else "k6 실행이 실패했습니다. 로그를 확인해주세요.",
    }


def validate_settings(settings):
    if not settings.target_url:
        raise ValueError("대상 URL을 입력해주세요.")
    if not settings.target_url.startswith(("http://", "https://")):
        raise ValueError("대상 URL은 http:// 또는 https://로 시작해야 합니다.")
    if settings.vus < 1:
        raise ValueError("동시 사용자는 1 이상이어야 합니다.")
    if settings.duration_seconds < 1:
        raise ValueError("테스트 시간은 1초 이상이어야 합니다.")


def build_k6_script(settings):
    stable_duration = max(settings.duration_seconds - settings.ramp_up_seconds, 1)
    if settings.ramp_up_seconds > 0:
        executor_options = f"""
  stages: [
    {{ duration: '{settings.ramp_up_seconds}s', target: {settings.vus} }},
    {{ duration: '{stable_duration}s', target: {settings.vus} }},
    {{ duration: '5s', target: 0 }},
  ],"""
    else:
        executor_options = f"""
  vus: {settings.vus},
  duration: '{settings.duration_seconds}s',"""

    target_url = json.dumps(settings.target_url)
    think_time = json.dumps(float(settings.think_time_seconds))
    failure_rate = settings.failure_rate_threshold_pct / 100
    checks_rate = settings.checks_threshold_pct / 100

    return f"""import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{{executor_options}
  thresholds: {{
    http_req_duration: ['p(95)<{settings.p95_threshold_ms}'],
    http_req_failed: ['rate<{failure_rate:.4f}'],
    checks: ['rate>{checks_rate:.4f}'],
  }},
}};

const TARGET_URL = {target_url};

export default function () {{
  const res = http.get(TARGET_URL);
  check(res, {{
    'status is 2xx or 3xx': (r) => r.status >= 200 && r.status < 400,
    'body returned': (r) => r.body !== null && r.body.length >= 0,
  }});
  sleep({think_time});
}}
"""


def build_run_record(
    run_id,
    settings,
    summary_path,
    script_path,
    return_code,
    stdout,
    stderr,
    normalized=None,
    raw_summary=None,
):
    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "settings": asdict(settings),
        "return_code": return_code,
        "summary_path": str(summary_path),
        "script_path": str(script_path),
        "stdout": stdout[-4000:] if stdout else "",
        "stderr": stderr[-4000:] if stderr else "",
        "summary": normalized or {},
        "raw_summary": raw_summary or {},
    }


def save_latest_summary(raw_summary, record):
    latest_path = PROJECT_DIR / "reports" / "k6_summary.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = raw_summary if raw_summary else {}
    if isinstance(payload, dict):
        payload = {
            **payload,
            "run_id": record["run_id"],
            "created_at": record["created_at"],
            "settings": record["settings"],
            "normalized": record["summary"],
        }
    write_json(latest_path, payload)


def load_recent_runs(limit=10):
    if not K6_RUNS_DIR.exists():
        return []

    records = []
    for record_path in sorted(K6_RUNS_DIR.glob("*/run_record.json"), reverse=True):
        record = load_json(record_path)
        if record:
            records.append(record)
        if len(records) >= limit:
            break
    return records


def normalize_k6_summary(summary):
    metrics = summary.get("metrics", {}) if isinstance(summary, dict) else {}
    return {
        "total_requests": metric_value(metrics, "http_reqs", "count"),
        "failure_rate": metric_value(metrics, "http_req_failed", "rate") * 100,
        "avg_duration_seconds": metric_value(metrics, "http_req_duration", "avg") / 1000,
        "p95_duration_seconds": metric_value(metrics, "http_req_duration", "p(95)") / 1000,
        "p90_duration_seconds": metric_value(metrics, "http_req_duration", "p(90)") / 1000,
        "p99_duration_seconds": metric_value(metrics, "http_req_duration", "p(99)") / 1000,
        "throughput": metric_value(metrics, "http_reqs", "rate"),
        "checks_rate": metric_value(metrics, "checks", "rate") * 100,
        "vus": metric_value(metrics, "vus_max", "value") or metric_value(metrics, "vus", "value"),
    }


def metric_value(metrics, metric_name, key):
    metric = metrics.get(metric_name, {})
    if not isinstance(metric, dict):
        return 0
    if key == "rate" and metric_name == "checks":
        passes = metric.get("passes")
        fails = metric.get("fails")
        if passes is not None and fails is not None:
            total = float(passes or 0) + float(fails or 0)
            return float(passes or 0) / total if total else 0
        if "value" in metric:
            return float(metric.get("value", 0) or 0)
    try:
        return float(metric.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def load_json(path):
    try:
        path = Path(path)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
