"""
report_generator.py (규칙 기반 vs API 기반 비교 대응)
- main.py가 만든 케이스별 {rule_based, api_based} 중첩 결과를 받아
  JSON, CSV, Markdown 보고서를 자동 생성합니다.
- CSV는 두 챗봇의 결과를 rule_/api_ 접두사로 나란히 플랫화하여 비교 표로 바로 활용할 수 있게 합니다.
"""

import json
from datetime import datetime
from pathlib import Path
import pandas as pd
from config import REPORTS_DIR, HISTORY_DIR
from quality.formal_report_generator import METRIC_LABELS, ITEM_PASS_THRESHOLD

AGENT_LABELS = {"rule_based": "규칙 기반 챗봇", "api_based": "API 기반 챗봇"}


def _agent_decisions(evaluation_results: list, agent_key: str) -> list:
    return [res.get(agent_key, {}).get("evaluation_result", {}).get("overall_decision", "FAIL") for res in evaluation_results]


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
        케이스당 한 행으로, 규칙 기반(rule_)/API 기반(api_) 챗봇의 결과를 나란히 플랫화하여
        CSV로 저장합니다. rule_overall_decision vs api_overall_decision 컬럼이 비교의 핵심입니다.
        """
        output_dir = output_dir or self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / filename
        try:
            flattened_data = []
            for res in evaluation_results:
                row = {
                    "case_id": res.get("case_id"),
                    "category": res.get("category"),
                    "test_type": res.get("test_type"),
                    "user_question": res.get("user_question"),
                }
                for agent_key in ("rule_based", "api_based"):
                    prefix = "rule" if agent_key == "rule_based" else "api"
                    agent_res = res.get(agent_key, {})
                    rule_val = agent_res.get("rule_validation", {})
                    eval_res = agent_res.get("evaluation_result", {})

                    row[f"{prefix}_ai_answer"] = agent_res.get("ai_answer")
                    row[f"{prefix}_rule_status"] = rule_val.get("rule_status")
                    row[f"{prefix}_rule_reason"] = rule_val.get("rule_reason")
                    row[f"{prefix}_keyword_found"] = rule_val.get("keyword_found")

                    row[f"{prefix}_accuracy_score"] = eval_res.get("accuracy", {}).get("score", 0)
                    row[f"{prefix}_accuracy_reason"] = eval_res.get("accuracy", {}).get("reason", "")
                    row[f"{prefix}_groundedness_score"] = eval_res.get("groundedness", {}).get("score", 0)
                    row[f"{prefix}_groundedness_reason"] = eval_res.get("groundedness", {}).get("reason", "")
                    row[f"{prefix}_helpfulness_score"] = eval_res.get("helpfulness", {}).get("score", 0)
                    row[f"{prefix}_helpfulness_reason"] = eval_res.get("helpfulness", {}).get("reason", "")
                    row[f"{prefix}_safety_score"] = eval_res.get("safety", {}).get("score", 0)
                    row[f"{prefix}_safety_reason"] = eval_res.get("safety", {}).get("reason", "")

                    row[f"{prefix}_overall_decision"] = eval_res.get("overall_decision", "FAIL")
                    row[f"{prefix}_summary"] = eval_res.get("summary", "")

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
        """규칙 기반/API 기반 챗봇을 비교할 수 있는 시각적인 Markdown 보고서를 작성합니다."""
        file_path = self.output_dir / filename

        total_cases = len(evaluation_results)
        if total_cases == 0:
            print("[Warning] 생성할 결과 데이터가 비어있습니다.")
            return None

        def agent_stats(agent_key: str) -> dict:
            decisions = _agent_decisions(evaluation_results, agent_key)
            pass_count = decisions.count("PASS")
            review_count = decisions.count("REVIEW")
            fail_count = decisions.count("FAIL")
            scores = {
                metric: [res.get(agent_key, {}).get("evaluation_result", {}).get(metric, {}).get("score", 0) for res in evaluation_results]
                for metric in ("accuracy", "groundedness", "helpfulness", "safety")
            }
            return {
                "pass": pass_count, "review": review_count, "fail": fail_count,
                "pass_rate": (pass_count / total_cases) * 100,
                "avg": {metric: sum(vals) / total_cases for metric, vals in scores.items()},
            }

        rule_stats = agent_stats("rule_based")
        api_stats = agent_stats("api_based")

        md_content = f"""# 📊 AI 교육과정 안내 챗봇 품질 검증 보고서 (규칙 기반 vs API 기반 비교)

본 보고서는 동일한 테스트 케이스에 대해 **규칙 기반 챗봇**과 **API 기반 챗봇**이 생성한 답변을
동일한 기준(규칙 기반 1차 검증 + AI 평가자 2차 평가)으로 채점한 비교 결과입니다.

## 📌 1. 종합 평가 요약 (챗봇 유형별)
| 지표 항목 | ⚙️ 규칙 기반 챗봇 | 🤖 API 기반 챗봇 |
| :--- | :--- | :--- |
| **총 테스트 케이스 수** | {total_cases} 개 | {total_cases} 개 |
| **성공 (PASS)** | {rule_stats['pass']} 개 | {api_stats['pass']} 개 |
| **재검토 (REVIEW)** | {rule_stats['review']} 개 | {api_stats['review']} 개 |
| **실패 (FAIL)** | {rule_stats['fail']} 개 | {api_stats['fail']} 개 |
| **최종 합격률** | {rule_stats['pass_rate']:.1f}% | {api_stats['pass_rate']:.1f}% |
| **정확성 평균** | {rule_stats['avg']['accuracy']:.2f} / 5.0 | {api_stats['avg']['accuracy']:.2f} / 5.0 |
| **근거성 평균** | {rule_stats['avg']['groundedness']:.2f} / 5.0 | {api_stats['avg']['groundedness']:.2f} / 5.0 |
| **유용성 평균** | {rule_stats['avg']['helpfulness']:.2f} / 5.0 | {api_stats['avg']['helpfulness']:.2f} / 5.0 |
| **안전성 평균** | {rule_stats['avg']['safety']:.2f} / 5.0 | {api_stats['avg']['safety']:.2f} / 5.0 |

---

## 🆚 2. 케이스별 판정 비교 표

| TC ID | 카테고리 | 유형 | 규칙기반 판정 | API기반 판정 | 일치 여부 |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
        def _dot(color: str) -> str:
            return f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{color};margin-right:5px;vertical-align:middle;"></span>'

        # 대시보드(streamlit_app.py)와 동일한 파스텔 색상을 재사용해 일관성을 맞춥니다.
        decision_dot_color = {"PASS": "#A7F3D0", "REVIEW": "#FDE68A", "FAIL": "#FECACA"}
        mismatch_dot_color = "#FED7AA"

        def _decision_badge(decision: str) -> str:
            return f"{_dot(decision_dot_color.get(decision, '#cbd5e1'))}{decision}"

        badge_map = {d: _decision_badge(d) for d in ("PASS", "REVIEW", "FAIL")}
        for res in evaluation_results:
            rule_decision = res.get("rule_based", {}).get("evaluation_result", {}).get("overall_decision", "FAIL")
            api_decision = res.get("api_based", {}).get("evaluation_result", {}).get("overall_decision", "FAIL")
            if rule_decision == api_decision:
                match_mark = f"{_dot(decision_dot_color['PASS'])}일치"
            else:
                match_mark = f"{_dot(mismatch_dot_color)}불일치"
            md_content += (
                f"| {res.get('case_id')} | {res.get('category')} | {res.get('test_type')} | "
                f"{badge_map.get(rule_decision, rule_decision)} | {badge_map.get(api_decision, api_decision)} | {match_mark} |\n"
            )

        md_content += "\n---\n\n## 🔍 3. 세부 테스트 케이스별 검증 결과\n\n"

        def render_agent_detail(agent_result: dict, heading: str) -> str:
            rule_val = agent_result.get("rule_validation", {})
            eval_res = agent_result.get("evaluation_result", {})
            decision = eval_res.get("overall_decision", "FAIL")
            badge = badge_map.get(decision, decision)
            rule_badge = (
                f"{_dot(decision_dot_color['PASS'])}PASS" if rule_val.get("rule_status") == "PASS"
                else f"{_dot(decision_dot_color['FAIL'])}FAIL"
            )
            return f"""#### {heading} — **{badge}**
- **챗봇의 답변:** {agent_result.get('ai_answer')}
- **1차 규칙 기반 검증:** {rule_badge} (키워드 발견 여부: {rule_val.get('keyword_found')}) — {rule_val.get('rule_reason')}
- **AI 심층 평가 종합 요약:** {eval_res.get('summary')}
  1. **정확성:** `{eval_res.get('accuracy', {}).get('score')}/5` ➡️ *{eval_res.get('accuracy', {}).get('reason')}*
  2. **근거성:** `{eval_res.get('groundedness', {}).get('score')}/5` ➡️ *{eval_res.get('groundedness', {}).get('reason')}*
  3. **유용성:** `{eval_res.get('helpfulness', {}).get('score')}/5` ➡️ *{eval_res.get('helpfulness', {}).get('reason')}*
  4. **안전성:** `{eval_res.get('safety', {}).get('score')}/5` ➡️ *{eval_res.get('safety', {}).get('reason')}*
"""

        for res in evaluation_results:
            md_content += f"""### [{res.get('case_id')}] {res.get('category')} 테스트 ({res.get('test_type')})
- **사용자 질문:** {res.get('user_question')}

{render_agent_detail(res.get('rule_based', {}), '⚙️ 규칙 기반 챗봇 결과')}

{render_agent_detail(res.get('api_based', {}), '🤖 API 기반 챗봇 결과')}

---
"""

        def category_pass_rates(agent_key: str) -> dict:
            cats: dict = {}
            for res in evaluation_results:
                cat = res.get("category")
                decision = res.get(agent_key, {}).get("evaluation_result", {}).get("overall_decision", "FAIL")
                cats.setdefault(cat, []).append(decision == "PASS")
            return {cat: (sum(v) / len(v) * 100) for cat, v in cats.items()}

        def fail_cases(agent_key: str) -> list:
            fails = []
            for res in evaluation_results:
                agent_res = res.get(agent_key, {})
                if agent_res.get("evaluation_result", {}).get("overall_decision") == "FAIL":
                    fails.append({
                        "case_id": res.get("case_id"),
                        "category": res.get("category"),
                        "summary": agent_res.get("evaluation_result", {}).get("summary", ""),
                    })
            return fails

        def agent_conclusion(label: str, stats: dict, agent_key: str) -> str:
            weakest_key = min(stats["avg"], key=stats["avg"].get)
            weakest_label = METRIC_LABELS.get(weakest_key, weakest_key)
            weakest_score = stats["avg"][weakest_key]
            cat_rates = category_pass_rates(agent_key)
            worst_cat = min(cat_rates, key=cat_rates.get)
            worst_rate = cat_rates[worst_cat]
            fails = fail_cases(agent_key)

            verdict = "충족" if stats["pass_rate"] >= ITEM_PASS_THRESHOLD else "미충족"
            section = f"""#### {label}
- **합격 기준({ITEM_PASS_THRESHOLD}% 이상) 충족 여부:** {verdict} (합격률 {stats['pass_rate']:.1f}%)
- **가장 취약한 지표:** {weakest_label} (평균 {weakest_score:.2f}/5.0) → 관련 프롬프트/규칙 보강 필요
- **가장 취약한 카테고리:** {worst_cat} (합격률 {worst_rate:.1f}%) → 해당 영역의 지식/규칙 데이터 보강 필요
"""
            if fails:
                section += f"- **실패(FAIL) 케이스 ({len(fails)}건):**\n"
                for f in fails:
                    section += f"  - {f['case_id']} [{f['category']}] — {f['summary']}\n"
            else:
                section += "- **실패(FAIL) 케이스:** 없음\n"
            return section

        better = (
            "규칙 기반 챗봇이" if rule_stats["pass_rate"] > api_stats["pass_rate"]
            else "API 기반 챗봇이" if api_stats["pass_rate"] > rule_stats["pass_rate"]
            else "두 챗봇이 동률로"
        )

        md_content += f"""## 🏁 4. 최종 결론 및 개선방안

### 4.1 종합 결론
전체 {total_cases}개 테스트 케이스 기준, 규칙 기반 챗봇은 합격률 **{rule_stats['pass_rate']:.1f}%**
({rule_stats['pass']}/{total_cases}), API 기반 챗봇은 합격률 **{api_stats['pass_rate']:.1f}%**
({api_stats['pass']}/{total_cases})를 기록하여 {better} 더 높은 합격률을 보였습니다.
두 챗봇 모두 합격 기준({ITEM_PASS_THRESHOLD}% 이상)을 {"충족" if max(rule_stats['pass_rate'], api_stats['pass_rate']) >= ITEM_PASS_THRESHOLD else "충족하지 못했으며, 개선 후 재검증이 필요"}합니다.

### 4.2 챗봇 유형별 개선방안

{agent_conclusion('⚙️ 규칙 기반 챗봇', rule_stats, 'rule_based')}
{agent_conclusion('🤖 API 기반 챗봇', api_stats, 'api_based')}

### 4.3 공통 개선 권고
1. **지식 베이스 보강:** 규칙 기반 챗봇의 키워드 매칭과 API 기반 챗봇의 RAG 검색이 공통으로 참조하는 지식 파일에 실제 정책 수치·규정 원문을 보강하여 두 챗봇 모두의 근거성을 높일 것.
2. **규칙 기반 챗봇 커버리지 확대:** 실패 케이스에서 나타난 질문 패턴을 `rule_based_agent.py`의 카테고리 키워드 테이블에 추가하여 사전에 정의되지 않은 질문에 대한 대응력을 높일 것.
3. **API 기반 챗봇 프롬프트 보강:** 할루시네이션이 의심되는 케이스를 중심으로 시스템 프롬프트의 근거 인용 지침을 강화할 것.
4. **회귀 테스트:** 개선 조치 적용 후 동일 테스트 케이스로 파이프라인을 재실행하여 두 챗봇의 판정이 PASS로 전환되는지 재확인할 것.

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

        def agent_meta(agent_key: str) -> dict:
            decisions = _agent_decisions(evaluation_results, agent_key)
            pass_n = decisions.count("PASS")
            return {
                "pass": pass_n,
                "review": decisions.count("REVIEW"),
                "fail": decisions.count("FAIL"),
                "pass_rate": round((pass_n / total * 100), 1) if total else 0.0,
            }

        rule_meta = agent_meta("rule_based")
        api_meta = agent_meta("api_based")

        meta = {
            "timestamp": timestamp,
            "display_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "rule_pass": rule_meta["pass"], "rule_review": rule_meta["review"],
            "rule_fail": rule_meta["fail"], "rule_pass_rate": rule_meta["pass_rate"],
            "api_pass": api_meta["pass"], "api_review": api_meta["review"],
            "api_fail": api_meta["fail"], "api_pass_rate": api_meta["pass_rate"],
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
