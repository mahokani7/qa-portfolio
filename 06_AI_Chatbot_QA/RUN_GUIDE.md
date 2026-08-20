# 프로젝트 실행 가이드

이 문서는 현재 프로젝트를 실행하고, 화면에서 테스트 결과와 k6 성능 테스트 결과를 확인하는 방법을 정리합니다.

> 아래 `cd C:\260710_project\ai_quality_final_project_Team3`는 원 개발 환경의 예시 경로입니다. 실제 실행 시에는 이 저장소를 클론한 본인 환경의 `06_AI_Chatbot_QA` 경로로 바꿔서 사용하세요.

## 1. 기본 위치

PowerShell에서 프로젝트 폴더로 이동합니다.

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
```

가상환경은 상위 폴더의 `.venv`를 사용합니다.

```powershell
..\.venv\Scripts\python.exe
```

## 2. API 서버 실행

터미널 1에서 FastAPI 서버를 실행합니다.

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
..\.venv\Scripts\python.exe -m uvicorn api_app:app --reload --port 8000
```

정상 실행되면 아래 주소로 확인할 수 있습니다.

```text
http://localhost:8000
http://localhost:8000/health
http://localhost:8000/docs
```

만약 `Could not import module "api_app"` 오류가 나오면 현재 위치가 프로젝트 폴더가 아닌 것입니다. 아래처럼 실행합니다.

```powershell
cd C:\260710_project
.\.venv\Scripts\python.exe -m uvicorn api_app:app --app-dir .\ai_quality_final_project_Team3 --reload --port 8000
```

## 3. Streamlit 대시보드 실행

터미널 2를 새로 열고 Streamlit 화면을 실행합니다.

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
..\.venv\Scripts\streamlit.exe run dashboard\streamlit_app.py --server.port 8501
```

브라우저에서 아래 주소로 접속합니다.

```text
http://localhost:8501
```

## 4. 테스트 수행 결과 확인

Streamlit 화면에서 아래 메뉴로 이동합니다.

```text
테스트 관리 > 테스트 수행 이력
```

수행 이력에서 상세 버튼을 누르면 테스트 결과, 고도화 지표, 결과 보고서를 확인할 수 있습니다.

결과 보고서에서 부록을 포함하면 k6 성능 테스트, 운영 모니터링, Jira 결함 등록 정보 등이 함께 반영됩니다.

```text
테스트 관리 > 테스트 수행 이력 > 상세 팝업 > 결과 보고서 > 부록 포함
```

## 5. k6 설치 확인

k6 성능 테스트를 화면에서 실행하려면 PC에 k6가 설치되어 있어야 합니다.

```powershell
k6 version
```

버전 정보가 나오면 설치된 상태입니다.

설치되어 있지 않으면 Streamlit 화면에서 k6 실행 버튼이 비활성화되거나 실행 불가 안내가 표시됩니다.

## 6. 화면에서 k6 성능 테스트 실행

API 서버와 Streamlit을 모두 실행한 뒤 아래 메뉴로 이동합니다.

```text
성능관리 > K6 성능테스트
```

대상 URL은 먼저 헬스체크 주소로 테스트하는 것을 권장합니다.

```text
http://localhost:8000/health
```

질문 API를 테스트하려면 아래처럼 입력할 수 있습니다.

```text
http://localhost:8000/ask?question=이 교육과정은 총 몇 시간인가요?
```

화면에서 조절할 수 있는 값은 다음과 같습니다.

- 동시 사용자 수
- 총 테스트 시간
- Ramp-up 시간
- 요청 간 대기시간
- p95 응답시간 기준
- 실패율 기준
- 체크 성공률 기준

설정을 조정한 뒤 `k6 실행` 버튼을 누르면 성능 테스트가 실행됩니다.

## 7. k6 결과 확인 위치

화면에서 바로 확인할 수 있는 메뉴입니다.

```text
성능관리 > K6 성능테스트 > 실행 결과
성능관리 > K6 성능테스트 > 최근 k6 수행이력
성능관리 > 운영 모니터링
```

파일로 저장되는 위치는 아래와 같습니다.

```text
reports/k6_runs/<실행시각>/
reports/k6_summary.json
```

`reports/k6_summary.json`은 최신 k6 결과이며, 결과 보고서 부록에서도 이 파일을 사용합니다.

## 8. Prometheus 연결

운영 모니터링 화면에서 Prometheus를 연결하려면 먼저 API 서버가 `/metrics`를 제공해야 합니다.

API 서버 실행 후 아래 주소가 열리는지 확인합니다.

```text
http://localhost:8000/metrics
```

Prometheus 설정 파일은 프로젝트 루트의 `prometheus.yml`을 사용합니다.

```text
prometheus.yml
```

Prometheus를 로컬 실행 파일로 설치한 경우, 터미널 3에서 아래처럼 실행합니다.

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
C:\prometheus\prometheus.exe --config.file=prometheus.yml --web.listen-address=:9090
```

정상 실행되면 아래 주소로 Prometheus를 확인합니다.

```text
http://localhost:9090
```

Streamlit의 운영 모니터링 화면은 기본적으로 아래 주소의 Prometheus를 조회합니다.

```text
http://localhost:9090
```

`C:\prometheus`가 Windows 환경변수 `Path`에 등록되어 있다면 아래처럼 짧게 실행해도 됩니다.

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
prometheus.exe --config.file=prometheus.yml --web.listen-address=:9090
```

다른 Prometheus 주소를 사용할 경우 `.env`에 아래 값을 설정합니다.

```env
PROMETHEUS_URL=http://localhost:9090
```

Prometheus 화면에서 아래 쿼리를 입력해 데이터가 나오는지 확인할 수 있습니다.

```promql
up
```

```promql
http_requests_total
```

```promql
agent_response_seconds_count
```

Docker로 Prometheus를 실행하는 경우에는 컨테이너 안에서 Windows 호스트의 API 서버를 `localhost`로 볼 수 없습니다. 이 경우 `prometheus.yml`의 target을 아래처럼 바꿔야 합니다.

```yaml
targets:
  - "host.docker.internal:8000"
```

그 다음 Docker에서 실행합니다.

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
docker run --rm -p 9090:9090 -v ${PWD}\prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus
```

## 9. 종료 방법

각 터미널에서 실행 중인 서버는 `Ctrl + C`로 종료합니다.

종료 대상은 보통 두 개입니다.

- uvicorn API 서버
- Streamlit 대시보드
- Prometheus

## 10. 권장 실행 순서 요약

1. API 서버 실행

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
..\.venv\Scripts\python.exe -m uvicorn api_app:app --reload --port 8000
```

2. Streamlit 실행

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
..\.venv\Scripts\streamlit.exe run dashboard\streamlit_app.py --server.port 8501
```

3. 브라우저 접속

```text
http://localhost:8501
```

4. k6 성능 테스트 실행

```text
성능관리 > K6 성능테스트
```

5. Prometheus 실행

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
C:\prometheus\prometheus.exe --config.file=prometheus.yml --web.listen-address=:9090
```

6. 결과 보고서 확인

```text
테스트 관리 > 테스트 수행 이력 > 상세 팝업 > 결과 보고서
```

## 11. Docker Compose 통합 실행

Docker Compose를 사용하면 FastAPI, Streamlit, Prometheus, Grafana를 한 번에 실행할 수 있습니다.

먼저 Windows에서 Docker Desktop을 실행합니다. Docker Desktop 상태가 `Running` 또는 `Engine running`이 된 뒤 PowerShell에서 아래 명령으로 Docker가 준비됐는지 확인합니다.

```powershell
docker ps
```

정상이라면 실행 중인 컨테이너 목록이 표시됩니다. Docker Desktop이 켜져 있지 않으면 `Cannot connect to the Docker daemon` 오류가 날 수 있습니다.

Docker Desktop 준비가 끝나면 프로젝트 전체 환경을 실행합니다.

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
docker compose up --build
```

실행 후 접속 주소는 아래와 같습니다.

```text
Streamlit 대시보드: http://localhost:8501
FastAPI: http://localhost:8000
Prometheus: http://localhost:9090
Grafana: http://localhost:3000
```

Grafana 기본 계정은 아래와 같습니다.

```text
ID: admin
PW: admin
```

Prometheus datasource는 Docker Compose 실행 시 Grafana에 자동 등록됩니다.

종료할 때는 아래 명령을 사용합니다.

```powershell
cd C:\260710_project\ai_quality_final_project_Team3
docker compose down
```
