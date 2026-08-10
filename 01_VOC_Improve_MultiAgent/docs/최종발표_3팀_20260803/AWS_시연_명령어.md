# AWS 시연 명령어 (3팀 · CloudShell)

리전은 **ap-northeast-2(서울)** 기준입니다. 모든 명령은 **CloudShell** 안에서 실행하며,
로컬에 AWS 액세스 키를 저장하지 않습니다.

> **녹화 전 필수**
> - **IAM 사용자**로 로그인합니다. root 계정은 사용하지 않습니다.
> - 브라우저 우측 상단 **계정 ID·사용자명**은 확대 화면에서 가리거나 흐림 처리합니다.
> - AWS Budgets에서 **Zero Spend Budget**을 미리 만들어 둡니다(비용 알림 확인용).
> - 아래 0단계~2단계는 **녹화 전에 미리 실행**해 두면 영상이 늘어지지 않습니다.

---

## 0. 로컬에서 증적 만들기 (녹화 대상 · 약 20초)

```powershell
cd C:\qaeduc2\VOC_Improve_1
.venv\Scripts\python.exe scripts\build_aws_evidence.py
.venv\Scripts\python.exe scripts\pack_for_cloudshell.py
```

생성물

| 파일 | 내용 |
| --- | --- |
| `aws_upload/qa_evidence/pytest_result.txt` | pytest 콘솔 결과 (32건) |
| `aws_upload/qa_evidence/pytest_report.html` | 시각화 테스트 보고서 |
| `aws_upload/qa_evidence/junit_result.xml` | CI 호환 결과 |
| `aws_upload/qa_evidence/llm_judge_result.csv` | **독립 Judge 케이스별 점수 (3팀 핵심)** |
| `aws_upload/qa_evidence/llm_judge_result.json` | 항목별 평가 사유 원문 |
| `aws_upload/qa_evidence/quality_score_report.md` | **통합 평가점수** |
| `aws_upload/qa_evidence/deployment_decision.md` | **최종 배포판정** |
| `aws_upload/qa_evidence/MANIFEST.md` | SHA256 무결성 목록 |
| `aws_upload/qa_evidence.zip` | CloudShell 업로드용 |
| `aws_upload/voc_qa_program.zip` | CloudShell 재현 실행용 (`.env` 미포함) |

---

## 1. CloudShell 열고 파일 올리기

1. AWS 콘솔 우측 상단 **CloudShell** 아이콘 클릭
2. **Actions → Upload file** 로 `qa_evidence.zip`, `voc_qa_program.zip` 업로드

```bash
ls -lh *.zip
unzip -o qa_evidence.zip
unzip -o voc_qa_program.zip -d voc_program
ls qa_evidence
```

---

## 2. 변수 설정과 신원 확인

```bash
export AWS_REGION=ap-northeast-2
export BUCKET="voc-qa-team3-$(date +%Y%m%d)-$RANDOM"
export PREFIX=team3
echo "버킷 이름: $BUCKET"

# 지금 누가 명령을 실행하고 있는가 (root가 아닌 IAM 사용자여야 함)
aws sts get-caller-identity
```

**발표 포인트** — `Arn` 이 `.../user/xxx` 형태의 IAM 사용자입니다. root가 아닙니다.

---

## 3. S3 버킷 생성

```bash
aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION"
```

**확인 값** — `Location` 에 버킷 이름이 출력됩니다. 버킷 이름은 전역에서 고유해야 합니다.

---

## 4. 퍼블릭 접근 차단과 암호화 (업로드 **전에** 설정)

```bash
# 퍼블릭 접근 4개 항목 모두 차단
aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# 기본 암호화 SSE-S3(AES256)
aws s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'
```

**순서가 중요합니다.** 파일을 먼저 올리고 나중에 잠그면, 그 사이 시간 동안 노출 위험이 남습니다.

---

## 5. QA 증적 업로드

```bash
aws s3 sync ./qa_evidence "s3://$BUCKET/$PREFIX/" --no-progress
```

**확인 값** — `upload:` 줄이 8개 출력됩니다.

---

## 6. 업로드 결과 조회

```bash
aws s3 ls "s3://$BUCKET/$PREFIX/" --human-readable --summarize
```

```bash
# 3팀 핵심 산출물 3종만 표로 확인
aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "$PREFIX/" \
  --query "Contents[?contains(Key,'judge')||contains(Key,'quality_score')||contains(Key,'deployment')].{파일:Key,크기:Size,수정시각:LastModified}" \
  --output table
```

---

## 7. 보안 설정 확인 (증적 캡처 구간)

```bash
# 4개 항목이 모두 true 여야 합니다
aws s3api get-public-access-block --bucket "$BUCKET"

# AES256 이어야 합니다
aws s3api get-bucket-encryption --bucket "$BUCKET"

# IsPublic: false 여야 합니다
aws s3api get-bucket-policy-status --bucket "$BUCKET" 2>/dev/null \
  || echo "버킷 정책 없음 → 퍼블릭 정책이 존재하지 않습니다"

# 개별 객체의 암호화·크기 확인
aws s3api head-object --bucket "$BUCKET" --key "$PREFIX/llm_judge_result.csv" \
  --query "{암호화:ServerSideEncryption,크기:ContentLength,수정시각:LastModified}" --output table
```

```bash
# 퍼블릭 URL이 실제로 막혀 있는지 확인 (AccessDenied 가 정상입니다)
curl -s -o /dev/null -w "HTTP 상태: %{http_code}\n" \
  "https://$BUCKET.s3.$AWS_REGION.amazonaws.com/$PREFIX/llm_judge_result.csv"
```

**발표 포인트** — `HTTP 상태: 403` 이 나와야 정상입니다. 200이면 즉시 보안 결함입니다.

---

## 8. 무결성 대조 (올린 파일이 그 파일이 맞는가)

```bash
# 로컬에서 만든 MANIFEST.md 의 SHA256 과 S3에서 받은 파일의 SHA256 을 비교
grep llm_judge_result.csv qa_evidence/MANIFEST.md
aws s3 cp "s3://$BUCKET/$PREFIX/llm_judge_result.csv" - | sha256sum
```

두 해시가 같으면 업로드 중 손상·변조가 없습니다.

---

## 9. AWS에 올린 프로그램을 AWS에서 실행 (시연 핵심)

S3에 보관한 프로그램을 CloudShell로 다시 내려받아, **AWS 안에서** 같은 테스트가
재현되는지 확인합니다. 32건 모두 오프라인 결정적 테스트라 **API 키도 비용도 필요 없습니다.**

```bash
# 프로그램도 같은 버킷에 보관
aws s3 cp voc_qa_program.zip "s3://$BUCKET/$PREFIX/program/voc_qa_program.zip"

# S3에서 다시 내려받아 실행 (여기부터가 'AWS에 올린 프로그램' 시연)
mkdir -p ~/voc_run && cd ~/voc_run
aws s3 cp "s3://$BUCKET/$PREFIX/program/voc_qa_program.zip" .
unzip -o -q voc_qa_program.zip

python3 -m venv .venv && source .venv/bin/activate
pip install -q grpcio protobuf "mcp>=1.2" "openai>=1.66" "anthropic>=0.39" python-dotenv pytest

python -m pytest quality_diagnosis/test_agent_unit.py \
  quality_diagnosis/test_pipeline_e2e.py quality_diagnosis/test_fault_tolerance.py \
  quality_diagnosis/test_mcp_tools.py quality_diagnosis/test_llm_judge.py \
  quality_diagnosis/test_release_defects.py -v -p no:cacheprovider
```

**확인 값** — 로컬과 동일하게 `32 passed` 가 나와야 합니다.
로컬 PC 환경에 의존하지 않는 결과라는 뜻입니다.

> `pip install` 은 1~2분 걸립니다. **녹화 전에 미리 한 번 실행**해 두고,
> 영상에서는 `pytest` 실행부터 담으세요.

---

## 10. CloudTrail 운영감사

```bash
# 버킷 생성 이력
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=CreateBucket \
  --max-results 5 \
  --query "Events[].{시각:EventTime,사용자:Username,작업:EventName}" --output table

# 퍼블릭 차단 설정 이력
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutBucketPublicAccessBlock \
  --max-results 5 \
  --query "Events[].{시각:EventTime,사용자:Username,작업:EventName}" --output table

# 내 계정에서 최근에 일어난 S3 관리 이벤트 전체
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceType,AttributeValue=AWS::S3::Bucket \
  --max-results 10 \
  --query "Events[].{시각:EventTime,사용자:Username,작업:EventName}" --output table
```

> **정확히 알고 말해야 하는 부분**
> CloudTrail 기본 이벤트 기록(90일 무료)에는 **관리 이벤트만** 남습니다.
> `CreateBucket` · `PutBucketPublicAccessBlock` · `PutBucketEncryption` · `DeleteBucket` 은 보이지만,
> **파일 업로드(`PutObject`)는 데이터 이벤트라 기본 기록에 나오지 않습니다.**
> 데이터 이벤트를 남기려면 별도 Trail이 필요하고 이번 프로젝트에서는 비용 때문에 만들지 않습니다.
> 따라서 **업로드 사실은 S3 객체 목록의 `LastModified`로**, **보안·생성·삭제 작업은 CloudTrail로** 감사합니다.

---

## 11. 전체 삭제 (과금 0 확인)

```bash
# 객체 전부 삭제
aws s3 rm "s3://$BUCKET" --recursive

# 비어 있는지 확인
aws s3 ls "s3://$BUCKET" --recursive --summarize

# 버킷 삭제
aws s3api delete-bucket --bucket "$BUCKET" --region "$AWS_REGION"

# 삭제 확인 — 빈 결과 [] 가 나와야 합니다
aws s3api list-buckets --query "Buckets[?Name=='$BUCKET']"
```

```bash
# 삭제 이력까지 감사에 남았는지 확인 (반영에 몇 분 걸릴 수 있습니다)
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteBucket \
  --max-results 3 \
  --query "Events[].{시각:EventTime,사용자:Username,작업:EventName}" --output table
```

마지막으로 **Billing → Free Tier** 화면에서 사용량이 무료 범위 안인지 확인하고 영상에 담습니다.

---

## 문제가 생겼을 때

| 증상 | 원인 | 조치 |
| --- | --- | --- |
| `BucketAlreadyExists` | 버킷 이름이 전역 중복 | `export BUCKET=...-$RANDOM` 다시 실행 |
| `IllegalLocationConstraintException` | 리전과 `LocationConstraint` 불일치 | 둘 다 `ap-northeast-2` 로 맞춤 |
| `AccessDenied` (s3api) | IAM 권한 부족 | 실습용 정책에 `s3:*` 를 해당 버킷 범위로 부여 |
| `BucketNotEmpty` | 객체가 남아 있음 | `aws s3 rm "s3://$BUCKET" --recursive` 먼저 실행 |
| CloudTrail에 이벤트 없음 | 반영 지연(최대 15분) | 잠시 후 재조회, 또는 콘솔 이벤트 기록 화면 사용 |
| CloudShell 세션 끊김 | 20분 이상 미조작 | 재접속 후 `export` 변수부터 다시 설정 |
