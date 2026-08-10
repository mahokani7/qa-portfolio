"""
ops_snapshot.py
------------------------------------------------------------------------------
운영 모니터링(Prometheus)·k6 성능 지표를 '보고서 부록'에 넣기 위해, Prometheus HTTP API를
직접 조회해 matplotlib 차트(PNG)로 렌더링한다. (Grafana 이미지 렌더러 의존성 없이 동작)

생성 차트(스냅샷):
  1) 운영 대시보드 (요청률 / 오류율 / p95 응답시간)
  2) 트래픽 & 오류 (초당 요청률 by agent_type / 성공·오류 누적)
  3) 응답시간 분포 (p50 / p95 / p99)
  4) k6 성능 테스트 결과 (총 요청 / VUs / p95 / 오류율)

Prometheus가 꺼져 있거나 데이터가 없으면 해당 차트는 None을 반환하고, 보고서는 '데이터 없음'으로 처리한다.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm

# 한글 폰트 설정 (맑은 고딕 우선). 없으면 기본 폰트로 두되 한글이 네모(□)로 나올 수 있음.
_KOREAN_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]
_KOREAN_FONT_PATH = next((p for p in _KOREAN_FONT_CANDIDATES if Path(p).exists()), None)
if _KOREAN_FONT_PATH:
    fm.fontManager.addfont(_KOREAN_FONT_PATH)
    plt.rcParams["font.family"] = fm.FontProperties(fname=_KOREAN_FONT_PATH).get_name()
plt.rcParams["axes.unicode_minus"] = False

PROM_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("GRAFANA_BASE_URL", "http://localhost:3000")


def fetch_alert_states() -> List[dict]:
    """
    Grafana Alerting API에서 알림 규칙의 현재 상태(Normal/Pending/Firing)를 가져온다.
    대시보드 '🚨 실시간 알림 상태(Golden Signals)' 카드와 동일한 데이터를 부록에 담기 위함.
    Grafana 미실행/오류 시 빈 리스트를 반환한다. (admin:admin 기본 계정)
    """
    url = f"{GRAFANA_URL}/api/prometheus/grafana/api/v1/rules"
    req = urllib.request.Request(url, headers={"Authorization": "Basic YWRtaW46YWRtaW4="})  # admin:admin
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    rules = []
    for g in data.get("data", {}).get("groups", []):
        for r in g.get("rules", []):
            name = r.get("name", "?")
            short = name.split("—")[0].strip()
            if "]" in short:
                short = short.split("]", 1)[-1].strip()
            rules.append({
                "name": short or name,
                "state": r.get("state", "unknown"),
                "severity": (r.get("labels", {}) or {}).get("severity", "-"),
            })
    return rules


# ---------------------------------------------------------------------------
# Prometheus 조회
# ---------------------------------------------------------------------------
def _query_range(expr: str, minutes: int = 30, step: int = 15) -> List[dict]:
    """query_range 결과(list of {metric, values})를 반환. 실패 시 빈 리스트."""
    end = time.time()
    start = end - minutes * 60
    params = urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": step})
    url = f"{PROM_URL}/api/v1/query_range?{params}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            d = json.loads(r.read().decode("utf-8"))
        return d.get("data", {}).get("result", [])
    except Exception:
        return []


def _query_instant(expr: str):
    """instant query 스칼라 값(float) 또는 None."""
    params = urllib.parse.urlencode({"query": expr})
    url = f"{PROM_URL}/api/v1/query?{params}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            d = json.loads(r.read().decode("utf-8"))
        res = d.get("data", {}).get("result", [])
        if res:
            val = float(res[0]["value"][1])
            # Prometheus는 데이터가 없으면 "NaN"을 반환 → 보고서에 'nan'이 찍히지 않도록 None 처리
            if val != val:  # NaN 판별
                return None
            return val
    except Exception:
        pass
    return None


def prometheus_available() -> bool:
    try:
        with urllib.request.urlopen(f"{PROM_URL}/-/ready", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _series_xy(result_item: dict):
    xs = [datetime.fromtimestamp(float(ts)) for ts, _ in result_item["values"]]
    ys = [float(v) for _, v in result_item["values"]]
    return xs, ys


def _has_any(results: List[dict]) -> bool:
    return any(item.get("values") for item in results)


def _style_time_axis(ax):
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.grid(True, alpha=0.25)


# ---------------------------------------------------------------------------
# 차트 생성 (각 함수는 PNG 경로를 반환, 데이터 없으면 None)
# ---------------------------------------------------------------------------
def chart_golden_signals(out_dir: Path, minutes: int = 30) -> Optional[Path]:
    """요청률 / 오류율 / p95 응답시간 3분할."""
    req = _query_range("sum(rate(ask_requests_total[1m]))", minutes)
    # 오류가 한 건도 없으면 분자 시리즈가 비어 그래프가 'No data'가 되므로 or vector(0)으로 0%를 명시한다.
    err = _query_range(
        '100 * (sum(rate(ask_requests_total{status="error"}[5m])) or vector(0)) / clamp_min(sum(rate(ask_requests_total[5m])), 0.001)',
        minutes)
    p95 = _query_range(
        "1000 * histogram_quantile(0.95, sum(rate(ask_request_latency_seconds_bucket[5m])) by (le))", minutes)
    if not (_has_any(req) or _has_any(err) or _has_any(p95)):
        return None

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.2))
    for ax, data, title, color, unit in [
        (axes[0], req, "요청률 (req/s)", "#2563EB", ""),
        (axes[1], err, "오류율 (%)", "#EF4444", "%"),
        (axes[2], p95, "p95 응답시간 (ms)", "#F59E0B", "ms"),
    ]:
        if _has_any(data):
            xs, ys = _series_xy(data[0])
            ax.plot(xs, ys, color=color, linewidth=1.8)
            ax.fill_between(xs, ys, color=color, alpha=0.12)
            if unit == "%":  # 오류율: 0% 라인이 바닥에 보기 좋게 놓이도록 y축 하한 0 고정
                ax.set_ylim(0, max(5, max(ys) * 1.3))
        else:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color="#94a3b8")
        ax.set_title(title, fontsize=10)
        _style_time_axis(ax)
    fig.suptitle("운영 대시보드 — 요청/오류율/응답시간", fontsize=12, y=1.02)
    fig.tight_layout()
    path = out_dir / "ops_golden.png"
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_traffic_errors(out_dir: Path, minutes: int = 30) -> Optional[Path]:
    """초당 요청률(agent_type별) + 성공/오류 누적 카운트."""
    rate_by_agent = _query_range("sum(rate(ask_requests_total[1m])) by (agent_type)", minutes)
    cum_by_status = _query_range("sum(ask_requests_total) by (status)", minutes)
    if not (_has_any(rate_by_agent) or _has_any(cum_by_status)):
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.4))
    colors = {"rule_based": "#2563EB", "api_based": "#93C5FD"}
    if _has_any(rate_by_agent):
        for item in rate_by_agent:
            agent = item["metric"].get("agent_type", "?")
            xs, ys = _series_xy(item)
            ax1.plot(xs, ys, label=agent, linewidth=1.8, color=colors.get(agent))
        ax1.legend(fontsize=8)
    else:
        ax1.text(0.5, 0.5, "No data", ha="center", va="center", color="#94a3b8")
    ax1.set_title("초당 요청률 — agent_type별", fontsize=10)
    _style_time_axis(ax1)

    scolor = {"success": "#10B981", "error": "#EF4444"}
    if _has_any(cum_by_status):
        for item in cum_by_status:
            status = item["metric"].get("status", "?")
            xs, ys = _series_xy(item)
            ax2.plot(xs, ys, label=status, linewidth=1.8, color=scolor.get(status))
        ax2.legend(fontsize=8)
    else:
        ax2.text(0.5, 0.5, "No data", ha="center", va="center", color="#94a3b8")
    ax2.set_title("성공 vs 오류 요청 (누적)", fontsize=10)
    _style_time_axis(ax2)

    fig.suptitle("트래픽 & 오류 (Rate / Errors)", fontsize=12, y=1.03)
    fig.tight_layout()
    path = out_dir / "ops_traffic.png"
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_duration(out_dir: Path, minutes: int = 30) -> Optional[Path]:
    """응답시간 분포 p50 / p95 / p99 (ms)."""
    series = {}
    for q, name, color in [
        (0.50, "p50", "#10B981"),
        (0.95, "p95", "#F59E0B"),
        (0.99, "p99", "#EF4444"),
    ]:
        series[name] = (
            _query_range(f"1000 * histogram_quantile({q}, sum(rate(ask_request_latency_seconds_bucket[5m])) by (le))", minutes),
            color,
        )
    if not any(_has_any(data) for data, _ in series.values()):
        return None

    fig, ax = plt.subplots(figsize=(11, 3.4))
    plotted = False
    for name, (data, color) in series.items():
        if _has_any(data):
            xs, ys = _series_xy(data[0])
            ax.plot(xs, ys, label=name, linewidth=1.8, color=color)
            plotted = True
    if plotted:
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", color="#94a3b8")
    ax.set_title("응답시간 분포 (Duration) — p50 / p95 / p99 (ms)", fontsize=11)
    ax.set_ylabel("ms")
    _style_time_axis(ax)
    fig.tight_layout()
    path = out_dir / "ops_duration.png"
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_k6(out_dir: Path, minutes: int = 60) -> Optional[Path]:
    """k6 성능 테스트 결과 (총 요청 / VUs / p95 / 오류율)."""
    # 추세 지표는 종료 시점 0을 피하려 최근 창에서 집계(요약 지표와 동일 기준).
    # duration은 '초' 단위 → ms로 1000배, 엔드포인트별 시리즈는 sum()/max()로 집계.
    total = _query_instant("sum(max_over_time(k6_http_reqs_total[15m]))")
    vus = _query_instant("max(max_over_time(k6_vus_max[15m]))")
    p95 = _query_instant("1000 * max(max_over_time(k6_http_req_duration_p95[15m]))")
    failrate = _query_instant("max(max_over_time(k6_http_req_failed_rate[15m]))")
    if total is None and vus is None and p95 is None:
        return None

    fig, axes = plt.subplots(1, 4, figsize=(12, 2.8))
    stats = [
        ("총 HTTP 요청", f"{int(total):,}" if total is not None else "No data", "#2563EB"),
        ("최대 VUs", f"{int(vus)}" if vus is not None else "No data", "#7C3AED"),
        ("p95 응답시간", f"{p95:.1f} ms" if p95 is not None else "No data", "#F59E0B"),
        ("오류율", f"{failrate * 100:.2f}%" if failrate is not None else "No data", "#EF4444"),
    ]
    for ax, (label, value, color) in zip(axes, stats):
        ax.axis("off")
        ax.text(0.5, 0.62, value, ha="center", va="center", fontsize=20, fontweight="bold", color=color)
        ax.text(0.5, 0.22, label, ha="center", va="center", fontsize=10, color="#475569")
    fig.suptitle("k6 성능 테스트 결과 (최근 실행)", fontsize=12, y=1.05)
    fig.tight_layout()
    path = out_dir / "ops_k6.png"
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return path


def build_ops_snapshot(out_dir: Path, minutes: int = 30) -> dict:
    """운영/k6 스냅샷 차트를 모두 생성하고 결과(차트 경로 + 요약)를 반환한다."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    available = prometheus_available()

    charts = {
        "golden": chart_golden_signals(out_dir, minutes) if available else None,
        "traffic": chart_traffic_errors(out_dir, minutes) if available else None,
        "duration": chart_duration(out_dir, minutes) if available else None,
        "k6": chart_k6(out_dir) if available else None,
    }
    k6_fail = _query_instant("max(max_over_time(k6_http_req_failed_rate[15m]))") if available else None
    summary = {
        "prometheus_available": available,
        "captured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "req_per_sec": _query_instant("sum(rate(ask_requests_total[1m]))") if available else None,
        "error_rate_pct": _query_instant(
            '100 * (sum(rate(ask_requests_total{status="error"}[5m])) or vector(0)) / clamp_min(sum(rate(ask_requests_total[5m])), 0.001)'
        ) if available else None,
        "p95_ms": _query_instant("1000 * histogram_quantile(0.95, sum(rate(ask_request_latency_seconds_bucket[5m])) by (le))") if available else None,
        # k6 지표 주의사항:
        #  - duration 계열 단위는 '초' → ms 표기하려면 1000을 곱한다.
        #  - 엔드포인트(/ask, /health)별로 시리즈가 나뉘므로 sum()/max()로 집계해 스칼라로 만든다.
        #  - 추세 지표는 매 플러시마다 리셋되는 게이지라 instant는 종료 시점 0을 잡을 수 있어 *_over_time으로 창 집계한다.
        "k6_total": _query_instant("sum(max_over_time(k6_http_reqs_total[15m]))") if available else None,
        "k6_vus": _query_instant("max(max_over_time(k6_vus_max[15m]))") if available else None,
        "k6_iterations": _query_instant("sum(max_over_time(k6_iterations_total[15m]))") if available else None,
        "k6_p95_ms": _query_instant("1000 * max(max_over_time(k6_http_req_duration_p95[15m]))") if available else None,
        "k6_p99_ms": _query_instant("1000 * max(max_over_time(k6_http_req_duration_p99[15m]))") if available else None,
        "k6_avg_ms": _query_instant("1000 * avg(avg_over_time(k6_http_req_duration_avg[15m]))") if available else None,
        "k6_fail_pct": (k6_fail * 100) if k6_fail is not None else None,
        "k6_checks_pct": (lambda v: v * 100 if v is not None else None)(
            _query_instant("avg(avg_over_time(k6_checks_rate[15m]))") if available else None),
    }
    alerts = fetch_alert_states() if available else []
    return {"charts": charts, "summary": summary, "alerts": alerts}


# ---------------------------------------------------------------------------
# Grafana 패널 렌더링 — 대시보드의 '실제' 패널을 항목별 PNG로 캡처한다.
# (docker-compose의 grafana-image-renderer가 있어야 동작. 없으면 빈 리스트 반환 → 보고서는
#  matplotlib 재현 차트로 폴백.)  대시보드 임베딩과 100% 동일한 그래프를 보고서 부록에 담기 위함.
# ---------------------------------------------------------------------------
GRAFANA_AUTH_HEADER = {"Authorization": "Basic YWRtaW46YWRtaW4="}  # admin:admin

# 대시보드(ai-quality-ops / k6-performance)의 패널을 화면 구성 순서대로 나열.
#   (panelId, 표시제목, 렌더 width, 렌더 height)
GRAFANA_PANEL_MANIFEST = [
    {"section": "운영 대시보드 — 서비스 헬스 (Golden Signals)", "uid": "ai-quality-ops", "slug": "ai-agent",
     "panels": [(1, "서비스 상태", 500, 260), (2, "오류율 (Errors)", 500, 260),
                (3, "p95 응답시간 (Latency)", 500, 260), (4, "처리량 (Traffic, req/s)", 500, 260)]},
    {"section": "트래픽 & 오류 (Rate / Errors)", "uid": "ai-quality-ops", "slug": "ai-agent",
     "panels": [(5, "초당 요청률 — agent_type별", 1000, 360), (6, "성공 vs 오류 요청 (누적)", 1000, 360)]},
    {"section": "응답시간 분포 (Duration)", "uid": "ai-quality-ops", "slug": "ai-agent",
     "panels": [(7, "응답시간 백분위 (p50 / p95 / p99, ms)", 1000, 360)]},
    {"section": "k6 성능 테스트 결과", "uid": "k6-performance", "slug": "k6",
     "panels": [(1, "총 HTTP 요청 수", 500, 240), (2, "오류율 (http_req_failed)", 500, 240),
                (3, "p95 응답시간 (ms)", 500, 240), (4, "가상 사용자 수 (VUs)", 500, 240),
                (5, "응답시간 추이 (avg / p95 / max, ms)", 1000, 360), (6, "초당 요청률 & 체크 성공률", 1000, 360)]},
]


def grafana_render_available(timeout: int = 30) -> bool:
    """Grafana image-renderer가 실제 PNG를 반환하는지 확인한다(콜드스타트가 있어 넉넉히 대기)."""
    url = f"{GRAFANA_URL}/render/d-solo/k6-performance/k6?panelId=1&from=now-5m&to=now&width=200&height=120"
    try:
        req = urllib.request.Request(url, headers=GRAFANA_AUTH_HEADER)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200 and "image" in (r.headers.get("Content-Type") or "")
    except Exception:
        return False


def _render_one_panel(uid, slug, panel_id, out_path: Path, width, height, from_, to, timeout: int = 30):
    url = (f"{GRAFANA_URL}/render/d-solo/{uid}/{slug}?panelId={panel_id}"
           f"&from={from_}&to={to}&width={width}&height={height}&theme=light&tz=Asia%2FSeoul")
    try:
        req = urllib.request.Request(url, headers=GRAFANA_AUTH_HEADER)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200 or "image" not in (r.headers.get("Content-Type") or ""):
                return None
            data = r.read()
        out_path.write_bytes(data)
        return out_path
    except Exception:
        return None


def render_grafana_panels(out_dir, from_: str = "now-30m", to: str = "now") -> list:
    """
    대시보드의 실제 Grafana 패널을 항목별로 PNG 캡처한다.
    반환: [{"section": str, "panels": [{"title": str, "path": Path}]}]  (성공한 패널만).
    렌더러가 없거나 전부 실패하면 빈 리스트 → 보고서는 matplotlib 차트로 폴백.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not grafana_render_available():
        return []
    sections = []
    for sec in GRAFANA_PANEL_MANIFEST:
        panels = []
        for pid, title, w, h in sec["panels"]:
            fname = f"grafana_{sec['uid']}_{pid}.png"
            p = _render_one_panel(sec["uid"], sec["slug"], pid, out_dir / fname, w, h, from_, to)
            if p:
                panels.append({"title": title, "path": p})
        if panels:
            sections.append({"section": sec["section"], "panels": panels})
    return sections


SNAPSHOT_SUBDIR = "ops_snapshot"


def save_ops_snapshot(run_dir, minutes: int = 30) -> dict:
    """
    현재 Prometheus/k6 지표를 run_dir/ops_snapshot/ 에 '동결(freeze)' 저장한다.
    차트 PNG 4개 + snapshot.json(summary + alerts + 차트 파일명 + 저장시각)을 남겨,
    이후 데이터 창이 만료되거나 k6를 다시 돌려도 '그 당시 값'을 그대로 재현할 수 있게 한다.
    반환: build_ops_snapshot과 동일 형식의 dict.
    """
    run_dir = Path(run_dir)
    snap_dir = run_dir / SNAPSHOT_SUBDIR
    snap = build_ops_snapshot(snap_dir, minutes)  # matplotlib PNG는 snap_dir 안에 생성됨
    # 대시보드와 동일한 '실제 Grafana 패널'을 항목별로 캡처(렌더러 있으면). 부록이 이걸 우선 사용한다.
    grafana_panels = render_grafana_panels(snap_dir, from_=f"now-{minutes}m", to="now")
    snap["grafana_panels"] = grafana_panels
    meta = {
        "summary": snap["summary"],
        "alerts": snap.get("alerts", []),
        # 폴더 이동에도 견디도록 절대경로가 아닌 '파일명'만 저장한다.
        "charts": {k: (Path(v).name if v else None) for k, v in snap["charts"].items()},
        "grafana_panels": [
            {"section": s["section"], "panels": [{"title": p["title"], "file": Path(p["path"]).name} for p in s["panels"]]}
            for s in grafana_panels
        ],
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / "snapshot.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return snap


def has_ops_snapshot(run_dir) -> bool:
    if run_dir is None:
        return False
    return (Path(run_dir) / SNAPSHOT_SUBDIR / "snapshot.json").exists()


def load_ops_snapshot(run_dir):
    """
    run_dir/ops_snapshot/snapshot.json 이 있으면 보고서 부록/대시보드가 쓰는 형식으로 복원한다.
    없으면 None (호출부는 None이면 라이브 조회로 폴백).
    """
    if run_dir is None:
        return None
    snap_dir = Path(run_dir) / SNAPSHOT_SUBDIR
    meta_path = snap_dir / "snapshot.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    charts = {}
    for k, fname in (meta.get("charts") or {}).items():
        p = snap_dir / fname if fname else None
        charts[k] = p if (p and p.exists()) else None
    # 저장된 실제 Grafana 패널 이미지 복원(있으면)
    grafana_panels = []
    for s in (meta.get("grafana_panels") or []):
        panels = []
        for pnl in s.get("panels", []):
            fp = snap_dir / pnl.get("file", "")
            if fp.exists():
                panels.append({"title": pnl.get("title", ""), "path": fp})
        if panels:
            grafana_panels.append({"section": s.get("section", ""), "panels": panels})
    summary = meta.get("summary") or {}
    summary["frozen"] = True                 # 저장된 스냅샷임을 표시
    summary["saved_at"] = meta.get("saved_at")
    return {"charts": charts, "summary": summary, "alerts": meta.get("alerts", []), "grafana_panels": grafana_panels}


if __name__ == "__main__":
    import tempfile
    d = Path(tempfile.mkdtemp())
    snap = build_ops_snapshot(d)
    print("Prometheus available:", snap["summary"]["prometheus_available"])
    print("captured_at:", snap["summary"]["captured_at"])
    for k, v in snap["charts"].items():
        print(f"  {k}: {'생성됨 ' + str(v) if v else 'No data(None)'}")
    print("summary:", {k: v for k, v in snap["summary"].items() if k != "prometheus_available"})
