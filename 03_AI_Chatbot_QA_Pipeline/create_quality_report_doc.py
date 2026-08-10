"""
create_quality_report_doc.py
final_quality_report.md 내용을 Word 문서로 변환
"""

import json
from pathlib import Path
from datetime import date
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE_DIR   = Path(__file__).resolve().parent
JSON_PATH  = BASE_DIR / "reports" / "evaluation_result.json"
OUTPUT_PATH = BASE_DIR / "reports" / "AI_챗봇_품질검증_최종보고서.docx"

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def set_cell_bg(cell, hex_color: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)

def set_cell_border(cell, color="DDDDDD"):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), color)
        tcBorders.append(b)
    tcPr.append(tcBorders)

def cell_write(cell, text, bold=False, size=9, color=None,
               align=WD_ALIGN_PARAGRAPH.LEFT, bg=None):
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    if bg:
        set_cell_bg(cell, bg)
    set_cell_border(cell)
    p = cell.paragraphs[0]
    p.alignment = align
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

def add_run(para, text, bold=False, size=10, color=None, italic=False):
    r = para.add_run(text)
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    if color:
        r.font.color.rgb = RGBColor(*color)
    return r

def section_heading(doc, text, level=1):
    colors_map = {1: (46, 64, 87), 2: (79, 70, 229), 3: (30, 30, 30)}
    sizes_map  = {1: 14, 2: 12, 3: 11}
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.bold = True
    r.font.size = Pt(sizes_map[level])
    r.font.color.rgb = RGBColor(*colors_map[level])
    if level == 1:
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after  = Pt(6)
    return p

def badge_color(decision):
    if decision == "PASS":
        return (0, 128, 0)
    elif decision == "REVIEW":
        return (200, 100, 0)
    return (180, 0, 0)

def score_bar(score, max_score=5):
    filled = "■" * score
    empty  = "□" * (max_score - score)
    return f"{filled}{empty}  {score}/{max_score}"

# ─── 데이터 로드 ─────────────────────────────────────────────────────────────

if not JSON_PATH.exists():
    raise FileNotFoundError(f"JSON 파일을 찾을 수 없습니다: {JSON_PATH}")

with open(JSON_PATH, encoding="utf-8") as f:
    results = json.load(f)

total  = len(results)
decisions = [r["evaluation_result"]["overall_decision"] for r in results]
pass_n   = decisions.count("PASS")
review_n = decisions.count("REVIEW")
fail_n   = decisions.count("FAIL")
pass_rate = pass_n / total * 100

def avg_score(key):
    return sum(r["evaluation_result"][key]["score"] for r in results) / total

avg_acc  = avg_score("accuracy")
avg_gnd  = avg_score("groundedness")
avg_help = avg_score("helpfulness")
avg_safe = avg_score("safety")

# ─── 문서 생성 ───────────────────────────────────────────────────────────────

doc = Document()
for sec in doc.sections:
    sec.top_margin    = Cm(2.5)
    sec.bottom_margin = Cm(2.5)
    sec.left_margin   = Cm(3.0)
    sec.right_margin  = Cm(2.5)

# ══════════════════════════════════════
# 표지
# ══════════════════════════════════════
for _ in range(4):
    doc.add_paragraph()

cover = doc.add_paragraph()
cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = cover.add_run("AI 교육과정 안내 챗봇\n품질 검증 최종 보고서")
r.font.size = Pt(22)
r.font.bold = True
r.font.color.rgb = RGBColor(46, 64, 87)

doc.add_paragraph()
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r2 = sub.add_run("QA Automation Pipeline · Final Quality Report")
r2.font.size = Pt(13)
r2.font.color.rgb = RGBColor(79, 70, 229)
r2.font.italic = True

doc.add_paragraph()
doc.add_paragraph()

# 표지 요약 카드 (표)
cover_tbl = doc.add_table(rows=4, cols=2)
cover_tbl.style = "Table Grid"
cover_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
cover_info = [
    ("작성일", str(date.today())),
    ("총 테스트 케이스", f"{total}건"),
    ("최종 합격률", f"{pass_rate:.1f}%"),
    ("평균 평가 점수", f"정확성 {avg_acc:.1f} / 근거성 {avg_gnd:.1f} / 유용성 {avg_help:.1f} / 안전성 {avg_safe:.1f}"),
]
for i, (k, v) in enumerate(cover_info):
    cell_write(cover_tbl.rows[i].cells[0], k, bold=True, size=10,
               bg="2E4057", color=(255,255,255), align=WD_ALIGN_PARAGRAPH.CENTER)
    cell_write(cover_tbl.rows[i].cells[1], v, size=10, bg="F5F7FA")

doc.add_page_break()

# ══════════════════════════════════════
# 1. 종합 평가 요약
# ══════════════════════════════════════
section_heading(doc, "1. 종합 평가 요약", 1)

# 판정 현황 표
sum_tbl = doc.add_table(rows=1, cols=5)
sum_tbl.style = "Table Grid"
sum_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
headers = ["총 케이스", "PASS", "REVIEW", "FAIL", "합격률"]
for i, h in enumerate(headers):
    cell_write(sum_tbl.rows[0].cells[i], h, bold=True, size=10,
               bg="2E4057", color=(255,255,255), align=WD_ALIGN_PARAGRAPH.CENTER)

row = sum_tbl.add_row()
values = [
    (str(total), None),
    (str(pass_n),   (0, 128, 0)),
    (str(review_n), (180, 120, 0)),
    (str(fail_n),   (180, 0, 0)),
    (f"{pass_rate:.1f}%", (46, 64, 87)),
]
for i, (val, col) in enumerate(values):
    cell_write(row.cells[i], val, bold=True, size=12,
               color=col, bg="FFFFFF", align=WD_ALIGN_PARAGRAPH.CENTER)

doc.add_paragraph()

# 4대 지표 평균 표
section_heading(doc, "2. 4대 AI 평가 지표 평균 (5점 만점)", 1)

metric_tbl = doc.add_table(rows=1, cols=4)
metric_tbl.style = "Table Grid"
metric_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
metric_headers = ["정확성 (Accuracy)", "근거성 (Groundedness)", "유용성 (Helpfulness)", "안전성 (Safety)"]
for i, h in enumerate(metric_headers):
    cell_write(metric_tbl.rows[0].cells[i], h, bold=True, size=9,
               bg="4F46E5", color=(255,255,255), align=WD_ALIGN_PARAGRAPH.CENTER)

mrow = metric_tbl.add_row()
for i, avg in enumerate([avg_acc, avg_gnd, avg_help, avg_safe]):
    bar = score_bar(round(avg))
    cell_write(mrow.cells[i], f"{avg:.2f}점\n{bar}",
               bold=True, size=10, align=WD_ALIGN_PARAGRAPH.CENTER,
               bg="F0F0FF" if avg >= 4.0 else "FFF0F0")

doc.add_paragraph()
doc.add_page_break()

# ══════════════════════════════════════
# 3. 세부 테스트 케이스별 결과
# ══════════════════════════════════════
section_heading(doc, "3. 세부 테스트 케이스별 검증 결과", 1)

for res in results:
    case_id   = res["case_id"]
    category  = res["category"]
    test_type = res["test_type"]
    question  = res["user_question"]
    answer    = res["ai_answer"]
    rule_val  = res["rule_validation"]
    eval_res  = res["evaluation_result"]
    decision  = eval_res["overall_decision"]

    dec_label = {"PASS": "PASS", "REVIEW": "REVIEW", "FAIL": "FAIL"}[decision]
    dec_prefix = {"PASS": "[통과]", "REVIEW": "[재검토]", "FAIL": "[실패]"}[decision]
    dec_col = badge_color(decision)

    # 케이스 헤더
    hdr = doc.add_paragraph()
    hdr.paragraph_format.space_before = Pt(10)
    hdr.paragraph_format.space_after  = Pt(2)
    add_run(hdr, f"{dec_prefix} ", bold=True, size=11, color=dec_col)
    add_run(hdr, f"[{case_id}] {category} 테스트", bold=True, size=11, color=(46, 64, 87))
    add_run(hdr, f"  ({test_type})", size=10, color=(120, 120, 120))

    # 케이스 상세 표
    detail_tbl = doc.add_table(rows=6, cols=2)
    detail_tbl.style = "Table Grid"
    detail_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    detail_tbl.columns[0].width = Cm(3.5)
    detail_tbl.columns[1].width = Cm(13.0)

    # 행 데이터
    rule_status = rule_val.get("rule_status", "PASS" if rule_val.get("rule_pass") else "FAIL")
    rule_reason = rule_val.get("rule_reason", rule_val.get("reason", ""))
    rule_badge  = "통과" if rule_status == "PASS" else "실패"
    rule_bg     = "E8F5E9" if rule_status == "PASS" else "FFEBEE"

    rows_data = [
        ("최종 판정",     dec_label,                        dec_col,  "FFFFFF"),
        ("사용자 질문",   question,                          None,     "FAFAFA"),
        ("챗봇 답변",     answer,                            None,     "FFFFFF"),
        ("1차 규칙 검증", f"[{rule_badge}] {rule_reason}",   None,     rule_bg),
        ("AI 종합 요약",  eval_res["summary"],               None,     "FAFAFA"),
        ("지표별 점수",
         f"정확성: {eval_res['accuracy']['score']}/5  |  "
         f"근거성: {eval_res['groundedness']['score']}/5  |  "
         f"유용성: {eval_res['helpfulness']['score']}/5  |  "
         f"안전성: {eval_res['safety']['score']}/5",        None,     "FFFFFF"),
    ]

    for i, (label, value, val_color, bg) in enumerate(rows_data):
        r_cells = detail_tbl.rows[i].cells
        cell_write(r_cells[0], label, bold=True, size=9, bg="E8EAF6",
                   align=WD_ALIGN_PARAGRAPH.CENTER)
        cell_write(r_cells[1], value, size=9, color=val_color, bg=bg,
                   bold=(i == 0))

    doc.add_paragraph()

    # 지표 상세 소표
    score_tbl = doc.add_table(rows=1, cols=4)
    score_tbl.style = "Table Grid"
    score_tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    for j, label in enumerate(["정확성", "근거성", "유용성", "안전성"]):
        cell_write(score_tbl.rows[0].cells[j], label, bold=True, size=8,
                   bg="3949AB", color=(255,255,255), align=WD_ALIGN_PARAGRAPH.CENTER)

    srow = score_tbl.add_row()
    for j, key in enumerate(["accuracy", "groundedness", "helpfulness", "safety"]):
        sc = eval_res[key]["score"]
        bar = score_bar(sc)
        bg  = "E8F5E9" if sc >= 4 else ("FFF9C4" if sc == 3 else "FFEBEE")
        cell_write(srow.cells[j], bar, size=8, bg=bg, align=WD_ALIGN_PARAGRAPH.CENTER)

    p_sep = doc.add_paragraph()
    p_sep.paragraph_format.space_after = Pt(4)
    p_sep.add_run("─" * 80).font.color.rgb = RGBColor(200, 200, 200)

doc.add_page_break()

# ══════════════════════════════════════
# 4. 종합 의견
# ══════════════════════════════════════
section_heading(doc, "4. 종합 의견 및 결론", 1)

doc.add_paragraph()

# 강점
section_heading(doc, "강점", 2)
strengths = [
    f"전체 합격률 {pass_rate:.1f}% — 정상 케이스(Happy Path) 전 항목 PASS",
    f"근거성·안전성 평균 {avg_gnd:.2f}/{avg_safe:.2f}점 — 할루시네이션 없는 RAG 기반 답변 우수",
    "위협·불법 요청(TC-010) 정확한 거절 처리 확인",
    "수료 조건, 출결 규정 등 핵심 정책 수치 정확 반영",
]
for s in strengths:
    p = doc.add_paragraph(style="List Bullet")
    add_run(p, s, size=10)

doc.add_paragraph()

# 개선 필요
section_heading(doc, "개선 필요 사항", 2)
weaknesses = [
    f"FAIL {fail_n}건 — 문서 외 질문(TC-008, TC-009): 챗봇은 적절히 거절했으나 Judge Agent가 '유용성' 0~1점 부여 → 평가 기준 재조정 필요",
    "TC-005 (출결/Edge): 규칙 검증 FAIL — expected_keyword '결석 1일'이 답변에 없으나 내용은 정확 → 키워드 기준 세분화 필요",
    "문서 외 질문 카테고리 Judge Agent 채점 기준을 '거절 적절성' 위주로 수정 권고",
]
for w in weaknesses:
    p = doc.add_paragraph(style="List Bullet")
    add_run(p, w, size=10)

doc.add_paragraph()

# 최종 결론
section_heading(doc, "최종 결론", 2)
conclusion = doc.add_paragraph()
add_run(conclusion,
    f"본 파이프라인은 총 {total}건의 테스트 케이스 중 {pass_n}건 PASS, 합격률 {pass_rate:.1f}%를 달성하였습니다. "
    "RAG 기반 지식 검색과 OpenAI Structured Outputs를 활용한 AI 평가 체계는 전반적으로 안정적으로 동작하고 있으며, "
    "일부 경계 케이스(문서 외 질문)에서 평가 기준 개선이 필요합니다. "
    "전체적으로 교육과정 안내 챗봇의 품질은 운영 수준에 도달한 것으로 판단됩니다.",
    size=10)

doc.add_paragraph()

# 끝
end_p = doc.add_paragraph()
end_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
add_run(end_p, f"── 보고서 끝  |  작성일: {date.today()} ──",
        size=9, color=(160, 160, 160))

# ─── 저장 ────────────────────────────────────────────────────────────────────
doc.save(str(OUTPUT_PATH))
print(f"[완료] 보고서 생성: {OUTPUT_PATH}")
