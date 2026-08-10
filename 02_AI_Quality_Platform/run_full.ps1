# =============================================================================
# run_full.ps1  —  운영 모니터링 데이터까지 한 번에 채우는 통합 실행 스크립트
#
# 실행:
#   cd C:\ai_quality_final_project_rule_2
#   .\run_full.ps1
#
# 이 스크립트가 하는 일 (순서 중요):
#   1) Docker 스택 기동      : app(8000) + Prometheus(9090) + Grafana(3000)
#   2) FastAPI /health 대기  : 앱이 준비될 때까지
#   3) k6 부하테스트 실행     : Prometheus remote-write 옵션 포함(-o experimental-prometheus-rw)
#                              → "운영 모니터링 · 성능 스냅샷" 4개 패널이 채워지는 핵심 단계
#   4) Streamlit 대시보드 기동: http://localhost:8501 (백그라운드)
#   5) 브라우저 자동 오픈
#
# 왜 이 순서인가:
#   - Prometheus는 도커 네트워크 안에서 app:8000 을 스크레이핑하므로 반드시 "도커 앱"이 대상.
#     (로컬 uvicorn을 따로 띄우면 8000 포트 충돌 + Prometheus가 못 봄 → run_all.ps1의 문제점)
#   - Grafana 패널은 from=now-30m 창을 보므로, k6를 돌린 뒤 30분 안에 새로고침하면 데이터가 보임.
#
# 옵션:
#   -SkipK6      : k6 부하테스트를 건너뜀(성능 스냅샷은 비게 됨)
#   -Rebuild     : docker compose 를 --build 로 재빌드
# =============================================================================
param(
    [switch]$SkipK6,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"

function Info($m){ Write-Host $m -ForegroundColor Cyan }
function Ok($m){ Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[!] $m" -ForegroundColor Yellow }

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " AI Agent 품질·운영 모니터링 플랫폼 — 통합 실행" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# --- 0. 사전 점검 ------------------------------------------------------------
if (-not (Test-Path $venvPy)) { Warn ".venv 없음. 먼저: python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt"; exit 1 }
docker info *> $null
if ($LASTEXITCODE -ne 0) { Warn "Docker Desktop이 실행 중이 아닙니다. Docker Desktop을 켠 뒤 다시 실행하세요."; exit 1 }

# --- 1. Docker 스택 기동 -----------------------------------------------------
Info "`n[1/5] Docker 스택 기동 (app + Prometheus + Grafana)..."
if ($Rebuild) { docker compose up -d --build } else { docker compose up -d }
if ($LASTEXITCODE -ne 0) { Warn "docker compose 기동 실패"; exit 1 }
Ok "app→:8000  Prometheus→:9090  Grafana→:3000 (admin/admin)"

# --- 2. FastAPI 준비 대기 ----------------------------------------------------
Info "`n[2/5] FastAPI /health 준비 대기 (최대 60초)..."
$ready = $false
for ($i=0; $i -lt 60; $i++) {
    try { if ((Invoke-WebRequest "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { $ready=$true; break } } catch { Start-Sleep 1 }
}
if ($ready) { Ok "FastAPI 준비 완료" } else { Warn "FastAPI가 60초 내 준비되지 않음 — 계속 진행"; }

# --- 3. k6 부하테스트 (Prometheus remote-write) ------------------------------
if ($SkipK6) {
    Warn "`n[3/5] -SkipK6 지정 → k6 생략 (성능 스냅샷은 비어 있음)"
} elseif (-not (Get-Command k6 -ErrorAction SilentlyContinue)) {
    Warn "`n[3/5] k6 미설치 (choco install k6) → 성능 스냅샷 생략"
} else {
    Info "`n[3/5] k6 부하테스트 실행 (약 30초, Prometheus로 remote-write)..."
    $env:K6_PROMETHEUS_RW_SERVER_URL = "http://localhost:9090/api/v1/write"
    $env:K6_PROMETHEUS_RW_TREND_STATS = "p(95),p(99),min,max,avg"
    k6 run -o experimental-prometheus-rw performance\k6_test.js
    if ($LASTEXITCODE -eq 0) { Ok "k6 완료 — 성능 데이터가 Prometheus에 기록됨 (이후 30분간 대시보드에 표시)" }
    else { Warn "k6 종료 코드 $LASTEXITCODE (임계치 초과일 수 있음). 데이터는 부분적으로 들어갔을 수 있음" }

    # k6 직후, 살아있는 데이터를 최신 실행 폴더에 '동결 스냅샷'으로 자동 저장한다.
    # 이후 그 히스토리를 다시 열거나 보고서를 생성하면 '그 당시 값'이 그대로 재현된다.
    Info "  |- 운영/성능 스냅샷 자동 저장 중..."
    Start-Sleep -Seconds 3   # 마지막 remote-write 플러시가 Prometheus에 반영될 여유
    & $venvPy -c "from pathlib import Path; from config import REPORTS_DIR; from quality.report_generator import list_archived_runs; from quality.ops_snapshot import save_ops_snapshot; runs=list_archived_runs(); target=Path(runs[0]['json_path']).parent if (runs and runs[0].get('timestamp')!='legacy') else REPORTS_DIR; snap=save_ops_snapshot(target); print('  saved ->', target); print('  prometheus_available =', snap['summary'].get('prometheus_available'))"
    if ($LASTEXITCODE -eq 0) { Ok "스냅샷 저장 완료 (히스토리에 고정)" } else { Warn "스냅샷 자동 저장 실패 — 대시보드 운영 모니터링 탭의 '현재 스냅샷 저장' 버튼으로 수동 저장 가능" }
}

# --- 4. Streamlit 대시보드 (백그라운드) --------------------------------------
Info "`n[4/5] Streamlit 대시보드 기동 (http://localhost:8501)..."
$st = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($st) { Ok "이미 8501에서 실행 중 — 재사용" }
else {
    # 파이프라인 등이 이모지를 print해도 Windows cp949에서 안 죽도록 UTF-8 강제
    $env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
    Start-Process -FilePath $venvPy -ArgumentList "-m","streamlit","run","dashboard\streamlit_app.py","--server.headless","true","--server.port","8501" -WorkingDirectory $Root
    for ($i=0; $i -lt 30; $i++) { try { if ((Invoke-WebRequest "http://localhost:8501/_stcore/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200){ break } } catch { Start-Sleep 1 } }
    Ok "Streamlit 준비 완료"
}

# --- 5. 브라우저 오픈 --------------------------------------------------------
Info "`n[5/5] 브라우저 오픈..."
Start-Process "http://localhost:8501"

Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host " 실행 완료 — 접속 주소" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " 대시보드   : http://localhost:8501   (운영 모니터링 탭까지 데이터 표시)"
Write-Host " FastAPI    : http://localhost:8000/docs"
Write-Host " Prometheus : http://localhost:9090"
Write-Host " Grafana    : http://localhost:3000   (admin/admin)"
Write-Host "--------------------------------------------------"
Write-Host " * 성능 스냅샷은 k6 실행 후 30분 창(now-30m)에 표시됩니다." -ForegroundColor Yellow
Write-Host " * 성능 데이터만 다시 채우려면:  k6만 재실행 → 이 스크립트를 다시 실행하거나" -ForegroundColor Yellow
Write-Host "   `$env:K6_PROMETHEUS_RW_SERVER_URL='http://localhost:9090/api/v1/write'; k6 run -o experimental-prometheus-rw performance\k6_test.js" -ForegroundColor Yellow
Write-Host " * 종료:  docker compose down   (Streamlit 창은 Ctrl+C 또는 프로세스 종료)" -ForegroundColor Yellow



