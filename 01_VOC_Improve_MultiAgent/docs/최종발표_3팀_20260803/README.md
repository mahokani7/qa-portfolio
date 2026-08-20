# 3팀 최종 발표 산출물 — LLM Judge 품질평가팀

**주제**: AWS 기반 VOC 멀티 에이전트 QA 결과관리 및 운영감사
**발표일**: 2026.08.03 · **분량**: 10분 · **팀 역할**: 3팀 LLM Judge 품질평가

---

## 산출물 목록

| 파일 | 용도 |
| --- | --- |
| [`../FINAL_PRESENTATION.pptx`](../FINAL_PRESENTATION.pptx) / [`.pdf`](../FINAL_PRESENTATION.pdf) | **최종 발표자료 11장** (2026-08-04 최종 수정, 녹화 시나리오의 발표 기준 자료) |
| [`발표대본_10분.md`](발표대본_10분.md) | 슬라이드별 대사·시간배분·예상 질문 |
| [`oCam_녹화_시나리오.md`](oCam_녹화_시나리오.md) | 녹화 설정·체크리스트·타임라인·편집 규격 |
| [`AWS_시연_명령어.md`](AWS_시연_명령어.md) | CloudShell 복붙용 명령 전체 |
| `../../aws_upload/qa_evidence/` | S3에 올릴 QA 증적 8종 |
| `../../aws_upload/qa_evidence.zip` | CloudShell 업로드용 증적 묶음 |
| `../../aws_upload/voc_qa_program.zip` | CloudShell 재현 실행용 프로그램 (`.env` 미포함) |

## 재생성 명령

```powershell
cd C:\qaeduc2\VOC_Improve_1
.venv\Scripts\python.exe scripts\build_aws_evidence.py    # 증적 8종 생성 (pytest 포함)
.venv\Scripts\python.exe scripts\pack_for_cloudshell.py   # 업로드용 ZIP 2개
.venv\Scripts\python.exe scripts\build_team3_deck.py      # 발표자료 PPTX
```

발표자료의 모든 숫자는 `aws_upload/qa_evidence/` 의 실제 증적 파일에서 읽어 채웁니다.
증적을 다시 만들면 슬라이드 숫자도 함께 갱신됩니다.

## 날짜와 점수 해석

- `90.6 / 89.0`: 2026-07-15 종합 품질평가의 과거 기준선
- `90.9 / 81.2`: 2026-07-16 라이브 E2E 및 최신 보관 Anthropic Judge 결과
- `2026-08-03`: pytest 재검증 및 최초 AWS 제출 패키지 생성일
- `2026-08-04`: 날짜 표기를 보완한 정정 패키지 생성일
- 2026-08-03에는 라이브 E2E와 Judge를 새로 실행하지 않았습니다.

---

## 발표 핵심 수치

| 항목 | 값 | 근거 파일 |
| --- | --- | --- |
| pytest 자동 테스트 | **32/32 PASS** | `pytest_result.txt` |
| 장애 진단 | 9/9 PASS | `deployment_decision.md` |
| 라이브 E2E | 18/18 PASS · 평균 **90.9** · 2026-07-16 실행 | `quality_score_report.md` |
| 독립 LLM Judge | 18건 · 평균 **81.2** · 2026-07-16 실행 | `llm_judge_result.csv` |
| Judge 모델 | Anthropic `claude-sonnet-4-6` (실제 호출) | `llm_judge_result.json` |
| 배포 기준 | **95.0** | `deployment_decision.md` |
| 중대 위반 | 0건 | `llm_judge_result.csv` |
| **최종 판정** | **배포 보류 (HOLD)** | `deployment_decision.md` |

### 항목별 Judge 점수

| 평가 항목 | 획득 | 배점 | 획득률 |
| --- | ---: | ---: | ---: |
| 정확성 | 21.33 | 25 | 85% |
| 요약 충실성 | 16.33 | 20 | 82% |
| **정책 구체성** | **14.72** | 20 | **74%** ← 최저 |
| 유용성 | 15.22 | 20 | 76% |
| 안전성 | 13.61 | 15 | 91% |

### 판정 분포 (18건)

- 조건부 배포 보류 13건 (72%) · 주요 개선 필요 4건 (22%) · 배포 보류 1건 (6%)
- **배포 가능 판정 0건**

---

## 발표 한 줄 요약

> pytest 32건은 전부 통과했지만, 독립 LLM Judge 평균은 81.2점으로 배포 기준 95점에
> 미달했습니다. **테스트 통과와 배포 승인은 다른 판단이며**, 그 판정 증적을 S3에
> 퍼블릭 차단·암호화 상태로 보관하고 CloudTrail로 감사한 뒤 전부 삭제했습니다.

---

## 준비 순서 (권장)

1. `발표대본_10분.md` 를 읽으며 **슬라이드 넘기는 타이밍**만 먼저 맞춰봅니다 (1회).
2. `AWS_시연_명령어.md` 를 CloudShell에서 **끝까지 한 번 실행**해 봅니다 (녹화 없이).
   - 이때 `pip install` 까지 끝내두면 본 녹화가 훨씬 빨라집니다.
3. `oCam_녹화_시나리오.md` 의 **녹화 전 체크리스트**를 그대로 따라 화면을 정리합니다.
4. 30초 **테스트 녹화** 후 소리를 확인합니다.
5. 테이크 A → B → C → D 순으로 촬영하고 이어붙입니다.
6. 제출 전 **보안 확인 항목**(API 키·계정 ID 노출)을 반드시 다시 봅니다.
