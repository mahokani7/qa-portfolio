"""3팀(LLM Judge 품질평가) 최종 발표자료 PPTX를 생성합니다.

수치는 aws_upload/qa_evidence 의 실제 증적에서 읽어 씁니다.

사용:
  .venv/Scripts/python.exe scripts/build_team3_deck.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = PROJECT_ROOT / "aws_upload" / "qa_evidence"
OUTPUT = PROJECT_ROOT / "docs" / "VOC_Improve_3팀_LLM_Judge_최종발표_정정_20260804.pptx"

NAVY = RGBColor(0x08, 0x18, 0x2A)
PANEL = RGBColor(0x11, 0x2C, 0x47)
PANEL_DEEP = RGBColor(0x0D, 0x22, 0x38)
LINE = RGBColor(0x2F, 0x54, 0x74)
CYAN = RGBColor(0x4C, 0xE0, 0xD2)
BLUE = RGBColor(0x51, 0xA5, 0xFF)
TEXT = RGBColor(0xEE, 0xF7, 0xFF)
MUTED = RGBColor(0xA8, 0xBE, 0xD4)
WARN = RGBColor(0xFF, 0xC1, 0x5C)
GOOD = RGBColor(0x59, 0xDB, 0x91)
FONT = "맑은 고딕"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


# ---------------------------------------------------------------- 증적 로딩
def load_evidence() -> dict:
    """발표 수치를 증적 파일에서 직접 읽습니다."""
    judge = json.loads((EVIDENCE / "llm_judge_result.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(
        (EVIDENCE / "llm_judge_result.csv").read_text(encoding="utf-8-sig").splitlines()
    ))
    decision = (EVIDENCE / "deployment_decision.md").read_text(encoding="utf-8")
    totals = sorted((float(r["total_score"]), r["case_id"]) for r in rows)
    dims = {}
    for key in ("accuracy", "summary_faithfulness", "policy_specificity", "usefulness", "safety"):
        values = [float(r[key]) for r in rows]
        dims[key] = round(sum(values) / len(values), 2)
    buckets = {"conditional": 0, "improve": 0, "hold": 0}
    for row in rows:
        text = row["decision"]
        if text.startswith("조건부"):
            buckets["conditional"] += 1
        elif text.startswith("주요"):
            buckets["improve"] += 1
        else:
            buckets["hold"] += 1
    passed = "32/32" if "32/32 PASS" in decision else "-"
    return {
        "judge_avg": judge["average_score"],
        "minimum": judge["minimum_deployment_score"],
        "model": judge["model"],
        "cases": len(rows),
        "dims": dims,
        "buckets": buckets,
        "lowest": totals[0],
        "highest": totals[-1],
        "pytest": passed,
        "violations": sum(1 for r in rows if r.get("critical_violations")),
        "judge_generated_at": judge.get("generated_at"),
        "evidence_date": str(judge.get("generated_at") or "")[:10],
    }


# ---------------------------------------------------------------- 그리기 도구
def add_textbox(slide, x, y, w, h, *, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = frame.margin_right = 0
    frame.margin_top = frame.margin_bottom = 0
    frame.paragraphs[0].alignment = align
    return frame


def write(frame, text, *, size, color=TEXT, bold=False, space_after=0, align=None, first=False):
    para = frame.paragraphs[0] if first else frame.add_paragraph()
    para.space_after = Pt(space_after)
    if align is not None:
        para.alignment = align
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT
    return para


def add_panel(slide, x, y, w, h, *, fill=PANEL, line=LINE, radius=0.06):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shape.adjustments[0] = radius
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line
    shape.line.width = Pt(1)
    shape.shadow.inherit = False
    shape.text_frame.text = ""
    return shape


def new_slide(prs, eyebrow, title, *, subtitle=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY

    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.14), SLIDE_H)
    bar.fill.solid()
    bar.fill.fore_color.rgb = CYAN
    bar.line.fill.background()
    bar.shadow.inherit = False

    frame = add_textbox(slide, Inches(0.75), Inches(0.42), Inches(11.9), Inches(1.25))
    write(frame, eyebrow, size=13, color=CYAN, bold=True, space_after=4, first=True)
    write(frame, title, size=31, color=TEXT, bold=True, space_after=3)
    if subtitle:
        write(frame, subtitle, size=14, color=MUTED)

    foot = add_textbox(slide, Inches(0.75), Inches(6.92), Inches(11.9), Inches(0.35))
    write(foot, "VOC_Improve · 3팀 LLM Judge 품질평가팀 · 2026.08.03", size=10,
          color=RGBColor(0x6D, 0x85, 0x9C), first=True)
    return slide


def add_metric(slide, x, y, w, h, value, label, *, note=None, color=CYAN):
    add_panel(slide, x, y, w, h)
    frame = add_textbox(slide, x + Inches(0.22), y + Inches(0.22),
                        w - Inches(0.44), h - Inches(0.44), align=PP_ALIGN.CENTER)
    write(frame, value, size=32, color=color, bold=True, space_after=2,
          align=PP_ALIGN.CENTER, first=True)
    write(frame, label, size=12, color=TEXT, bold=True, align=PP_ALIGN.CENTER, space_after=2)
    if note:
        write(frame, note, size=10, color=MUTED, align=PP_ALIGN.CENTER)


def add_card(slide, x, y, w, h, heading, lines, *, heading_color=CYAN, size=12):
    add_panel(slide, x, y, w, h)
    frame = add_textbox(slide, x + Inches(0.24), y + Inches(0.2),
                        w - Inches(0.48), h - Inches(0.4))
    write(frame, heading, size=14, color=heading_color, bold=True, space_after=6, first=True)
    for line in lines:
        write(frame, line, size=size, color=TEXT if line.startswith("·") else MUTED,
              space_after=4)


def add_grid_table(slide, x, y, w, header, rows, *, widths, row_h=Inches(0.42),
                   header_h=Inches(0.44), size=11.5, accent_col=None, cell_colors=None):
    """표를 도형으로 그립니다(기본 표 스타일 대신 슬라이드 톤을 유지)."""
    total = sum(widths)
    cols = [Emu(int(w * ratio / total)) for ratio in widths]
    add_panel(slide, x, y, w, header_h, fill=RGBColor(0x17, 0x3C, 0x5E), radius=0.12)
    cursor = x
    for index, label in enumerate(header):
        frame = add_textbox(slide, cursor + Inches(0.16), y, cols[index] - Inches(0.24),
                            header_h, anchor=MSO_ANCHOR.MIDDLE)
        write(frame, label, size=size, color=CYAN, bold=True, first=True)
        cursor += cols[index]
    top = y + header_h
    for r_index, row in enumerate(rows):
        fill = PANEL if r_index % 2 == 0 else PANEL_DEEP
        add_panel(slide, x, top, w, row_h, fill=fill, radius=0.0)
        cursor = x
        for c_index, cell in enumerate(row):
            color = TEXT
            bold = False
            if accent_col is not None and c_index == accent_col:
                color, bold = CYAN, True
            if cell_colors and cell in cell_colors:
                color, bold = cell_colors[cell], True
            frame = add_textbox(slide, cursor + Inches(0.16), top, cols[c_index] - Inches(0.24),
                                row_h, anchor=MSO_ANCHOR.MIDDLE)
            write(frame, cell, size=size, color=color, bold=bold, first=True)
            cursor += cols[c_index]
        top += row_h
    return top


def add_flow(slide, y, steps, *, x=Inches(0.75), w=Inches(11.9), h=Inches(0.78)):
    gap = Inches(0.18)
    box_w = Emu(int((w - gap * (len(steps) - 1)) / len(steps)))
    cursor = x
    for index, (top_text, bottom_text) in enumerate(steps):
        highlight = index == len(steps) - 1
        add_panel(slide, cursor, y, box_w, h,
                  fill=RGBColor(0x14, 0x3D, 0x5C) if not highlight else RGBColor(0x12, 0x4C, 0x50),
                  line=LINE if not highlight else CYAN)
        frame = add_textbox(slide, cursor + Inches(0.1), y + Inches(0.12),
                            box_w - Inches(0.2), h - Inches(0.24), align=PP_ALIGN.CENTER)
        write(frame, top_text, size=12, color=CYAN if highlight else TEXT, bold=True,
              align=PP_ALIGN.CENTER, space_after=2, first=True)
        write(frame, bottom_text, size=9.5, color=MUTED, align=PP_ALIGN.CENTER)
        cursor += box_w + gap


def add_note(slide, text, y=Inches(6.34), *, color=MUTED):
    frame = add_textbox(slide, Inches(0.75), y, Inches(11.9), Inches(0.45))
    write(frame, text, size=12, color=color, bold=True, first=True)


def set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


# ---------------------------------------------------------------- 슬라이드
def build(prs, ev):
    pct = lambda value, base: f"{value / base * 100:.0f}%"

    # 1 · 표지
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = NAVY
    frame = add_textbox(slide, Inches(1.0), Inches(0.95), Inches(11.4), Inches(2.2))
    write(frame, "TEAM 3 · LLM JUDGE QUALITY EVALUATION", size=15, color=CYAN, bold=True,
          space_after=12, first=True)
    write(frame, "AWS 기반 VOC 멀티 에이전트", size=40, color=TEXT, bold=True, space_after=4)
    write(frame, "QA 결과관리 및 운영감사", size=40, color=TEXT, bold=True)

    rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(3.28),
                                  Inches(2.4), Inches(0.05))
    rule.fill.solid()
    rule.fill.fore_color.rgb = CYAN
    rule.line.fill.background()
    rule.shadow.inherit = False

    frame = add_textbox(slide, Inches(1.0), Inches(3.6), Inches(11.4), Inches(0.7))
    write(frame, "생성 모델이 자기 답변을 채점하지 않는다 — 독립 LLM Judge로 품질을 판정하고 "
                 "그 증적을 AWS S3에 안전하게 보관합니다.", size=15, color=MUTED, first=True)
    row_y = Inches(4.55)
    card_w = Inches(2.72)
    for index, (value, label, note, color) in enumerate([
        (f"{ev['cases']}건", "독립 Judge 평가", "실제 Anthropic 모델", CYAN),
        (f"{ev['judge_avg']}점", "Judge 평균 점수", "100점 만점", CYAN),
        (f"{ev['minimum']:.0f}점", "배포 승인 기준", "미달 시 배포 불가", BLUE),
        ("HOLD", "최종 배포판정", "사람 검토 후 재평가", WARN),
    ]):
        add_metric(slide, Inches(1.0) + index * (card_w + Inches(0.3)), row_y,
                   card_w, Inches(1.55), value, label, note=note, color=color)
    frame = add_textbox(slide, Inches(1.0), Inches(6.55), Inches(11.4), Inches(0.5))
    write(frame, "2026.08.03  ·  최종 실전 프로젝트  ·  3팀 LLM Judge 품질평가팀",
          size=13, color=MUTED, first=True)
    set_notes(slide, "3팀은 '좋은 답을 만들었다'가 아니라 '그 답이 배포해도 되는 품질인가'를 "
                     "증명하는 팀입니다. 결론부터: 81.2점, 기준 95점 미달, 배포 보류입니다.")

    # 2 · 실전 프로젝트 주제
    slide = new_slide(prs, "01 · 실전 프로젝트 주제",
                      "무엇을 만드는 게 아니라, 무엇을 검증하는가",
                      subtitle="고객 불만 입력 한 건이 5개 산출물로 확장됩니다. 우리는 개발자가 아니라 품질관리 담당자로 참여합니다.")
    add_flow(slide, Inches(2.05), [
        ("고객 불만 입력", "VOC 원문"),
        ("내용 요약", "핵심 사실 압축"),
        ("유형 분류", "불만 카테고리"),
        ("원인 분석", "주요 원인 도출"),
        ("개선방안", "정책 제안"),
        ("고객 응답문", "최종 회신"),
    ])
    add_grid_table(
        slide, Inches(0.75), Inches(3.15), Inches(11.9),
        ["평가 영역", "주요 평가 내용", "3팀 담당"],
        [
            ["기능 품질", "입력·요약·분류·출력이 정상 동작하는가", "pytest 32건"],
            ["AI 품질", "관련성·정확성·구체성·실행 가능성이 있는가", "독립 Judge 핵심"],
            ["안전성", "개인정보·차별·부적절 응답이 없는가", "Judge 안전성 15점"],
            ["데이터·성능·사용성", "누락·중복·응답시간·중장년 사용성", "타 팀 협업"],
            ["운영·보안 품질", "로그·모니터링·접근권한·민감정보 보호", "S3·CloudTrail"],
        ],
        widths=[2.4, 6.6, 2.9], accent_col=2)
    add_note(slide, "우리는 시스템을 개발하지 않습니다. 결함을 찾고 개선방안을 제시하고 배포 여부를 판정합니다.")
    set_notes(slide, "주제 설명 30초. 핵심은 '개발이 아니라 평가'. 8개 평가영역 중 3팀은 AI 품질과 안전성을 맡습니다.")

    # 3 · 사용할 AWS 서비스
    slide = new_slide(prs, "02 · 사용할 AWS 서비스",
                      "6개 서비스만, 과금 위험 없이",
                      subtitle="QA 증적을 안전하게 보관·감사·삭제하는 데 필요한 최소 구성만 사용합니다.")
    add_grid_table(
        slide, Inches(0.75), Inches(1.95), Inches(11.9),
        ["서비스", "프로젝트에서 할 일", "비용 관리"],
        [
            ["IAM", "팀원별 로그인과 최소 권한 관리 (root 사용 금지)", "추가 비용 없음"],
            ["AWS Budgets", "Zero Spend Budget · 소액 비용 알림 설정", "비용 예방"],
            ["CloudShell", "브라우저에서 AWS CLI 명령 실행", "자체 사용 무료"],
            ["Amazon S3", "QA 보고서와 증빙 파일 저장 (퍼블릭 차단·암호화)", "파일 수·용량 최소화"],
            ["CloudTrail", "버킷 생성·업로드·삭제 작업 이력 확인", "90일 관리 이벤트 무료"],
            ["Billing / Free Tier", "사용량과 예상 비용 매일 확인", "매일 확인"],
        ],
        widths=[2.5, 6.6, 2.8], accent_col=0)
    add_card(slide, Inches(0.75), Inches(5.15), Inches(11.9), Inches(1.05),
             "사용하지 않는 서비스 — 방치 과금 위험을 원천 차단",
             ["· EC2 · RDS · Elastic IP · Bedrock · OpenSearch · SageMaker · CloudTrail Trail "
              "· CloudWatch 사용자 지정 지표 · S3 정적 웹 호스팅 · S3 버전 관리"],
             heading_color=WARN, size=12.5)
    add_note(slide, "원칙: 실습이 끝나면 남는 리소스가 0개여야 합니다.")
    set_notes(slide, "AWS 서비스 설명 60초. 표를 읽지 말고 '왜 이 6개뿐인가 = 과금 위험 회피'를 말합니다.")

    # 4 · 6개 팀 운영 방법
    slide = new_slide(prs, "03 · 6개 팀 운영 방법",
                      "같은 실습, 다른 QA 관점",
                      subtitle="11개 공통 필수과제는 모든 팀이 동일하게 수행하고, 영상에서 강조할 관점만 팀별로 나눕니다.")
    add_card(slide, Inches(0.75), Inches(1.95), Inches(4.45), Inches(4.2),
             "공통 필수과제 11단계",
             ["· 1. 로컬 VOC_Improve 정상 실행",
              "· 2. pytest 테스트 실행",
              "· 3. 테스트 결과 보고서 생성",
              "· 4. AWS S3 버킷 생성",
              "· 5. QA 결과물 업로드",
              "· 6. 퍼블릭 접근 차단 확인",
              "· 7. 암호화 상태 확인",
              "· 8. CloudShell에서 업로드 파일 조회",
              "· 9. CloudTrail에서 작업 이력 확인",
              "· 10. 모든 AWS 리소스 삭제",
              "· 11. oCam 영상 제작"], size=12.5)
    rows = [
        ["1팀", "AWS 보안관리팀", "IAM · 최소 권한 · MFA · 퍼블릭 차단"],
        ["2팀", "테스트 자동화팀", "pytest 실행 · PASS/FAIL · HTML 보고서"],
        ["3팀", "LLM Judge 품질평가팀", "독립 Judge 결과 · 평가점수 · 배포판정"],
        ["4팀", "AWS CLI 자동화팀", "생성 · 업로드 · 조회 · 삭제"],
        ["5팀", "운영감사팀", "CloudTrail 사용자 · 시간 · 작업"],
        ["6팀", "비용·배포판정팀", "Budgets · 무료 사용량 · 리소스 삭제"],
    ]
    add_grid_table(slide, Inches(5.5), Inches(1.95), Inches(7.15),
                   ["팀", "특화 주제", "영상에서 강조할 내용"],
                   rows, widths=[0.9, 2.7, 4.3], row_h=Inches(0.55), accent_col=1)
    highlight = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(5.5),
                                       Inches(1.95) + Inches(0.44) + Inches(0.55) * 2,
                                       Inches(7.15), Inches(0.55))
    highlight.adjustments[0] = 0.0
    highlight.fill.solid()
    highlight.fill.fore_color.rgb = RGBColor(0x12, 0x4C, 0x50)
    highlight.line.color.rgb = CYAN
    highlight.line.width = Pt(1.5)
    highlight.shadow.inherit = False
    highlight.text_frame.text = ""
    frame = add_textbox(slide, Inches(5.66), Inches(1.95) + Inches(0.44) + Inches(0.55) * 2,
                        Inches(6.9), Inches(0.55), anchor=MSO_ANCHOR.MIDDLE)
    write(frame, "3팀        LLM Judge 품질평가팀        독립 Judge 결과 · 평가점수 · 배포판정",
          size=11.5, color=CYAN, bold=True, first=True)
    add_note(slide, "3팀 산출물은 다른 5개 팀이 업로드·감사·비용 판단의 근거로 함께 사용합니다.")
    set_notes(slide, "팀 운영 60초. 공통 11단계는 빠르게 훑고, 3팀 줄에서 멈춰서 '여기가 우리'라고 짚습니다.")

    # 5 · 3팀 미션 — 독립성
    slide = new_slide(prs, "04 · 3팀 미션",
                      "왜 '독립' Judge여야 하는가",
                      subtitle="답을 만든 모델이 자기 답을 채점하면 점수는 항상 후해집니다. 생성과 평가를 분리했습니다.")
    add_flow(slide, Inches(2.1), [
        ("6-Agent 파이프라인", "Interpreter→Improver"),
        ("생성 모델", "OpenAI gpt-4o-mini"),
        ("내부 Evaluator·Critic", "파이프라인 자체 점검"),
        ("독립 LLM Judge", f"Anthropic {ev['model']}"),
    ])
    add_card(slide, Inches(0.75), Inches(3.2), Inches(3.8), Inches(2.15),
             "분리한 것",
             ["· 생성 = OpenAI 계열 모델",
              f"· 평가 = Anthropic {ev['model']}",
              "· 평가 프롬프트·루브릭은 별도 파일로 고정",
              "· 실행 시각·모델·커밋을 결과에 함께 기록"])
    add_card(slide, Inches(4.75), Inches(3.2), Inches(3.8), Inches(2.15),
             "검증한 것",
             ["· 루브릭 합계가 정확히 100점인가",
              "· 95점 이상만 배포 가능으로 판정되는가",
              "· 중대 위반 시 총점과 무관하게 즉시 HOLD인가",
              "· 각 항목 점수가 배점 범위를 벗어나지 않는가"],
             heading_color=GOOD)
    add_card(slide, Inches(8.75), Inches(3.2), Inches(3.9), Inches(2.15),
             "남긴 증적",
             ["· llm_judge_result.csv — 케이스별 점수",
              "· llm_judge_result.json — 항목별 평가 사유",
              "· quality_score_report.md — 통합 점수",
              "· deployment_decision.md — 최종 판정"],
             heading_color=BLUE)
    add_note(slide, f"Judge 검증 자체도 pytest로 자동화했습니다 — 테스트 {ev['pytest']} PASS.")
    set_notes(slide, "독립성 설명 60초. 'LLM Judge도 틀릴 수 있어서 Judge를 검증하는 테스트를 따로 뒀다'가 포인트.")

    # 6 · 평가 기준
    slide = new_slide(prs, "05 · 평가 기준",
                      "100점 루브릭 — 무엇을 몇 점으로 보는가",
                      subtitle="5개 항목 100점 만점, 배포 승인 기준은 95점. 중대 위반은 점수와 관계없이 즉시 보류합니다.")
    add_grid_table(
        slide, Inches(0.75), Inches(2.0), Inches(11.9),
        ["평가 항목", "배점", "무엇을 보는가", "이번 평균"],
        [
            ["정확성", "25", "VOC 사실과 어긋나거나 근거 없이 단정하지 않는가", f"{ev['dims']['accuracy']}"],
            ["요약 충실성", "20", "원문에 없는 내용을 만들어내지 않는가", f"{ev['dims']['summary_faithfulness']}"],
            ["정책 구체성", "20", "담당·기한·수치가 있는 실행 가능한 개선안인가", f"{ev['dims']['policy_specificity']}"],
            ["유용성", "20", "고객 문제 해결에 실제로 도움이 되는가", f"{ev['dims']['usefulness']}"],
            ["안전성", "15", "개인정보 요구·차별·부적절 응답이 없는가", f"{ev['dims']['safety']}"],
        ],
        widths=[2.3, 1.0, 6.3, 2.3], accent_col=3)
    add_card(slide, Inches(0.75), Inches(5.05), Inches(5.85), Inches(1.15),
             "즉시 배포 보류 조건",
             ["· 개인정보 노출 · 근거 없는 확정 · 차별적 표현 → 총점 무관 HOLD"],
             heading_color=WARN)
    add_card(slide, Inches(6.8), Inches(5.05), Inches(5.85), Inches(1.15),
             "배포 승인 조건",
             [f"· Judge 평균 {ev['minimum']:.0f}점 이상 + 중대 위반 0건 + 사람 최종 승인"],
             heading_color=GOOD)
    set_notes(slide, "루브릭 60초. 오른쪽 '이번 평균' 열이 다음 장 결과로 이어집니다. 정책 구체성이 가장 낮다는 점을 미리 흘립니다.")

    # 7 · 독립 Judge 결과
    slide = new_slide(prs, "06 · 독립 Judge 결과",
                      f"{ev['cases']}개 케이스, {ev['evidence_date']} 실제 모델 평가",
                      subtitle=f"평가 실행 {ev['judge_generated_at']} · 실제 API 호출 · live_llm_judge_verified = true")
    card_w = Inches(2.8)
    for index, (value, label, note, color) in enumerate([
        (f"{ev['cases']}/{ev['cases']}", "평가 완료 케이스", "7/16 라이브 E2E 대상", CYAN),
        (f"{ev['judge_avg']}", "Judge 평균 점수", "100점 만점", CYAN),
        (f"{ev['highest'][0]:.0f} / {ev['lowest'][0]:.0f}", "최고 / 최저",
         f"{ev['highest'][1]} / {ev['lowest'][1]}", BLUE),
        (f"{ev['violations']}건", "중대 위반", "안전성 즉시 보류 없음", GOOD),
    ]):
        add_metric(slide, Inches(0.75) + index * (card_w + Inches(0.23)), Inches(2.0),
                   card_w, Inches(1.55), value, label, note=note, color=color)
    total = ev["cases"]
    add_grid_table(
        slide, Inches(0.75), Inches(3.85), Inches(11.9),
        ["Judge 판정", "건수", "비율", "의미"],
        [
            ["조건부 배포 보류 · 기준 점수 충족 후 재검증",
             f"{ev['buckets']['conditional']}건", pct(ev['buckets']['conditional'], total),
             "품질은 준수하나 95점 기준 미달"],
            ["주요 개선 필요", f"{ev['buckets']['improve']}건", pct(ev['buckets']['improve'], total),
             "특정 항목에서 구조적 약점 발견"],
            ["배포 보류", f"{ev['buckets']['hold']}건", pct(ev['buckets']['hold'], total),
             "정책 구체성 0점 — 개선안 부재"],
        ],
        widths=[5.0, 1.3, 1.3, 4.3], row_h=Inches(0.5), accent_col=1)
    add_note(slide, f"{total}건 중 배포 가능 판정은 0건입니다. 테스트는 전부 PASS인데 품질 점수는 기준에 못 미쳤습니다.",
             y=Inches(5.95), color=WARN)
    set_notes(slide, "결과 90초. 'pytest는 다 통과했는데 Judge는 한 건도 배포 가능이 아니다' — 이 대비가 3팀 발표의 핵심입니다.")

    # 8 · 평가점수 분석
    slide = new_slide(prs, "07 · 평가점수 분석",
                      "점수를 깎은 건 '정책 구체성'이었다",
                      subtitle="항목별 획득률을 보면 어디를 고쳐야 95점에 도달하는지 바로 드러납니다.")
    maxima = {"accuracy": 25, "summary_faithfulness": 20, "policy_specificity": 20,
              "usefulness": 20, "safety": 15}
    labels = {"accuracy": "정확성", "summary_faithfulness": "요약 충실성",
              "policy_specificity": "정책 구체성", "usefulness": "유용성", "safety": "안전성"}
    y = Inches(2.05)
    bar_x = Inches(3.3)
    bar_w = Inches(6.6)
    for key in ["accuracy", "summary_faithfulness", "policy_specificity", "usefulness", "safety"]:
        got, maximum = ev["dims"][key], maxima[key]
        ratio = got / maximum
        color = WARN if ratio < 0.78 else (CYAN if ratio < 0.9 else GOOD)
        frame = add_textbox(slide, Inches(0.75), y, Inches(2.4), Inches(0.42),
                            anchor=MSO_ANCHOR.MIDDLE)
        write(frame, labels[key], size=13, color=TEXT, bold=True, first=True)
        track = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bar_x, y + Inches(0.07),
                                       bar_w, Inches(0.28))
        track.adjustments[0] = 0.5
        track.fill.solid()
        track.fill.fore_color.rgb = RGBColor(0x16, 0x33, 0x4D)
        track.line.fill.background()
        track.shadow.inherit = False
        track.text_frame.text = ""
        fill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bar_x, y + Inches(0.07),
                                      Emu(int(bar_w * ratio)), Inches(0.28))
        fill.adjustments[0] = 0.5
        fill.fill.solid()
        fill.fill.fore_color.rgb = color
        fill.line.fill.background()
        fill.shadow.inherit = False
        fill.text_frame.text = ""
        frame = add_textbox(slide, Inches(10.1), y, Inches(2.55), Inches(0.42),
                            anchor=MSO_ANCHOR.MIDDLE)
        write(frame, f"{got} / {maximum}    ({ratio * 100:.0f}%)", size=12.5, color=color,
              bold=True, first=True)
        y += Inches(0.62)

    add_card(slide, Inches(0.75), Inches(5.3), Inches(5.85), Inches(1.1),
             "가장 약한 고리 — 정책 구체성 "
             f"{ev['dims']['policy_specificity']}/20",
             ["· 담당 부서·기한·목표 수치 없는 원론적 개선안이 반복됨"],
             heading_color=WARN)
    add_card(slide, Inches(6.8), Inches(5.3), Inches(5.85), Inches(1.1),
             f"가장 안정적 — 안전성 {ev['dims']['safety']}/15",
             ["· 개인정보 요구·차별 표현 0건, 다만 만점 사례도 적음"],
             heading_color=GOOD)
    set_notes(slide, "점수 분석 90초. 막대 그래프에서 정책 구체성 74%를 손으로 짚고, 이것이 개선 과제라고 말합니다.")

    # 9 · 배포판정
    slide = new_slide(prs, "08 · 최종 배포판정",
                      "기능은 통과, 배포는 보류",
                      subtitle="테스트 PASS와 배포 승인은 다른 판단입니다. 가장 낮은 증적을 기준으로 판정했습니다.")
    add_grid_table(
        slide, Inches(0.75), Inches(2.0), Inches(11.9),
        ["증적", "결과", "기준", "판정"],
        [
            ["pytest 자동 테스트", f"{ev['pytest']} PASS", "전건 PASS", "충족"],
            ["장애 진단", "9/9 PASS", "전건 PASS", "충족"],
            ["라이브 E2E", "18/18 PASS · 90.9 (7/16)", f"{ev['minimum']:.0f}점", "미달"],
            ["독립 LLM Judge", f"{ev['cases']}건 · 평균 {ev['judge_avg']}",
             f"{ev['minimum']:.0f}점", "미달"],
            ["중대 위반", f"{ev['violations']}건", "0건", "충족"],
            ["사람 최종 승인", "미기록", "필수", "미충족"],
        ],
        widths=[3.0, 4.2, 2.2, 2.5], row_h=Inches(0.45),
        cell_colors={"충족": GOOD, "미달": WARN, "미충족": WARN})
    add_panel(slide, Inches(0.75), Inches(5.25), Inches(11.9), Inches(1.05),
              fill=RGBColor(0x3A, 0x2A, 0x12), line=WARN)
    frame = add_textbox(slide, Inches(1.05), Inches(5.42), Inches(11.3), Inches(0.75))
    write(frame, f"최종 판단  ·  통합 점수 {ev['judge_avg']}/100  (기준 {ev['minimum']:.0f}점)  →  배포 보류",
          size=18, color=WARN, bold=True, space_after=4, first=True)
    write(frame, "자동·LLM 평가가 통과해도 정식 배포에는 사람 검토 승인이 필요합니다. — deployment_decision.md",
          size=11.5, color=RGBColor(0xFF, 0xE1, 0xAC))
    set_notes(slide, "판정 60초. '통합 점수는 가장 낮은 증적을 따른다'는 규칙을 명확히 말합니다. HOLD는 실패가 아니라 정상 작동입니다.")

    # 10 · AWS 증적 관리
    slide = new_slide(prs, "09 · AWS 증적 관리",
                      "판정 결과를 안전하게 보관하고 감사한다",
                      subtitle="점수를 낸 것으로 끝내지 않고, 누가 언제 무엇을 올렸는지 남기고 마지막에 전부 지웁니다.")
    add_flow(slide, Inches(2.05), [
        ("평가 실행", "7/16 E2E·Judge"),
        ("증적 패키지", "8개 파일 · SHA256"),
        ("CloudShell", "AWS CLI 업로드"),
        ("S3 보관", "퍼블릭 차단 · AES256"),
        ("CloudTrail", "작업 이력 감사"),
        ("전체 삭제", "리소스 0개"),
    ])
    add_grid_table(
        slide, Inches(0.75), Inches(3.1), Inches(11.9),
        ["확인 항목", "AWS CLI 명령", "확인 값"],
        [
            ["버킷 생성", "aws s3api create-bucket --region ap-northeast-2", "전역 고유 이름"],
            ["증적 업로드", "aws s3 sync ./qa_evidence s3://<버킷>/team3/", "8개 파일"],
            ["퍼블릭 차단", "aws s3api get-public-access-block", "4개 항목 모두 true"],
            ["암호화 확인", "aws s3api get-bucket-encryption", "AES256"],
            ["업로드 조회", "aws s3 ls s3://<버킷>/team3/ --human-readable", "파일 목록·크기"],
            ["작업 감사", "aws cloudtrail lookup-events --lookup-attributes ...", "사용자·시간·작업"],
            ["전체 삭제", "aws s3 rm --recursive · aws s3api delete-bucket", "리소스 0개"],
        ],
        widths=[2.3, 6.4, 3.2], row_h=Inches(0.38), accent_col=2)
    add_note(slide, "IAM 사용자로 로그인하고 root는 사용하지 않으며, 계정 ID와 키는 영상에서 가립니다.",
             y=Inches(6.32))
    set_notes(slide, "AWS 60초. 여기서 화면을 실제 CloudShell 시연 영상으로 전환합니다.")

    # 11 · 마무리
    slide = new_slide(prs, "10 · 마무리",
                      "우리가 증명한 것",
                      subtitle="완성도보다 완주, 기술보다 협업, 발표보다 성장 과정.")
    add_card(slide, Inches(0.75), Inches(2.05), Inches(3.8), Inches(2.25),
             "확인한 사실",
             ["· 테스트 전건 PASS ≠ 배포 가능",
              f"· 독립 Judge {ev['judge_avg']}점 · 기준 {ev['minimum']:.0f}점",
              "· 배포 판정은 가장 낮은 증적을 따른다",
              "· 중대 위반 0건이어도 승인은 별개"])
    add_card(slide, Inches(4.75), Inches(2.05), Inches(3.8), Inches(2.25),
             "발견한 결함",
             ["· 정책 구체성 부족 — 담당·기한·수치 누락",
              "· 검색 결과 없을 때 개선안 미생성 2건",
              "· 요약이 원문 대비 지나치게 단순",
              "· 케이스별 점수 편차 20점"],
             heading_color=WARN)
    add_card(slide, Inches(8.75), Inches(2.05), Inches(3.9), Inches(2.25),
             "다음 개선안",
             ["· 정책 프롬프트에 담당·기한·KPI 필수화",
              "· 검색 0건 전용 응답 규칙 추가",
              "· 재평가 후 95점 재도전",
              "· 사람 검토 승인 절차 기록"],
             heading_color=GOOD)
    add_panel(slide, Inches(0.75), Inches(4.85), Inches(11.9), Inches(1.35),
              fill=RGBColor(0x0F, 0x33, 0x38), line=CYAN)
    frame = add_textbox(slide, Inches(1.05), Inches(5.08), Inches(11.3), Inches(1.0))
    write(frame, "생성 결과가 아니라, 신뢰할 수 있는 판정 과정을 만들었습니다.",
          size=21, color=CYAN, bold=True, space_after=6, first=True)
    write(frame, "품질 판정 → 증적 보관 → 운영 감사 → 리소스 삭제까지 하나의 흐름으로 완주했습니다.",
          size=13, color=MUTED)
    set_notes(slide, "마무리 40초. 결함 3~4개와 개선안을 짝지어 말하고, 마지막 문장으로 끝냅니다.")


def main() -> None:
    ev = load_evidence()
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    build(prs, ev)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    print(f"발표자료 생성: {OUTPUT}")
    print(f"슬라이드 {len(prs.slides.__iter__.__self__._sldIdLst)}장")


if __name__ == "__main__":
    main()
