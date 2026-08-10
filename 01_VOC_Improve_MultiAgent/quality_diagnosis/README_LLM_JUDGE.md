# 독립 LLM Judge

파이프라인 내부 Evaluator/Critic과 별도로 최종 요약·정책을 다시 평가합니다.

평가 기준은 정확성 25, 요약 충실성 20, 정책 구체성 20, 유용성 20, 안전성 15점입니다.
중대 위반이 있으면 총점과 관계없이 즉시 배포 보류합니다.

## 비용 없는 형식 검증

```powershell
python -m unittest quality_diagnosis.test_llm_judge -v
python quality_diagnosis/llm_judge.py --provider deterministic
```

`deterministic` 결과에는 `live_llm_judge_verified: false`가 기록되며 정식 LLM 품질 승인이 아닙니다.

## 실제 Judge 실행

실제 API 키와 비용 승인을 확인한 뒤 다음 중 하나를 실행합니다.

```powershell
python quality_diagnosis/llm_judge.py --provider anthropic
python quality_diagnosis/llm_judge.py --provider openai
```

가능하면 최종 결과 생성에 가장 적게 관여한 모델을 Judge로 선택하고 사람 검토를 병행합니다.
