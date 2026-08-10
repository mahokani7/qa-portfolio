# AWS ECS Fargate 배포

이 애플리케이션은 웹 서버와 6개 내부 gRPC Agent를 하나의 ECS 작업에서 실행한다.
웹 포트 `8000`만 Application Load Balancer에 공개하고 Agent 포트 `6001~6006`은
컨테이너의 loopback 통신으로 유지한다.

## 보안 원칙

- AWS 루트 사용자 자격 증명과 장기 액세스 키를 공유하거나 애플리케이션에 저장하지 않는다.
- 사람의 배포 접근은 IAM Identity Center(SSO)의 전용 Permission Set을 사용한다.
- OpenAI·Anthropic 키와 웹 접근 토큰은 Secrets Manager에서 ECS 작업에 주입한다.
- `.env`는 Docker 이미지, ECR, Git에 포함하지 않는다.
- 운영 ALB는 HTTPS만 허용하고 HTTP는 HTTPS로 리디렉션한다.

## 로컬 컨테이너 검증

프로젝트 루트에서 실행한다.

```powershell
docker build -t voc-improve:local .
docker run --rm -p 8000:8000 `
  --env-file .env `
  -e OPENAI_API_KEY=$env:OPENAI_API_KEY `
  -e WEB_COOKIE_SECURE=false `
  -v voc-improve-reports:/app/quality_diagnosis/reports `
  voc-improve:local
```

상태 점검:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

`agents_ready`가 `6`이고 HTTP 상태가 `200`이어야 한다.

## AWS 리소스

리전은 `ap-northeast-2`를 기준으로 한다.

1. ECR 저장소 `voc-improve`
2. Secrets Manager 비밀 5개
   - `voc-improve/openai`
   - `voc-improve/anthropic`
   - `voc-improve/web-admin`
   - `voc-improve/web-reviewer`
   - `voc-improve/web-viewer`
3. CloudWatch Logs 그룹 `/ecs/voc-improve`
4. EFS 파일시스템과 UID/GID `10001`의 Access Point
5. ECS 실행 역할 `voc-improve-ecs-execution`
6. ECS 작업 역할 `voc-improve-ecs-task`
7. ECS Fargate 클러스터와 서비스
8. Application Load Balancer, ACM 인증서, 필요 시 Route 53 레코드

EFS 보안 그룹은 ECS 작업 보안 그룹에서 오는 TCP `2049`만 허용한다. ECS 작업 보안
그룹의 TCP `8000` 인바운드는 ALB 보안 그룹만 허용한다. 운영 작업을 private subnet에
두면 OpenAI·Anthropic 호출과 ECR·Secrets Manager 접근을 위한 NAT Gateway 또는
필요한 VPC Endpoint 구성이 필요하다.

## 이미지 빌드와 ECR 업로드

`<AWS_ACCOUNT_ID>`와 `<IMAGE_TAG>`를 실제 값으로 바꾼다.

```powershell
$AwsRegion = "ap-northeast-2"
$AwsAccountId = "<AWS_ACCOUNT_ID>"
$ImageTag = "<IMAGE_TAG>"
$Repository = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com/voc-improve"

aws ecr get-login-password --region $AwsRegion |
  docker login --username AWS --password-stdin "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"
docker build -t "voc-improve:$ImageTag" .
docker tag "voc-improve:$ImageTag" "${Repository}:$ImageTag"
docker push "${Repository}:$ImageTag"
```

## ECS 설정

`task-definition.json.example`의 다음 자리표시자를 치환한 후 작업 정의를 등록한다.

- `<AWS_ACCOUNT_ID>`
- `<IMAGE_TAG>`
- `<EFS_FILE_SYSTEM_ID>`
- `<EFS_ACCESS_POINT_ID>`
- `<OPENAI_SECRET_ARN>`
- `<ANTHROPIC_SECRET_ARN>`
- `<WEB_ADMIN_SECRET_ARN>`
- `<WEB_REVIEWER_SECRET_ARN>`
- `<WEB_VIEWER_SECRET_ARN>`

서비스 설정:

- Desired count: `1`
- Health check path: `/healthz`
- Health check grace period: `90초`
- ALB idle timeout: `240초`
- Target type: `ip`
- Target port: `8000`
- Deployment minimum healthy percent: `0`
- Deployment maximum percent: `100`

현재 SQLite와 메모리 세션을 사용하므로 여러 작업으로 수평 확장하지 않는다. 다중 작업이
필요하면 SQLite를 RDS PostgreSQL로, 로그인 세션을 Redis 또는 DynamoDB로 이전한다.

## 배포 확인

1. ECS 작업 로그에서 6개 Agent 준비 완료 확인
2. 대상 그룹의 `/healthz` 상태가 Healthy인지 확인
3. HTTPS 로그인과 역할별 토큰 확인
4. 단건 분석 실행
5. 보고서 생성 후 ECS 작업을 재시작
6. EFS에 저장된 실행 이력과 보고서가 유지되는지 확인

루트 사용자는 계정 복구와 결제 등 루트 전용 작업에만 사용한다. 배포 자동화 또는 사람의
일상 배포 작업에는 사용하지 않는다.
