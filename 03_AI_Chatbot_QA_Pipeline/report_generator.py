"""
report_generator.py (수정본)
- 변경된 실행 결과 스키마(rule_validation 객체 및 evaluation_result 상세 지표 구조)를 반영하여
  JSON, CSV, Markdown 보고서를 자동 생성합니다.
"""

import json
from datetime import datetime
from pathlib import Path
import pandas as pd
from config import REPORTS_DIR, HISTORY_DIR

class ReportGenerator:
    def __init__(self):
        """ReportGenerator 초기화 및 저장 폴더 확인"""
        self.output_dir = REPORTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_json_report(self, evaluation_results: list, filename: str = "evaluation_result.json", output_dir: Path = None) -> Path:
        """평가 결과 리스트를 JSON 파일로 저장합니다."""
        output_dir = output_dir or self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / filename
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(evaluation_results, f, ensure_ascii=False, indent=2)
            print(f"[Success] JSON 리포트 생성 완료: {file_path}")
            return file_path
        except Exception as e:
            print(f"[Error] JSON 리포트 생성 중 오류 발생: {e}")
            return None

    def generate_csv_report(self, evaluation_results: list, filename: str = "evaluation_result.csv", output_dir: Path = None) -> Path:
        """
        중첩된 JSON 객체 구조를 1차원 표 형태로 변환하여 CSV 파일로 저장합니다.
        (Streamlit 대시보드 연동 및 Excel 가독성 최적화)
        """
        output_dir = output_dir or self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / filename
        try:
            flattened_data = []
            for res in evaluation_results:
                rule_val = res.get("rule_validation", {})
                eval_res = res.get("evaluation_result", {})
                
                # 중첩 구조를 평탄화(Flatten)하여 딕셔너리로 재구성
                row = {
                    "case_id": res.get("case_id"),
                    "category": res.get("category"),
                    "test_type": res.get("test_type"),
                    "user_question": res.get("user_question"),
                    "ai_answer": res.get("ai_answer"),
                    
                    # 1차 검증 결과
                    "rule_status": rule_val.get("rule_status"),
                    "rule_reason": rule_val.get("rule_reason"),
                    "keyword_found": rule_val.get("keyword_found"),
                    
                    # AI 4대 지표 점수 및 상세 사유
                    "accuracy_score": eval_res.get("accuracy", {}).get("score", 0),
                    "accuracy_reason": eval_res.get("accuracy", {}).get("reason", ""),
                    "groundedness_score": eval_res.get("groundedness", {}).get("score", 0),
                    "groundedness_reason": eval_res.get("groundedness", {}).get("reason", ""),
                    "helpfulness_score": eval_res.get("helpfulness", {}).get("score", 0),
                    "helpfulness_reason": eval_res.get("helpfulness", {}).get("reason", ""),
                    "safety_score": eval_res.get("safety", {}).get("score", 0),
                    "safety_reason": eval_res.get("safety", {}).get("reason", ""),
                    
                    # 최종 결과 요약
                    "overall_decision": eval_res.get("overall_decision", "FAIL"),
                    "summary": eval_res.get("summary", "")
                }
                flattened_data.append(row)
            
            df = pd.DataFrame(flattened_data)
            # UTF-8-SIG 인코딩으로 저장하여 한글 엑셀 깨짐을 방지합니다.
            df.to_csv(file_path, index=False, encoding="utf-8-sig")
            print(f"[Success] CSV 리포트 생성 완료: {file_path}")
            return file_path
        except Exception as e:
            print(f"[Error] CSV 리포트 생성 중 오류 발생: {e}")
            return None

    def generate_markdown_report(self, evaluation_results: list, filename: str = "final_quality_report.md") -> Path:
        """한눈에 품질 현황을 파악할 수 있는 시각적인 Markdown 보고서를 작성합니다."""
        file_path = self.output_dir / filename
        
        total_cases = len(evaluation_results)
        if total_cases == 0:
            print("[Warning] 생성할 결과 데이터가 비어있습니다.")
            return None

        # 통계 데이터 추출을 위한 리스트 컴프리헨션
        decisions = [res.get("evaluation_result", {}).get("overall_decision", "FAIL") for res in evaluation_results]
        pass_count = decisions.count("PASS")
        review_count = decisions.count("REVIEW")
        fail_count = decisions.count("FAIL")
        pass_rate = (pass_count / total_cases) * 100

        # 지표별 스코어 평균 계산
        accuracy_scores = [res.get("evaluation_result", {}).get("accuracy", {}).get("score", 0) for res in evaluation_results]
        grounded_scores = [res.get("evaluation_result", {}).get("groundedness", {}).get("score", 0) for res in evaluation_results]
        helpful_scores = [res.get("evaluation_result", {}).get("helpfulness", {}).get("score", 0) for res in evaluation_results]
        safety_scores = [res.get("evaluation_result", {}).get("safety", {}).get("score", 0) for res in evaluation_results]

        avg_accuracy = sum(accuracy_scores) / total_cases
        avg_grounded = sum(grounded_scores) / total_cases
        avg_helpful = sum(helpful_scores) / total_cases
        avg_safety = sum(safety_scores) / total_cases

        md_content = f"""# 📊 AI 교육과정 안내 챗봇 품질 검증 보고서

본 보고서는 자동화 퀄리티 QA 파이프라인의 인공지능 정밀 평가 및 규칙 기반 1차 검증을 거친 최종 보고서입니다.

## 📌 1. 종합 평가 요약
| 지표 항목 | 결과 내용 |
| :--- | :--- |
| **총 테스트 케이스 수** | {total_cases} 개 |
| **성공 (PASS)** | <span style="color:green">**{pass_count} 개**</span> |
| **재검토 (REVIEW)** | <span style="color:orange">**{review_count} 개**</span> |
| **실패 (FAIL)** | <span style="color:red">**{fail_count} 개**</span> |
| **최종 합격률 (Pass Rate)** | **{pass_rate:.1f}%** |

## 📈 2. 4대 AI 평가 지표 평균 점수 (5점 만점)
- 🎯 **정확성 (Accuracy):** `{avg_accuracy:.2f} / 5.0`
- 🪵 **근거성 (Groundedness):** `{avg_grounded:.2f} / 5.0`
- 💡 **유용성 (Helpfulness):** `{avg_helpful:.2f} / 5.0`
- 🛡️ **안전성 (Safety):** `{avg_safety:.2f} / 5.0`

---

## 🔍 3. 세부 테스트 케이스별 검증 결과

"""
        for res in evaluation_results:
            rule_val = res.get("rule_validation", {})
            eval_res = res.get("evaluation_result", {})
            decision = eval_res.get("overall_decision", "FAIL")
            
            # 판정 상태에 따른 이모지 뱃지 처리
            badge = "✅ PASS" if decision == "PASS" else ("⚠️ REVIEW" if decision == "REVIEW" else "❌ FAIL")
            rule_badge = "🟢 PASS" if rule_val.get("rule_status") == "PASS" else "🔴 FAIL"

            md_content += f"""### [{res.get('case_id')}] {res.get('category')} 테스트 ({res.get('test_type')})
- **최종 판정:** **{badge}**
- **사용자 질문:** {res.get('user_question')}
- **챗봇의 답변 (AI Answer):** {res.get('ai_answer')}

#### ⚙️ 1차 규칙 기반 검증 (Rule Validation)
- **상태:** {rule_badge} (키워드 발견 여부: {rule_val.get('keyword_found')})
- **검증 상세:** {rule_val.get('rule_reason')}

#### 🧠 AI 심층 평가 결과 (Evaluation Detail)
- **종합 요약:** {eval_res.get('summary')}
- **평가 지표 스코어 및 근거:**
  1. **정확성 (Accuracy):** `{eval_res.get('accuracy', {}).get('score')}/5` ➡️ *{eval_res.get('accuracy', {}).get('reason')}*
  2. **근거성 (Groundedness):** `{eval_res.get('groundedness', {}).get('score')}/5` ➡️ *{eval_res.get('groundedness', {}).get('reason')}*
  3. **유용성 (Helpfulness):** `{eval_res.get('helpfulness', {}).get('score')}/5` ➡️ *{eval_res.get('helpfulness', {}).get('reason')}*
  4. **안전성 (Safety):** `{eval_res.get('safety', {}).get('score')}/5` ➡️ *{eval_res.get('safety', {}).get('reason')}*

---
"""

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"[Success] Markdown 리포트 생성 완료: {file_path}")
            return file_path
        except Exception as e:
            print(f"[Error] Markdown 리포트 생성 중 오류 발생: {e}")
            return None

    def archive_run(self, evaluation_results: list) -> dict:
        """
        현재 실행 결과를 타임스탬프 폴더(reports/history/<timestamp>/)에 JSON·CSV로 보관하여
        대시보드의 '테스트 히스토리' 목록에서 과거 실행 결과를 선택해 조회할 수 있게 합니다.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = HISTORY_DIR / timestamp

        self.generate_json_report(evaluation_results, output_dir=run_dir)
        self.generate_csv_report(evaluation_results, output_dir=run_dir)

        total = len(evaluation_results)
        decisions = [res.get("evaluation_result", {}).get("overall_decision", "FAIL") for res in evaluation_results]
        pass_n = decisions.count("PASS")
        meta = {
            "timestamp": timestamp,
            "display_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "pass": pass_n,
            "review": decisions.count("REVIEW"),
            "fail": decisions.count("FAIL"),
            "pass_rate": round((pass_n / total * 100), 1) if total else 0.0,
        }
        (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Success] 실행 결과 히스토리 저장 완료: {run_dir}")
        return meta


def list_archived_runs() -> list:
    """
    보관된 실행 이력을 최신순으로 반환합니다.
    히스토리가 아직 하나도 없다면(과거 버전에서 생성된 reports/evaluation_result.csv만 있는 경우),
    해당 파일을 '아카이브 이전' 단일 항목으로 대체하여 목록이 비어 보이지 않게 합니다.
    """
    runs = []
    if HISTORY_DIR.exists():
        for run_dir in sorted(HISTORY_DIR.iterdir(), reverse=True):
            meta_path = run_dir / "meta.json"
            csv_path = run_dir / "evaluation_result.csv"
            json_path = run_dir / "evaluation_result.json"
            if not (meta_path.exists() and csv_path.exists()):
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            meta["csv_path"] = csv_path
            meta["json_path"] = json_path
            runs.append(meta)

    if not runs:
        legacy_csv = REPORTS_DIR / "evaluation_result.csv"
        legacy_json = REPORTS_DIR / "evaluation_result.json"
        if legacy_csv.exists():
            mtime = datetime.fromtimestamp(legacy_csv.stat().st_mtime)
            runs.append({
                "timestamp": "legacy",
                "display_time": mtime.strftime("%Y-%m-%d %H:%M:%S") + " (아카이브 이전 결과)",
                "csv_path": legacy_csv,
                "json_path": legacy_json,
            })
    return runs


# 변경된 데이터 스키마 독립 실행 테스트 코드
if __name__ == "__main__":
    print("--- Report Generator 수정본 테스트 ---")
    
    # 전달해주신 데이터 규격과 동일한 Mock 데이터 설정
    sample_pipeline_output = [
        {
            "case_id": "TC-001",
            "category": "정확성",
            "test_type": "Happy",
            "user_question": "이 교육과정은 총 몇 시간인가요?",
            "ai_answer": "AI 기반 SW 테스터 및 품질관리 실무 과정은 총 320시간으로 구성되어 있습니다.",
            "rule_validation": {
                "keyword_found": True,
                "rule_status": "PASS",
                "rule_reason": "예상 핵심 키워드 '320시간'가 답변에 포함되어 있습니다."
            },
            "evaluation_result": {
                "accuracy": {
                    "score": 5,
                    "reason": "기준 정보의 총 교육시간 320시간과 일치합니다."
                },
                "groundedness": {
                    "score": 5,
                    "reason": "제공된 교육과정 기준 정보에 근거한 답변입니다."
                },
                "helpfulness": {
                    "score": 5,
                    "reason": "사용자의 질문에 직접적이고 명확하게 답했습니다."
                },
                "safety": {
                    "score": 5,
                    "reason": "위험하거나 과장된 표현이 없습니다."
                },
                "overall_decision": "PASS",
                "summary": "교육시간을 정확하게 안내한 정상 답변입니다."
            }
        }
    ]
    
    reporter = ReportGenerator()
    reporter.generate_json_report(sample_pipeline_output)
    reporter.generate_csv_report(sample_pipeline_output)
    reporter.generate_markdown_report(sample_pipeline_output)