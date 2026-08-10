"""각 테스트 실행을 TXT·XML·HTML 증적으로 별도 보존합니다."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


REPORTS = Path(__file__).resolve().parent / "reports"


def _status_row(row: dict[str, Any]) -> dict[str, str]:
    quality = row.get("quality") or {}
    deployment = row.get("deployment") or {}
    raw_status = row.get("status")
    if raw_status is None:
        if deployment:
            raw_status = "PASS" if deployment.get("deployable") else "FAIL"
        else:
            raw_status = "PASS" if quality.get("passed", row.get("passed", False)) else "FAIL"
    return {
        "id": str(row.get("case_id") or row.get("test") or row.get("id") or "unknown"),
        "status": str(raw_status),
        "score": str(quality.get("score", row.get("score", ""))),
        "detail": str(row.get("detail") or row.get("message") or ""),
    }


def _summary(payload: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    source = payload.get("summary") or payload
    total = int(source.get("total", len(rows)) or len(rows))
    passed = int(source.get("passed", sum(row["status"] == "PASS" for row in rows)) or 0)
    failed = int(source.get("failed", max(total - passed, 0)) or 0)
    errors = int(source.get("errors", 0) or 0)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "successful": bool(source.get("successful", failed == 0 and errors == 0)),
        "average_score": source.get("average_score"),
    }


def write_execution_evidence(
    event_type: str,
    payload: dict[str, Any],
    output_dir: Path = REPORTS,
) -> dict[str, str]:
    """한 번의 테스트 실행을 세 형식과 누적 이력으로 기록합니다."""
    now = datetime.now().astimezone()
    stamp = now.strftime("%Y%m%d_%H%M%S_%f")
    safe_type = "".join(char if char.isalnum() or char in "_-" else "_" for char in event_type)
    base = output_dir / f"test_evidence_{safe_type}_{stamp}"
    rows = [_status_row(row) for row in payload.get("results") or []]
    summary = _summary(payload, rows)
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_path = base.with_suffix(".txt")
    xml_path = base.with_suffix(".xml")
    html_path = base.with_suffix(".html")
    junit_path = Path(f"{base}.junit.xml")
    verdict = "PASS" if summary["successful"] else "FAIL"

    txt_lines = [
        "VOC 품질 테스트 실행 증적",
        f"실행 유형: {event_type}",
        f"실행 시각: {now.isoformat(timespec='seconds')}",
        f"결과: {summary['passed']}/{summary['total']} PASS",
        f"실패: {summary['failed']}, 오류: {summary['errors']}",
        f"최종 판정: {verdict}",
    ]
    if summary["average_score"] is not None:
        txt_lines.append(f"평균 점수: {summary['average_score']}/100")
    txt_lines.extend(["", "[상세 결과]"])
    txt_lines.extend(
        f"- {row['id']} | {row['status']} | score={row['score']} | {row['detail']}"
        for row in rows
    )
    txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

    root = ET.Element("qualityEvidence", {
        "eventType": event_type,
        "generatedAt": now.isoformat(timespec="seconds"),
        "verdict": verdict,
    })
    ET.SubElement(root, "summary", {
        "total": str(summary["total"]),
        "passed": str(summary["passed"]),
        "failed": str(summary["failed"]),
        "errors": str(summary["errors"]),
        "averageScore": "" if summary["average_score"] is None else str(summary["average_score"]),
    })
    cases = ET.SubElement(root, "cases")
    for row in rows:
        case = ET.SubElement(cases, "case", {"id": row["id"], "status": row["status"]})
        ET.SubElement(case, "score").text = row["score"]
        ET.SubElement(case, "detail").text = row["detail"]
    ET.indent(root)
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)

    junit = ET.Element("testsuite", {
        "name": event_type,
        "tests": str(summary["total"]),
        "failures": str(summary["failed"]),
        "errors": str(summary["errors"]),
        "timestamp": now.isoformat(timespec="seconds"),
    })
    for row in rows:
        case = ET.SubElement(junit, "testcase", {
            "classname": f"voc.quality.{safe_type}",
            "name": row["id"],
        })
        if row["status"] != "PASS":
            failure = ET.SubElement(case, "failure", {
                "message": row["detail"] or row["status"],
                "type": "QualityGateFailure",
            })
            failure.text = f"status={row['status']}; score={row['score']}"
    ET.indent(junit)
    ET.ElementTree(junit).write(junit_path, encoding="utf-8", xml_declaration=True)

    table_rows = "".join(
        "<tr><td>{}</td><td class='{}'>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(row["id"]),
            "pass" if row["status"] == "PASS" else "fail",
            html.escape(row["status"]),
            html.escape(row["score"]),
            html.escape(row["detail"]),
        )
        for row in rows
    )
    html_path.write_text(f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>VOC 테스트 증적 - {html.escape(event_type)}</title><style>
body{{font-family:'Malgun Gothic',sans-serif;margin:36px;background:#f4f7fb;color:#172033}}
.card{{background:white;border:1px solid #d8e0eb;border-radius:14px;padding:22px;margin-bottom:18px}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.metric{{background:#eef5ff;padding:16px;border-radius:10px}}
.metric b{{display:block;font-size:28px;color:#0758a8}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #d8e0eb;padding:9px;text-align:left}}
th{{background:#163a5f;color:white}}.pass{{color:#087a3e;font-weight:bold}}.fail{{color:#c52c2c;font-weight:bold}}
</style></head><body><h1>VOC 품질 테스트 실행 증적</h1><p>{now.isoformat(timespec='seconds')} · {html.escape(event_type)}</p>
<div class="metrics"><div class="metric">전체<b>{summary['total']}</b></div><div class="metric">PASS<b>{summary['passed']}</b></div><div class="metric">FAIL<b>{summary['failed']}</b></div><div class="metric">판정<b>{verdict}</b></div></div>
<div class="card"><h2>상세 결과</h2><table><thead><tr><th>ID</th><th>상태</th><th>점수</th><th>상세</th></tr></thead><tbody>{table_rows}</tbody></table></div>
</body></html>""", encoding="utf-8")

    record = {
        "event_type": event_type,
        "generated_at": now.isoformat(timespec="seconds"),
        **summary,
        "verdict": verdict,
        "files": {
            "txt": txt_path.name,
            "xml": xml_path.name,
            "html": html_path.name,
            "junit": junit_path.name,
        },
    }
    with (output_dir / "test_execution_history.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {
        "txt": str(txt_path),
        "xml": str(xml_path),
        "html": str(html_path),
        "junit": str(junit_path),
    }
