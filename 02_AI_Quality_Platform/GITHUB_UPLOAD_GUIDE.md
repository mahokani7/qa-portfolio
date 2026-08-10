# GitHub 업로드 매뉴얼

이 문서는 `C:\ai_quality_final_project_rule_2` 폴더를 본인의 GitHub 저장소에 처음 올리고, 이후 변경 사항을 업데이트하는 절차를 설명합니다.

## 1. 업로드 전 확인

PowerShell을 열고 프로젝트 폴더로 이동합니다.

```powershell
Set-Location C:\ai_quality_final_project_rule_2
```

다음 파일이 준비되어 있는지 확인합니다.

```powershell
Get-ChildItem README.md, .gitignore, .gitattributes, .env.example, GITHUB_UPLOAD_GUIDE.md
```

중요한 보안 원칙:

- 실제 API 키가 들어 있는 `.env`는 올리지 않습니다.
- `.venv`, `venv`, `__pycache__`, ChromaDB, 로그, 테스트 결과는 올리지 않습니다.
- 공개 저장소라면 문서·보고서·테스트 파일에 개인정보가 없는지 직접 확인합니다.

## 2. Git 설치와 계정 확인

Git이 설치되어 있는지 확인합니다.

```powershell
git --version
```

처음 사용하는 PC라면 커밋 작성자 정보를 설정합니다.

```powershell
git config --global user.name "본인 GitHub 이름"
git config --global user.email "본인 GitHub 이메일"
```

현재 설정은 다음 명령으로 확인할 수 있습니다.

```powershell
git config --global --list
```

## 3. GitHub에서 빈 저장소 만들기

1. GitHub에 로그인합니다.
2. 오른쪽 위 `+` 메뉴에서 `New repository`를 선택합니다.
3. 저장소 이름을 입력합니다. 예: `ai-quality-final-project`
4. 공개 범위는 `Public` 또는 `Private` 중 선택합니다.
5. `Add a README file`, `.gitignore`, `license`는 선택하지 않습니다. 현재 폴더에 이미 관련 파일이 있기 때문입니다.
6. `Create repository`를 누릅니다.
7. 생성된 저장소의 HTTPS 주소를 복사합니다.

주소 예시:

```text
https://github.com/GITHUB_ID/ai-quality-final-project.git
```

## 4. 현재 폴더를 처음 업로드

아래 명령을 한 줄씩 실행합니다. `GITHUB_ID`와 저장소 이름은 본인의 값으로 바꿉니다.

```powershell
git init
git branch -M main
git add .
git status
```

`git status`에서 `.env`, 가상환경 폴더, `data/knowledge/chroma_db`, `tests_output`이 표시되지 않는지 반드시 확인합니다.

문제가 없다면 첫 커밋을 만듭니다.

```powershell
git commit -m "Initial commit"
git remote add origin https://github.com/GITHUB_ID/ai-quality-final-project.git
git push -u origin main
```

GitHub 로그인 창이 열리면 브라우저 인증을 완료합니다. 비밀번호 입력을 요구하는 환경에서는 GitHub 계정 비밀번호 대신 Personal Access Token 또는 GitHub CLI 인증을 사용해야 합니다.

## 5. 이후 변경 사항 업데이트

파일을 수정한 뒤 다음 순서로 올립니다.

```powershell
git status
git add .
git status
git commit -m "변경 내용을 설명하는 메시지"
git push
```

예시:

```powershell
git commit -m "Add quality evaluation report"
```

## 6. 다른 PC에서 내려받기

```powershell
git clone https://github.com/GITHUB_ID/ai-quality-final-project.git
Set-Location ai-quality-final-project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

그다음 `.env`에 본인의 API 키를 직접 입력합니다. API 키는 GitHub에서 내려받는 대상이 아닙니다.

## 7. 자주 발생하는 문제

### `remote origin already exists`

이미 원격 주소가 등록되어 있습니다. 현재 주소를 확인하고 필요할 때만 변경합니다.

```powershell
git remote -v
git remote set-url origin https://github.com/GITHUB_ID/ai-quality-final-project.git
```

### `rejected` 또는 `fetch first`

GitHub 저장소를 만들 때 README 등을 자동 생성했을 가능성이 있습니다. 원격 변경을 먼저 합친 후 다시 올립니다.

```powershell
git pull --rebase origin main
git push
```

충돌이 발생하면 충돌 파일을 수정한 뒤 다음 명령을 실행합니다.

```powershell
git add .
git rebase --continue
git push
```

### 잘못된 파일을 `git add`한 경우

아직 커밋하지 않았다면 스테이징에서만 제거합니다. 실제 파일은 삭제되지 않습니다.

```powershell
git restore --staged 파일경로
```

전체 스테이징을 취소하려면:

```powershell
git restore --staged .
```

### `.env`를 실수로 커밋한 경우

즉시 해당 API 키와 토큰을 폐기하고 새로 발급하세요. 그다음 Git 추적에서 제거합니다.

```powershell
git rm --cached .env
git commit -m "Remove environment secrets"
git push
```

이미 공개된 비밀값은 파일을 삭제하거나 커밋을 되돌리는 것만으로 안전해지지 않습니다. 키 교체가 가장 먼저입니다.

### 파일이 너무 크다는 오류

GitHub 일반 Git 저장소는 단일 파일 크기에 제한이 있습니다. 큰 모델, 데이터베이스, 동영상 등이 필요하면 Git LFS 또는 별도 저장소를 사용합니다. 현재 프로젝트의 재생성 가능한 ChromaDB는 `.gitignore`로 제외되어 있습니다.

## 8. 최종 확인 체크리스트

- [ ] GitHub 첫 화면에 `README.md`가 정상 표시된다.
- [ ] `.env`와 API 키가 보이지 않는다.
- [ ] `venv`, `.venv`, `__pycache__`가 보이지 않는다.
- [ ] `data/knowledge/chroma_db`와 실행 로그가 보이지 않는다.
- [ ] 필요한 소스, 테스트, 원본 지식 문서가 보인다.
- [ ] 새 PC에서 `requirements.txt`로 설치할 수 있다.

