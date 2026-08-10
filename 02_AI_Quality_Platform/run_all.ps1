# =============================================================================
# run_all.ps1
# AI Agent 품질관리·운영 모니터링 플랫폼 — 전체 구성요소 한 번에 실행
#
# 실행: PowerShell에서
#   cd C:\ai_quality_final_project_rule_2
#   .\run_all.ps1
#
# 동작:
#   1) 가상환경 활성화
#   2) pytest 자동 테스트 (1회 실행 후 결과 요약)
#   3) FastAPI 서버        → 새 창 (http://localhost:8000/docs)
#   4) Streamlit 대시보드   → 새 창 (http://localhost:8501)
#   5) Docker 스택(app+Prometheus+Grafana) → Docker 실행 중일 때만
#   6) k6 성능 테스트       → FastAPI 준비된 뒤 새 창
#
# 종료: 각 새 창에서 Ctrl+C, Docker는  docker compose down
# =============================================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " AI Agent 품질관리 플랫폼 - 전체 실행" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# --- 0. 가상환경 확인 ---------------------------------------------------------
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$venvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvPython)) {
    Write-Host "[오류] .venv를 찾을 수 없습니다. 먼저 아래를 실행하세요:" -ForegroundColor Red
    Write-Host "  python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}
& $venvActivate
Write-Host "[OK] 가상환경 활성화됨" -ForegroundColor Green

# --- 1. pytest 자동 테스트 (1회) ---------------------------------------------
Write-Host "`n[1/5] pytest 자동 테스트 실행..." -ForegroundColor Cyan
& $venvPython -m pytest -q
if ($LASTEXITCODE -eq 0) {
    & $venvPython scripts\generate_test_report_md.py
    Write-Host "[OK] 테스트 결과: tests_output\test_results.md" -ForegroundColor Green
} else {
    Write-Host "[경고] 일부 테스트 실패 — 계속 진행합니다." -ForegroundColor Yellow
}

# --- 2. FastAPI 서버 (새 창) --------------------------------------------------
Write-Host "`n[2/5] FastAPI 서버를 새 창에서 시작..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$ProjectRoot'; & '$venvActivate'; Write-Host 'FastAPI: http://localhost:8000/docs' -ForegroundColor Green; uvicorn app.main:app --reload"
Write-Host "[OK] FastAPI → http://localhost:8000/docs" -ForegroundColor Green

# --- 3. Streamlit 대시보드 (새 창) -------------------------------------------
Write-Host "`n[3/5] Streamlit 대시보드를 새 창에서 시작..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$ProjectRoot'; & '$venvActivate'; Write-Host 'Streamlit: http://localhost:8501' -ForegroundColor Green; streamlit run dashboard\streamlit_app.py"
Write-Host "[OK] Streamlit → http://localhost:8501" -ForegroundColor Green

# --- 4. Docker 스택 (Prometheus + Grafana + app) -----------------------------
Write-Host "`n[4/5] Docker 스택(app+Prometheus+Grafana) 확인..." -ForegroundColor Cyan
docker info 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Docker 실행 중 → docker compose up -d --build" -ForegroundColor Green
    docker compose up -d --build
    Write-Host "[OK] Prometheus → http://localhost:9090 / Grafana → http://localhost:3000 (admin/admin)" -ForegroundColor Green
} else {
    Write-Host "[건너뜀] Docker Desktop이 실행 중이 아닙니다." -ForegroundColor Yellow
    Write-Host "         Docker Desktop을 켠 뒤 수동 실행:  docker compose up -d --build" -ForegroundColor Yellow
}

# --- 5. FastAPI 준비 대기 후 k6 성능 테스트 (새 창) ---------------------------
Write-Host "`n[5/5] FastAPI 준비 대기 중 (최대 30초)..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 1 }
}
if ($ready) {
    Write-Host "[OK] FastAPI 준비 완료 → k6 성능 테스트를 새 창에서 시작" -ForegroundColor Green
    if (Get-Command k6 -ErrorAction SilentlyContinue) {
        Start-Process powershell -ArgumentList "-NoExit", "-Command", `
            "cd '$ProjectRoot'; Write-Host 'k6 성능 테스트 실행 중...' -ForegroundColor Green; k6 run performance\k6_test.js"
    } else {
        Write-Host "[건너뜀] k6가 설치되어 있지 않습니다 (choco install k6)." -ForegroundColor Yellow
    }
} else {
    Write-Host "[건너뜀] FastAPI가 30초 안에 준비되지 않아 k6를 건너뜁니다." -ForegroundColor Yellow
}

Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host " 실행 요약" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " FastAPI    : http://localhost:8000/docs"
Write-Host " Streamlit  : http://localhost:8501"
Write-Host " Prometheus : http://localhost:9090   (Docker 실행 시)"
Write-Host " Grafana    : http://localhost:3000   (Docker 실행 시, admin/admin)"
Write-Host " 테스트결과 : tests_output\test_results.md"
Write-Host "--------------------------------------------------"
Write-Host " 종료: 각 새 창에서 Ctrl+C  /  Docker:  docker compose down" -ForegroundColor Yellow
