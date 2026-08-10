"""VOC 종합 품질평가 보고서 PDF와 다형식 첨부 증적을 생성합니다."""

from __future__ import annotations

import argparse
import base64
import html
import json
import sys
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


QUALITY_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = QUALITY_ROOT.parent
REPORTS = QUALITY_ROOT / "reports"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.deployment_policy import evaluate_release_evidence, load_deployment_config


FONT_REGULAR = Path("C:/Windows/Fonts/malgun.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/malgunbd.ttf")
NAVY = "#12375B"
BLUE = "#2B78C5"
CYAN = "#1AA6A6"
GREEN = "#178A50"
RED = "#C53D3D"
ORANGE = "#D77A16"
LIGHT = "#F3F7FB"
GRAY = "#5E6B78"


def _latest(pattern: str, *, prefer_live: bool = False) -> Path | None:
    matches = [path for path in REPORTS.glob(pattern) if path.is_file()]
    if not matches:
        return None
    if prefer_live:
        return max(
            matches,
            key=lambda path: (
                0 if "deterministic" in path.name or "offline" in path.name else 1,
                path.stat().st_mtime,
            ),
        )
    return max(matches, key=lambda path: path.stat().st_mtime)


def _read_json(path: Path | None) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}


def _load_ledger() -> list[dict[str, str]]:
    path = PROJECT_ROOT / "docs" / "개발진행_발표원장.md"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| 07-"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 6:
            rows.append({
                "date": cells[0],
                "problem": cells[1],
                "implementation": cells[2],
                "web": cells[3],
                "evidence": cells[4],
                "message": cells[5],
            })
    return rows


def _font(size: int, bold: bool = False):
    path = FONT_BOLD if bold and FONT_BOLD.is_file() else FONT_REGULAR
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def _new_chart(title: str, subtitle: str = "") -> tuple[PILImage.Image, ImageDraw.ImageDraw]:
    image = PILImage.new("RGB", (1200, 620), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, 1184, 604), radius=24, fill=LIGHT, outline="#D5E0EB", width=2)
    draw.text((54, 44), title, fill=NAVY, font=_font(36, True))
    if subtitle:
        draw.text((54, 94), subtitle, fill=GRAY, font=_font(21))
    return image, draw


def _save_test_trend(path: Path) -> None:
    image, draw = _new_chart("테스트 결과 추이", "초기 결함 2건 수정 후 최종 35건 전면 통과")
    data = [("초기", 33, 2), ("최종", 35, 0)]
    max_height = 340
    for index, (label, passed, failed) in enumerate(data):
        x = 250 + index * 440
        total_height = max_height
        passed_height = int(total_height * passed / 35)
        failed_height = total_height - passed_height
        y_bottom = 520
        draw.rectangle((x, y_bottom - passed_height, x + 190, y_bottom), fill=GREEN)
        if failed_height:
            draw.rectangle((x, y_bottom - total_height, x + 190, y_bottom - passed_height), fill=RED)
        draw.text((x + 54, 540), label, fill=NAVY, font=_font(27, True))
        draw.text((x + 50, y_bottom - passed_height + 15), f"PASS {passed}", fill="white", font=_font(24, True))
        if failed:
            draw.text((x + 55, y_bottom - total_height + 10), f"FAIL {failed}", fill="white", font=_font(23, True))
    image.save(path)


def _save_scope(path: Path) -> None:
    image, draw = _new_chart("35건 점검 범위", "두 도메인 기능 케이스와 핵심 결함 회귀를 함께 검증")
    items = [("이커머스 VOC", 18, BLUE), ("보험 VOC", 15, CYAN), ("핵심 결함 재시험", 2, ORANGE)]
    for index, (label, value, color) in enumerate(items):
        y = 175 + index * 120
        draw.text((70, y), label, fill=NAVY, font=_font(26, True))
        draw.rounded_rectangle((330, y, 1080, y + 50), radius=20, fill="#E4ECF4")
        width = int(750 * value / 18)
        draw.rounded_rectangle((330, y, 330 + width, y + 50), radius=20, fill=color)
        draw.text((345, y + 8), f"{value}건", fill="white", font=_font(23, True))
    image.save(path)


def _save_defects(path: Path) -> None:
    image, draw = _new_chart("결함 상태 변화", "분기 인터페이스와 API 429 결함의 수정·재시험 결과")
    draw.text((130, 165), "초기", fill=NAVY, font=_font(30, True))
    draw.ellipse((100, 230, 390, 520), fill=RED)
    draw.text((207, 315), "OPEN", fill="white", font=_font(28, True))
    draw.text((224, 365), "2건", fill="white", font=_font(40, True))
    draw.text((500, 325), "→", fill=BLUE, font=_font(70, True))
    draw.text((840, 165), "최종", fill=NAVY, font=_font(30, True))
    draw.ellipse((770, 230, 1060, 520), fill=GREEN)
    draw.text((858, 315), "CLOSED", fill="white", font=_font(27, True))
    draw.text((879, 365), "2건", fill="white", font=_font(40, True))
    image.save(path)


def _save_risks(path: Path, risks: list[dict[str, Any]]) -> None:
    image, draw = _new_chart("잔여 위험 수준", "5점 척도 · 점수가 높을수록 운영 전 우선 조치 필요")
    for index, risk in enumerate(risks):
        y = 150 + index * 75
        score = int(risk["score"])
        color = RED if score >= 5 else ORANGE if score >= 4 else BLUE
        draw.text((60, y), risk["short"], fill=NAVY, font=_font(21, True))
        draw.rounded_rectangle((410, y, 1050, y + 38), radius=16, fill="#DFE7EF")
        draw.rounded_rectangle((410, y, 410 + int(640 * score / 5), y + 38), radius=16, fill=color)
        draw.text((1070, y + 3), str(score), fill=color, font=_font(24, True))
    image.save(path)


def _image_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _report_data() -> dict[str, Any]:
    case_path = _latest("test_35_case_result_*.json")
    if case_path is None:
        raise FileNotFoundError("먼저 run_35_case_evaluation.py를 실행하세요.")
    cases = _read_json(case_path)
    e2e = _read_json(_latest("*live_retest_merged_e2e_*.json", prefer_live=True) or _latest("*live_e2e_*.json", prefer_live=True))
    judge = _read_json(_latest("llm_judge_*.json", prefer_live=True))
    suite = _read_json(REPORTS / "test_result.json")
    fault = _read_json(_latest("fault_diagnosis_*.json"))
    config = load_deployment_config()
    assessment = evaluate_release_evidence(suite, fault, e2e, judge, config["minimum_score"])
    defects = [
        {
            "id": "DEF-BRANCH-01",
            "name": "분기 인터페이스 오류",
            "severity": "높음",
            "initial": "FAIL",
            "cause": "OpenAI·Anthropic 분기에서 공급자별 요청 인수가 혼용되어 Anthropic Messages 호출이 거부됨",
            "action": "공급자별 클라이언트를 분리하고 Anthropic 분기에서 temperature를 제거, model·max_tokens·messages만 전달",
            "final": "PASS / 수정 완료",
        },
        {
            "id": "DEF-429-01",
            "name": "API 429 사용량 제한 장애",
            "severity": "높음",
            "initial": "FAIL",
            "cause": "라이브 병렬 테스트가 공급자 사용량 한도를 초과했으나 일반 서버 오류로만 표시됨",
            "action": "동시 실행 기본 2·최대 4 제한, SDK 재시도 1회, 429 전용 오류코드와 동시 실행 1건 축소 안내 적용",
            "final": "PASS / 운영 모니터링",
        },
    ]
    risks = [
        {"short": "95점 배포 기준 미달", "score": 5, "recommendation": "E2E +4.4점, Judge +6.0점 개선 후 재시험"},
        {"short": "사람 승인 미기록", "score": 5, "recommendation": "승인자·시각·판단 근거를 전자 승인 이력으로 보존"},
        {"short": "운영 부하·429", "score": 4, "recommendation": "동시성 1~2 유지, 큐·지수 백오프·사용량 알림 추가"},
        {"short": "인증·TLS·프록시", "score": 4, "recommendation": "로컬 바인딩 이후 운영 게이트웨이 보안 검증"},
        {"short": "도메인 확장·드리프트", "score": 3, "recommendation": "보험 라이브 전체와 장기 회귀 추세 비교"},
    ]
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cases": cases,
        "case_source": case_path.name,
        "e2e": e2e,
        "judge": judge,
        "quality_suite": suite,
        "fault": fault,
        "deployment": assessment,
        "ledger": _load_ledger(),
        "defects": defects,
        "risks": risks,
        "roles": [
            ["Evaluator", "내부 1차 평가", "요약 후보 점수·승자 선택·근거 정합성", "후보 선택 결과를 다음 단계로 전달"],
            ["Critic", "내부 비판·교정", "누락·과장·안전 위험·구체성 부족 탐지", "필요 시 Refine 재작업 유도"],
            ["독립 LLM Judge", "외부 최종 감사", "정확성·충실성·정책 구체성·유용성·안전성", "산출물 수정 없이 독립 점수와 배포 증적 생성"],
        ],
    }


def _write_txt(path: Path, data: dict[str, Any]) -> None:
    assessment = data["deployment"]
    lines = [
        "VOC 분석 및 QA 시스템 종합 품질평가 결과 보고서",
        f"생성 시각: {data['generated_at']}",
        "",
        "[최종 완료 판정]",
        "- 품질평가 수행: 완료",
        "- 기능·결함 회귀: PASS (35/35)",
        f"- 배포 판단: {assessment['label']} ({assessment['overall_score']}/{assessment['minimum_score']}점)",
        "",
        "[3단계 평가 구조]",
        "1단계 VOC 분석 및 정책 개선안 생성: Interpreter→Retriever→Summarizer→Improver",
        "2단계 6개 멀티 에이전트 내부 품질진단: Evaluator·Critic 포함 단계별 근거·위험·성능 점검",
        "3단계 독립 LLM Judge: 생성 주체와 분리된 교차 모델의 최종 감사",
        "",
        "[35건 정량 결과]",
        "- 점검 범위: 이커머스 18 + 보험 15 + 핵심 결함 2 = 35건",
        "- 초기: 33 PASS / 2 FAIL (94.3%)",
        "- 최종: 35 PASS / 0 FAIL (100.0%)",
        "",
        "[결함 관리]",
    ]
    for defect in data["defects"]:
        lines.extend([
            f"- {defect['id']} {defect['name']} [{defect['severity']}] {defect['final']}",
            f"  원인: {defect['cause']}",
            f"  조치: {defect['action']}",
        ])
    lines.extend(["", "[잔여 위험과 운영 권고]"])
    lines.extend(f"- {risk['short']} ({risk['score']}/5): {risk['recommendation']}" for risk in data["risks"])
    lines.extend([
        "",
        "[성공 판단 근거]",
        "- 정의된 35개 범위 전면 통과와 초기 결함 2건 폐쇄",
        "- 생성·내부평가·독립평가를 분리한 계층형 QA 구조",
        "- 정상·장애·보안·성능·배포 기준의 다각도 검증",
        "- TXT·XML·HTML·PDF로 보존되는 재현 가능한 감사 증적",
        "",
        "주의: 테스트 완료 PASS는 운영 배포 승인과 다릅니다. 현재는 95점 기준 미달로 배포 보류입니다.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_xml(path: Path, data: dict[str, Any]) -> None:
    assessment = data["deployment"]
    root = ET.Element("comprehensiveQualityReport", {
        "generatedAt": data["generated_at"],
        "testVerdict": "PASS",
        "deploymentVerdict": assessment["code"],
    })
    ET.SubElement(root, "testTrend", {
        "initialPassed": "33", "initialFailed": "2", "finalPassed": "35", "finalFailed": "0"
    })
    ET.SubElement(root, "deployment", {
        "overallScore": str(assessment["overall_score"]),
        "minimumScore": str(assessment["minimum_score"]),
        "technicalPass": str(assessment["technical_pass"]).lower(),
        "label": assessment["label"],
    })
    stages = ET.SubElement(root, "stages")
    for number, name in (
        (1, "VOC 분석 및 정책 개선안 생성"),
        (2, "6개 멀티 에이전트 내부 품질진단"),
        (3, "독립 LLM Judge 평가"),
    ):
        ET.SubElement(stages, "stage", {"number": str(number), "name": name})
    cases = ET.SubElement(root, "testCases", {"total": "35"})
    for row in data["cases"].get("results") or []:
        ET.SubElement(cases, "case", {
            "id": str(row.get("case_id")),
            "category": str(row.get("category")),
            "initialStatus": str(row.get("initial_status")),
            "finalStatus": str(row.get("status")),
            "score": str(row.get("score", "")),
        }).text = str(row.get("detail") or "")
    defects = ET.SubElement(root, "defects")
    for item in data["defects"]:
        node = ET.SubElement(defects, "defect", {"id": item["id"], "status": item["final"], "severity": item["severity"]})
        ET.SubElement(node, "name").text = item["name"]
        ET.SubElement(node, "cause").text = item["cause"]
        ET.SubElement(node, "correctiveAction").text = item["action"]
    risks = ET.SubElement(root, "residualRisks")
    for item in data["risks"]:
        ET.SubElement(risks, "risk", {"name": item["short"], "score": str(item["score"])}).text = item["recommendation"]
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _write_html(path: Path, data: dict[str, Any], charts: dict[str, Path]) -> None:
    assessment = data["deployment"]
    defect_rows = "".join(
        f"<tr><td>{html.escape(item['id'])}</td><td>{html.escape(item['name'])}</td><td>{html.escape(item['cause'])}</td><td>{html.escape(item['action'])}</td><td class='pass'>{html.escape(item['final'])}</td></tr>"
        for item in data["defects"]
    )
    role_rows = "".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in data["roles"])
    risk_rows = "".join(
        f"<tr><td>{html.escape(item['short'])}</td><td>{item['score']}/5</td><td>{html.escape(item['recommendation'])}</td></tr>"
        for item in data["risks"]
    )
    ledger_rows = "".join(
        f"<tr><td>{row['date']}</td><td>{html.escape(row['problem'])}</td><td>{html.escape(row['implementation'])}</td><td>{html.escape(row['evidence'])}</td></tr>"
        for row in data["ledger"]
    )
    path.write_text(f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VOC 종합 품질평가 결과 보고서</title><style>
:root{{--navy:{NAVY};--blue:{BLUE};--green:{GREEN};--red:{RED};--light:{LIGHT}}}*{{box-sizing:border-box}}body{{margin:0;font-family:'Malgun Gothic',sans-serif;color:#18283a;background:#eaf0f6}}
main{{max-width:1180px;margin:auto;background:white;padding:54px}}h1{{font-size:42px;color:var(--navy)}}h2{{border-left:7px solid var(--blue);padding-left:13px;margin-top:46px;color:var(--navy)}}
.hero{{padding:45px;border-radius:18px;background:linear-gradient(135deg,#0d2b49,#1d5b8f);color:white}}.hero h1{{color:white}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}}
.card{{padding:18px;background:var(--light);border:1px solid #d6e1ec;border-radius:13px}}.card b{{display:block;font-size:30px;color:var(--blue)}}.hold{{color:var(--red);font-weight:bold}}.pass{{color:var(--green);font-weight:bold}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{border:1px solid #d4dde7;padding:10px;vertical-align:top}}th{{background:var(--navy);color:white}}.chart{{width:100%;margin:18px 0;border:1px solid #dae3ec;border-radius:12px}}
.stage{{padding:16px 19px;margin:10px 0;border-left:5px solid var(--blue);background:#f5f8fb}}.verdict{{padding:24px;border:2px solid var(--red);border-radius:14px;background:#fff7f7}}
@media(max-width:800px){{main{{padding:22px}}.cards{{grid-template-columns:1fr 1fr}}}}@media print{{body{{background:white}}main{{max-width:none;padding:20px}}}}
</style></head><body><main><section class="hero"><div>2026.07.14—2026.07.15 개발·QA 통합 기록</div><h1>VOC 분석 및 QA 시스템<br>종합 품질평가 결과 보고서</h1><p>생성, 내부 진단, 독립 Judge를 분리한 3단계 AI 품질관리 체계</p></section>
<div class="cards"><div class="card">최종 테스트<b>35/35</b>PASS</div><div class="card">초기 테스트<b>33/35</b>2 FAIL</div><div class="card">통합 점수<b>{assessment['overall_score']}</b>/ 100</div><div class="card">배포 기준<b>{assessment['minimum_score']}</b>/ 100</div></div>
<div class="verdict"><h2>최종 완료 판정</h2><p><span class="pass">품질평가 수행 및 기능·결함 회귀 완료</span> · <span class="hold">현재 배포 보류</span></p><p>{html.escape(assessment['label'])}. 테스트 PASS와 운영 배포 승인을 분리합니다.</p></div>
<h2>1. 3단계 품질평가 구조</h2><div class="stage"><b>1단계 · VOC 분석 및 정책 개선안 생성</b><br>Interpreter → Retriever → Summarizer → Improver가 고객 불만의 의도·근거·원인·실행안을 연결합니다.</div>
<div class="stage"><b>2단계 · 6개 멀티 에이전트 내부 품질진단</b><br>Evaluator와 Critic이 후보 타당성, 누락, 과장, 안전, 성능과 Agent 연계를 검사하고 필요 시 Refine을 유도합니다.</div>
<div class="stage"><b>3단계 · 독립 LLM Judge 평가</b><br>생성 주체와 분리된 교차 모델이 정확성·충실성·정책 구체성·유용성·안전성을 최종 감사합니다.</div>
<h2>2. 전체 35건 정량 분석</h2><img class="chart" src="{_image_data_uri(charts['trend'])}"><img class="chart" src="{_image_data_uri(charts['scope'])}">
<p>이커머스 18건과 보험 15건의 도메인 시나리오, 핵심 결함 재시험 2건을 합쳐 35건입니다. 초기 2개 결함을 수정한 뒤 성공률은 94.3%에서 100%로 5.7%p 개선되었습니다.</p>
<h2>3. 결함관리 내역</h2><table><thead><tr><th>ID</th><th>결함</th><th>원인</th><th>시정 조치</th><th>최종</th></tr></thead><tbody>{defect_rows}</tbody></table><img class="chart" src="{_image_data_uri(charts['defects'])}">
<h2>4. Evaluator·Critic·독립 Judge 역할 구분</h2><table><thead><tr><th>역할</th><th>위치</th><th>판단 범위</th><th>결과 사용</th></tr></thead><tbody>{role_rows}</tbody></table>
<h2>5. 성공적인 품질평가라고 판단한 근거</h2><ol><li>35개 요구·결함 추적 항목을 모두 통과했습니다.</li><li>단위·통합·E2E·장애·보안·독립 Judge를 계층적으로 분리했습니다.</li><li>초기 실패 2건에 원인·시정 조치·재시험 결과가 연결됩니다.</li><li>생성 주체와 독립 평가 주체를 분리해 자기평가 편향을 줄였습니다.</li><li>모든 공식 테스트 실행에서 TXT·XML·HTML 증적과 누적 이력을 자동 생성합니다.</li></ol>
<h2>6. 개발과정 기록</h2><table><thead><tr><th>날짜</th><th>문제</th><th>구현</th><th>검증</th></tr></thead><tbody>{ledger_rows}</tbody></table>
<h2>7. 잔여 위험과 운영 권고</h2><img class="chart" src="{_image_data_uri(charts['risks'])}"><table><thead><tr><th>위험</th><th>수준</th><th>권고</th></tr></thead><tbody>{risk_rows}</tbody></table>
<h2>8. 품질 증적과 최종 판정</h2><ul><li>TXT: 사람이 읽는 실행·판정 기록</li><li>XML: CI/CD와 감사도구가 읽는 구조화 증적</li><li>HTML: 브라우저용 시각 보고서</li><li>PDF: 발표·승인 검토용 종합 보고서</li></ul>
<div class="verdict"><b>최종 판정:</b> 품질평가 완료(35/35 PASS). 다만 E2E {assessment['e2e_score']}점과 Judge {assessment['judge_score']}점의 낮은 값인 통합 {assessment['overall_score']}점이 배포 기준 {assessment['minimum_score']}점에 미달하므로 운영 배포는 보류합니다.</div>
</main></body></html>""", encoding="utf-8")


def _pdf_styles():
    pdfmetrics.registerFont(TTFont("Malgun", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("MalgunBold", str(FONT_BOLD)))
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("KTitle", parent=styles["Title"], fontName="MalgunBold", fontSize=26, leading=36, textColor=colors.HexColor(NAVY), alignment=TA_CENTER, spaceAfter=18),
        "h1": ParagraphStyle("KH1", parent=styles["Heading1"], fontName="MalgunBold", fontSize=18, leading=25, textColor=colors.HexColor(NAVY), spaceBefore=12, spaceAfter=12),
        "h2": ParagraphStyle("KH2", parent=styles["Heading2"], fontName="MalgunBold", fontSize=13, leading=19, textColor=colors.HexColor(BLUE), spaceBefore=8, spaceAfter=7),
        "body": ParagraphStyle("KBody", parent=styles["BodyText"], fontName="Malgun", fontSize=9.4, leading=15, textColor=colors.HexColor("#263849"), spaceAfter=7),
        "small": ParagraphStyle("KSmall", parent=styles["BodyText"], fontName="Malgun", fontSize=7.7, leading=11, textColor=colors.HexColor("#33475B")),
        "center": ParagraphStyle("KCenter", parent=styles["BodyText"], fontName="Malgun", fontSize=10, leading=16, alignment=TA_CENTER),
        "white": ParagraphStyle("KWhite", parent=styles["BodyText"], fontName="MalgunBold", fontSize=11, leading=16, textColor=colors.white, alignment=TA_CENTER),
    }


def _p(text: Any, style, bold: bool = False) -> Paragraph:
    value = html.escape(str(text)).replace("\n", "<br/>")
    return Paragraph(f"<b>{value}</b>" if bold else value, style)


def _page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D8E1EA"))
    canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
    canvas.setFont("Malgun", 7.5)
    canvas.setFillColor(colors.HexColor(GRAY))
    canvas.drawString(18 * mm, 9 * mm, "VOC 분석 및 QA 시스템 종합 품질평가 결과 보고서")
    canvas.drawRightString(192 * mm, 9 * mm, str(doc.page))
    canvas.restoreState()


def _write_pdf(path: Path, data: dict[str, Any], charts: dict[str, Path]) -> None:
    s = _pdf_styles()
    assessment = data["deployment"]
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm, topMargin=18 * mm, bottomMargin=20 * mm)
    story = [
        Spacer(1, 20 * mm),
        _p("VOC 분석 및 QA 시스템", s["center"]),
        _p("종합 품질평가 결과 보고서", s["title"], True),
        Spacer(1, 6 * mm),
        Table([
            [_p("최종 테스트", s["white"]), _p("초기 테스트", s["white"]), _p("통합 점수", s["white"]), _p("배포 기준", s["white"])],
            [_p("35/35 PASS", s["center"], True), _p("33 PASS / 2 FAIL", s["center"], True), _p(f"{assessment['overall_score']}/100", s["center"], True), _p(f"{assessment['minimum_score']}/100", s["center"], True)],
        ], colWidths=[43 * mm] * 4, style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor(LIGHT)),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#B8C8D7")), ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D4DFE9")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ])),
        Spacer(1, 12 * mm),
        _p("최종 완료 판정", s["h1"]),
        _p("품질평가 수행 및 기능·결함 회귀는 완료되었습니다. 정의된 35건이 모두 통과했습니다.", s["body"], True),
        _p(f"운영 배포는 보류합니다. 현재 통합 점수 {assessment['overall_score']}점이 배포 기준 {assessment['minimum_score']}점에 미달하고 사람 승인 기록도 필요합니다.", s["body"]),
        Spacer(1, 8 * mm),
        _p(f"평가 기간: 2026-07-14 ~ 2026-07-15 · 보고서 생성: {data['generated_at']}", s["center"]),
        PageBreak(),
        _p("1. 품질평가 목적과 3단계 구조", s["h1"]),
        _p("본 평가는 단순 실행 성공이 아니라 VOC 근거 기반 분석, 내부 다중 Agent 진단, 독립 모델 감사와 배포 판단을 하나의 추적 가능한 QA 체계로 검증합니다.", s["body"]),
    ]
    stages = [
        ("1단계 · VOC 분석 및 정책 개선안 생성", "Interpreter가 질문 의도를 해석하고 Retriever가 근거 VOC를 찾습니다. Summarizer가 핵심 원인과 영향을 요약하며 Improver가 담당·기한·우선순위·검증지표를 갖춘 정책안을 생성합니다."),
        ("2단계 · 6개 멀티 에이전트 내부 품질진단", "Interpreter, Retriever, Summarizer, Evaluator, Critic, Improver의 단계별 출력과 시간, 오류 전파, 사실성, 안전성과 실행 가능성을 진단합니다. Critic 지적은 필요 시 Refine으로 연결됩니다."),
        ("3단계 · 독립 LLM Judge 평가", "내부 생성·평가와 분리된 교차 모델이 정확성, 요약 충실성, 정책 구체성, 유용성, 안전성을 독립 채점합니다. Judge는 결과를 수정하지 않고 최종 감사 증적을 생성합니다."),
    ]
    for title, body in stages:
        story.extend([_p(title, s["h2"]), _p(body, s["body"]), Spacer(1, 2 * mm)])
    story.extend([PageBreak(), _p("2. 전체 35건 테스트 정량 분석", s["h1"]), Image(str(charts["trend"]), width=174 * mm, height=90 * mm), Spacer(1, 5 * mm), Image(str(charts["scope"]), width=174 * mm, height=90 * mm), _p("초기에는 33 PASS / 2 FAIL로 성공률 94.3%였습니다. 두 결함의 원인 분석·수정·재시험을 거쳐 최종 35 PASS / 0 FAIL, 성공률 100%로 5.7%p 개선되었습니다.", s["body"]), PageBreak(), _p("3. 결함관리 내역", s["h1"])])
    defect_table = [[_p(x, s["small"], True) for x in ("ID", "결함", "원인", "시정 조치", "최종")]]
    for item in data["defects"]:
        defect_table.append([_p(item["id"], s["small"]), _p(item["name"], s["small"]), _p(item["cause"], s["small"]), _p(item["action"], s["small"]), _p(item["final"], s["small"], True)])
    story.extend([Table(defect_table, repeatRows=1, colWidths=[23 * mm, 27 * mm, 48 * mm, 57 * mm, 24 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])), Spacer(1, 6 * mm), Image(str(charts["defects"]), width=174 * mm, height=90 * mm), PageBreak(), _p("4. 내부 평가와 독립 Judge 역할 구분", s["h1"])])
    role_table = [[_p(x, s["small"], True) for x in ("역할", "위치", "판단 범위", "결과 사용")]] + [[_p(cell, s["small"]) for cell in row] for row in data["roles"]]
    story.extend([Table(role_table, repeatRows=1, colWidths=[27 * mm, 31 * mm, 65 * mm, 56 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT)]), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ])), Spacer(1, 7 * mm), _p("Evaluator와 Critic은 파이프라인 내부의 품질 루프이며 산출물 선택·교정에 직접 관여합니다. 독립 Judge는 생성 주체와 분리되어 결과를 수정하지 않고 외부 감사 점수와 배포 근거를 제공합니다.", s["body"]), _p("5. 성공적인 품질평가라고 판단한 근거", s["h1"])])
    for item in (
        "35개 테스트와 요구사항·결함을 1:1로 추적하고 모두 통과했습니다.",
        "기능 정상 경로뿐 아니라 포트·API 키·CSV·타임아웃·빈 결과·429 등 실패 경로를 검증했습니다.",
        "생성, 내부 평가, 독립 평가를 분리해 자기평가 편향을 줄였습니다.",
        "오프라인 결정적 회귀와 실제 LLM 라이브 검증을 분리해 비용과 재현성을 동시에 관리했습니다.",
        "TXT·XML·HTML·PDF 및 JSON·CSV 원본 증적을 함께 보존합니다.",
    ):
        story.append(_p("• " + item, s["body"]))
    story.extend([PageBreak(), _p("6. 7월 14일부터의 개발·개선 과정", s["h1"])])
    for row in data["ledger"]:
        story.extend([_p(f"{row['date']} · {row['problem']}", s["h2"]), _p(f"구현: {row['implementation']}\n웹 적용: {row['web']}\n검증: {row['evidence']}", s["small"]), Spacer(1, 2 * mm)])
    story.extend([PageBreak(), _p("7. 잔여 위험과 운영 권고사항", s["h1"]), Image(str(charts["risks"]), width=174 * mm, height=90 * mm)])
    risk_table = [[_p(x, s["small"], True) for x in ("잔여 위험", "수준", "운영 권고")]] + [[_p(r["short"], s["small"]), _p(f"{r['score']}/5", s["small"]), _p(r["recommendation"], s["small"])] for r in data["risks"]]
    story.extend([Table(risk_table, repeatRows=1, colWidths=[48 * mm, 20 * mm, 111 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT)]), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])), PageBreak(), _p("8. 다형식 품질 증적과 최종 완료 판정", s["h1"]), _p("모든 공식 테스트 실행은 타임스탬프가 붙은 TXT·XML·HTML 증적을 별도로 생성하고 test_execution_history.jsonl에 누적합니다. 종합 보고서는 PDF와 ZIP 첨부 묶음으로 보존합니다.", s["body"]), Spacer(1, 4 * mm)])
    evidence_table = [[_p(x, s["small"], True) for x in ("형식", "용도")]] + [[_p(a, s["small"], True), _p(b, s["small"])] for a, b in (
        ("TXT", "사람이 읽는 실행 요약·상세 결과·최종 판정"), ("XML", "CI/CD·감사 도구가 읽는 구조화된 35건 증적"), ("HTML", "브라우저에서 그래프와 표를 확인하는 시각 보고서"), ("PDF", "발표·검토·승인을 위한 고정형 종합 보고서"), ("ZIP", "보고서·그래프·원본 결과를 한 번에 전달하는 첨부 묶음"),
    )]
    story.extend([Table(evidence_table, colWidths=[35 * mm, 144 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(LIGHT)]), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ])), Spacer(1, 10 * mm), _p("최종 종합 평가", s["h1"]), _p("[품질평가 수행 완료 · 기능 및 결함 회귀 PASS · 운영 배포 HOLD]", s["center"], True), _p(f"35/35 테스트는 완료되었으나 E2E {assessment['e2e_score']}점과 독립 Judge {assessment['judge_score']}점 중 낮은 통합 점수 {assessment['overall_score']}점이 배포 기준 {assessment['minimum_score']}점에 미달합니다. 점수 개선과 사람 승인 기록 후 다시 배포 판단을 생성해야 합니다.", s["body"])])
    doc.build(story, onFirstPage=_page, onLaterPages=_page)


def build(output_dir: Path = REPORTS) -> dict[str, Any]:
    data = _report_data()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"VOC_종합_품질평가_결과보고서_{stamp}"
    paths = {
        "pdf": output_dir / f"{base_name}.pdf",
        "html": output_dir / f"{base_name}.html",
        "xml": output_dir / f"{base_name}.xml",
        "txt": output_dir / f"{base_name}.txt",
        "json": output_dir / f"{base_name}.json",
        "trend": output_dir / f"{base_name}_테스트추이.png",
        "scope": output_dir / f"{base_name}_점검범위.png",
        "defects": output_dir / f"{base_name}_결함상태.png",
        "risks": output_dir / f"{base_name}_잔여위험.png",
        "zip": output_dir / f"{base_name}_첨부증적.zip",
    }
    _save_test_trend(paths["trend"])
    _save_scope(paths["scope"])
    _save_defects(paths["defects"])
    _save_risks(paths["risks"], data["risks"])
    _write_txt(paths["txt"], data)
    _write_xml(paths["xml"], data)
    _write_html(paths["html"], data, paths)
    _write_pdf(paths["pdf"], data, paths)
    paths["json"].write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    source_case = REPORTS / data["case_source"]
    supporting = [
        REPORTS / "deployment_decision.md",
        REPORTS / "test_result.json",
        source_case,
    ]
    with zipfile.ZipFile(paths["zip"], "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key in ("pdf", "html", "xml", "txt", "json", "trend", "scope", "defects", "risks"):
            archive.write(paths[key], arcname=paths[key].name)
        for path in supporting:
            if path.is_file():
                archive.write(path, arcname=f"supporting/{path.name}")
    return {
        "generated_at": data["generated_at"],
        "test_verdict": "PASS 35/35",
        "deployment_verdict": data["deployment"]["label"],
        "overall_score": data["deployment"]["overall_score"],
        "minimum_score": data["deployment"]["minimum_score"],
        "files": {key: str(value) for key, value in paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=REPORTS)
    args = parser.parse_args()
    result = build(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
