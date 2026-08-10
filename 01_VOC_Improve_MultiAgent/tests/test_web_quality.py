"""웹 품질 운영 화면과 비용 보호 API 회귀 테스트."""

import asyncio
import grpc
import re
import shutil
import subprocess
import unittest
import os
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

import web_app
from presentation import PRESENTATION_PAGE


class WebQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(web_app.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_analyze_redacts_invalid_api_key_and_returns_auth_status(self):
        secret = "sk-proj-" + "x" * 32
        error = grpc.aio.AioRpcError(
            grpc.StatusCode.INTERNAL,
            details=f"Interpreter error: Error code: 401 - invalid_api_key: {secret}",
        )
        with patch.object(web_app.runtime, "run_with_diagnostics", AsyncMock(side_effect=error)):
            response = self.client.post(
                "/analyze", json={"question": "결제가 되지 않아요", "task": "both"}
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error_code"], "API_AUTHENTICATION_FAILED")
        self.assertNotIn(secret, response.text)

    def test_analyze_returns_credit_error_without_provider_payload(self):
        error = grpc.aio.AioRpcError(
            grpc.StatusCode.INTERNAL,
            details=(
                "Improver.Improve error: Anthropic API: Your credit balance is too low "
                "to access the API. Please go to Plans & Billing to purchase credits."
            ),
        )
        with patch.object(web_app.runtime, "run_with_diagnostics", AsyncMock(side_effect=error)):
            response = self.client.post(
                "/analyze", json={"question": "결제가 되지 않아요", "task": "both"}
            )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["error_code"], "API_CREDIT_EXHAUSTED")
        self.assertIn("결제", response.json()["message"])
        self.assertNotIn("Plans & Billing", response.text)

    def test_report_center_uses_qa_facing_korean_run_titles(self):
        response = self.client.get("/reports")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("장애 허용성 진단", html)
        self.assertIn("내부 실행 ID:", html)
        self.assertIn("runKindName(bundle.kind)", html)
        self.assertNotIn("<summary><b>Run ", html)

    def test_index_exposes_all_quality_operations(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        for expected in (
            "QA Control Center",
            "Release Command Center",
            "기준선 ↔ 후보 회귀 비교",
            "6-Agent Trace",
            "Human Review · 승인 워크벤치",
            "테스트 케이스 · 결과/실패 원인 Explorer",
            "자동 검토 큐",
            "중앙 실행 설정",
            "프롬프트·모델·데이터 버전",
            "Noise Sensitivity",
            "비용·드리프트 기준",
            "반복 안정성·Flakiness",
            "OWASP Red Team",
            "CI 품질 게이트",
            "실행 취소",
            "품질 운영·보고서",
            "자동 품질 테스트",
            "장애 진단",
            "외부 LLM E2E",
            "실제 API 라이브 E2E",
            "2건(권장)",
            "재시험 보고서 통합",
            "독립 LLM Judge",
            "최종 배포 판단",
            "배포 기준 점수",
            "기준 점수 저장",
            "35건 종합 보고서 생성",
            "개발 발표자료 열기",
        ):
            self.assertIn(expected, response.text)
        self.assertIn("오프라인 대체는 사용하지 않습니다", response.text)
        self.assertNotIn('id="confirmRepeatCost"', response.text)
        self.assertNotIn('id="confirmLiveCost"', response.text)
        self.assertNotIn('id="confirmJudgeCost"', response.text)
        self.assertNotIn('value="deterministic">Deterministic', response.text)

    def test_control_center_history_detail_and_compare_apis(self):
        dashboard = self.client.get("/quality/control-center")
        self.assertEqual(dashboard.status_code, 200)
        self.assertTrue(dashboard.json()["ok"])
        self.assertIn("trends", dashboard.json())
        self.assertIn("drift_alerts", dashboard.json())
        self.assertIn("recent_summary", dashboard.json())
        self.assertEqual(dashboard.json()["recent_summary"]["window_days"], 7)

        history = self.client.get("/quality/runs?limit=10")
        self.assertEqual(history.status_code, 200)
        runs = history.json()["runs"]
        self.assertGreaterEqual(len(runs), 2)
        detail = self.client.get(f"/quality/runs/{runs[0]['run_id']}")
        self.assertEqual(detail.status_code, 200)
        detailed_run = detail.json()["run"]
        self.assertIn("cases", detailed_run)
        self.assertIn("source_payload", detailed_run)
        if detailed_run["cases"]:
            self.assertIn("raw", detailed_run["cases"][0])

        comparison = self.client.post(
            "/quality/compare",
            json={
                "baseline_run_id": runs[1]["run_id"],
                "candidate_run_id": runs[0]["run_id"],
            },
        )
        self.assertEqual(comparison.status_code, 200)
        self.assertIn("release_gate", comparison.json()["comparison"]["summary"])

    def test_control_center_validates_approval_and_compare_inputs(self):
        same = self.client.post(
            "/quality/compare",
            json={"baseline_run_id": "same", "candidate_run_id": "same"},
        )
        self.assertEqual(same.status_code, 400)

        invalid = self.client.post(
            "/quality/approvals",
            json={"run_id": "missing", "reviewer": "", "decision": "APPROVED"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_approval_page_uses_qa_case_data_instead_of_report_filenames(self):
        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("실제 AI/Judge 응답 보기", html)
        self.assertIn("검토 대상 테스트 케이스 ", html)
        self.assertIn("등록된 검토자 의견(참고)", html)
        self.assertIn("기존 검토 메모의 문자 인코딩이 손상", html)
        self.assertIn("질문: ", html)
        self.assertNotIn("esc(item.source_file)", html)
        self.assertLess(html.index('id="reviewQueueTitle"'), html.index('id="evaluationTitle"'))
        for element_id in (
            "approvalQueueDate", "approvalQueueRun", "approvalQueueStatus",
            "approvalQueueSearch", "selectedReviewContext", "approvalEvaluationFields",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('<fieldset id="approvalEvaluationFields" disabled>', html)
        self.assertIn("function filteredApprovalQueue", html)
        self.assertIn("function selectApprovalReview", html)
        self.assertIn("function selectManualApproval", html)
        self.assertIn(".approval-filter-grid label { display:grid;", html)
        self.assertIn(".approval-filter-grid input, .approval-filter-grid select { display:block; width:100%; max-width:100%; min-width:0; }", html)
        self.assertIn("#approvalQueueRun { overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }", html)

    def test_case_review_version_and_preview_apis(self):
        cases = self.client.get("/quality/cases?limit=5&defects_only=true")
        self.assertEqual(cases.status_code, 200)
        self.assertIn("cases", cases.json())

        queue = self.client.get("/quality/review-queue?limit=5")
        self.assertEqual(queue.status_code, 200)
        self.assertIn("queue", queue.json())

        versions = self.client.get("/quality/versions?limit=5")
        self.assertEqual(versions.status_code, 200)
        self.assertTrue(versions.json()["versions"])
        self.assertIn("git_commit", versions.json()["versions"][0])

        if (web_app.REPORTS_PATH / "test_result.json").is_file():
            preview = self.client.get("/quality/report-preview/test_result.json")
            self.assertEqual(preview.status_code, 200)
            self.assertIn("content", preview.json())

    def test_case_explorer_detail_shows_actual_response_and_trace(self):
        response = self.client.get("/test-cases")

        self.assertEqual(response.status_code, 200)
        for expected in (
            'id="caseDetailPanel"',
            'id="caseDetailContent"',
            'id="closeCaseDetail"',
            "function loadCaseExplorerDetail",
            "function renderCaseExplorerDetail",
            "실제 VOC 요약 응답",
            "실제 정책 개선안 응답",
            "6-Agent 단계별 실제 수행결과",
            "renderAgentResultTable(trace)",
            "function renderAutomatedTestDetail",
            "자동 품질 테스트입니다.",
            "품질 점수<b>적용 대상 아님",
            "개발자용 원본 식별자·소스 보기",
        ):
            self.assertIn(expected, response.text)
        self.assertNotIn('id="caseDefectsOnly" type="checkbox" checked', response.text)
        self.assertIn('class="control-toolbar case-filter-toolbar"', response.text)
        self.assertIn('class="case-checkbox"><input id="caseDefectsOnly"', response.text)
        self.assertIn(".case-filter-toolbar .case-checkbox { display:flex;", response.text)
        self.assertIn(".case-filter-toolbar > button { display:block; width:100%; max-width:100%; min-width:0; }", response.text)
        self.assertNotIn('<pre id="caseDetailPanel"', response.text)

    def test_run_history_page_exposes_full_data_and_word_report_actions(self):
        response = self.client.get("/runs")

        self.assertEqual(response.status_code, 200)
        for expected in (
            "테스트 수행결과 이력",
            'id="runDetailPanel"',
            'class="run-detail-layer" role="dialog" aria-modal="true"',
            'class="run-detail-dialog"',
            'id="runDetailMetadata"',
            'id="downloadRunWord"',
            "run-detail-button",
            "/report.docx",
            "loadRunHistoryDetail",
            "renderExpectationTable",
            "renderRubricTable",
            "renderRagTable",
            "renderAgentResultTable",
            "runResultText",
            "요약 복사",
            "Word 최종보고서 다운로드",
            "function auditRunDetailData",
            "function openRunDetailLayer",
            "function closeRunDetailLayer",
            "표시 데이터 검증",
            "RAG 6지표 종합",
            "지표 판정",
            'class="run-actions"',
            'class="run-action word"',
        ):
            self.assertIn(expected, response.text)
        for prohibited in (
            'id="runDetailRaw"',
            "원본 케이스 JSON",
            "실행 원본·메타데이터 전체 보기",
            "JSON.stringify(run, null, 2)",
            '$("runDetailPanel").scrollIntoView',
        ):
            self.assertNotIn(prohibited, response.text)
        self.assertIn('class="control-toolbar run-filter-toolbar"', response.text)
        self.assertIn('class="run-checkbox"><input id="runDefectsOnly"', response.text)
        self.assertIn(".run-filter-toolbar .run-checkbox { display:flex;", response.text)
        self.assertIn(".run-filter-toolbar > button { display:block; width:100%; max-width:100%; min-width:0; }", response.text)

    def test_run_history_word_report_download_endpoint(self):
        history = self.client.get("/quality/runs?limit=10")
        self.assertEqual(history.status_code, 200)
        run_id = history.json()["runs"][0]["run_id"]
        fake_report = web_app.REPORTS_PATH / "_test_run_history_report.docx"
        fake_report.write_bytes(b"PK\x03\x04test-docx")
        try:
            with patch("web_app.build_history_word_report", return_value=fake_report):
                response = self.client.get(f"/quality/runs/{run_id}/report.docx")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.headers.get("content-type"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            self.assertIn(".docx", response.headers.get("content-disposition", ""))
        finally:
            fake_report.unlink(missing_ok=True)

    def test_quality_results_use_structured_values_and_adaptive_cards(self):
        response = self.client.get("/quality")

        self.assertEqual(response.status_code, 200)
        for expected in (
            "grid-template-columns: repeat(2, minmax(0, 1fr))",
            ".ops-grid > .card.is-result-expanded",
            'id="artifactPreview" class="artifact-preview"',
            "function renderOperationResultData",
            "function renderResultRows",
            "item?.test_descriptor",
            "검증 내용 자세히 보기",
            "개발자용 내부 ID",
            "function renderArtifactResult",
            "function applyOperationCardLayout",
            "고급 기술 데이터(JSON) 보기",
            "케이스 단위 상세 결과",
            "결과 보기",
            "다운로드 전용",
        ):
            self.assertIn(expected, response.text)
        self.assertNotIn('<pre id="artifactPreview"', response.text)
        self.assertNotIn("<details open><summary>실행 결과 상세", response.text)

    @unittest.skipUnless(shutil.which("node"), "Node.js가 없어 웹 JavaScript 구문 검사를 건너뜁니다.")
    def test_embedded_javascript_has_valid_syntax(self):
        script = re.search(r"<script>(.*?)</script>", web_app.PAGE, re.DOTALL)
        self.assertIsNotNone(script)
        result = subprocess.run(
            [
                "node",
                "-e",
                "new Function(require('fs').readFileSync(0, 'utf8'));",
            ],
            input=script.group(1),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_javascript_element_references_exist_and_ids_are_unique(self):
        ids = re.findall(r'\bid="([^"]+)"', web_app.PAGE)
        self.assertEqual(len(ids), len(set(ids)), "HTML id가 중복되었습니다.")
        references = set(re.findall(r'\$\("([^"]+)"\)', web_app.PAGE))
        missing = sorted(references - set(ids))
        self.assertEqual(missing, [], f"JavaScript가 존재하지 않는 요소를 참조합니다: {missing}")

    def test_each_quality_action_has_an_independent_result_panel(self):
        expected_pairs = {
            "runQualitySuite": "resultQualitySuite",
            "runFault": "resultFault",
            "runRedTeam": "resultRedTeam",
            "runQualityGate": "resultQualityGate",
            "runOfflineE2E": "resultOfflineE2E",
            "runRepeatability": "resultRepeatability",
            "runLiveE2E": "resultLiveE2E",
            "mergeReports": "resultMergeReports",
            "runJudge": "resultJudge",
            "saveDeploymentThreshold": "resultDeploymentThreshold",
            "generateDeployment": "resultDeploymentDecision",
            "generateComprehensiveReport": "resultComprehensiveReport",
        }
        for button_id, result_id in expected_pairs.items():
            self.assertIn(f'id="{button_id}"', web_app.PAGE)
            self.assertIn(f'id="{result_id}"', web_app.PAGE)
            self.assertIn(f"{button_id}: '{result_id}'", web_app.PAGE)

        self.assertIn("const activeQualityJobs = new Map();", web_app.PAGE)
        self.assertIn("encodeURIComponent(jobId)", web_app.PAGE)
        self.assertNotIn("activeQualityJobId", web_app.PAGE)

    def test_enterprise_dashboard_design_is_default_and_accessible(self):
        for expected in (
            'class="system-bar"',
            'VOC QA Control Center',
            'AI QA 모니터링 대시보드',
            'class="system-link active"',
            'id="pageBreadcrumb"',
            'id="pageTitle"',
            'id="pageSubtitle"',
            'class="control-live-status"',
            'role="status" aria-live="polite"',
        ):
            self.assertIn(expected, web_app.PAGE)

        self.assertIn("localStorage.getItem('qaTheme') || 'light'", web_app.PAGE)
        self.assertIn("@media (max-width: 600px)", web_app.PAGE)
        self.assertNotIn('id="controlLiveStatus" class="sr-only"', web_app.PAGE)

    def test_control_center_home_renders_latest_quality_data(self):
        for expected in (
            'id="latestOverviewTitle"',
            'id="latestOverviewTime"',
            'id="latestQualityOverview"',
            'function renderLatestQualityOverview(control, quality)',
            'renderLatestQualityOverview(control, qualityResponse.ok ? quality : {});',
            'QUALITY SCORE',
            'PASS RATE',
            'SCORE DRIFT',
            'DEPLOY READINESS',
        ):
            self.assertIn(expected, web_app.PAGE)
        self.assertEqual(web_app.PAGE.count('<div class="latest-stat '), 6)
        self.assertIn('grid-template-areas:"quality pass recent" "drift deploy duration"', web_app.PAGE)
        self.assertEqual(web_app.PAGE.count('class="page-launch-card"'), 8)
        self.assertNotIn('<a class="page-launch-card" href="/settings"', web_app.PAGE)
        self.assertNotIn('id="recentGatePassRate"', web_app.PAGE)
        self.assertNotIn('function renderRecentSummary(control)', web_app.PAGE)
        self.assertLess(web_app.PAGE.index('class="latest-overview"'), web_app.PAGE.index('class="page-launch-grid"'))

    def test_batch_source_starts_empty_and_raw_json_is_collapsed(self):
        self.assertIn('id="batchSourceEditor" class="batch-source-editor"', web_app.PAGE)
        self.assertIn('고급 설정 · 테스트 데이터 원문 보기/편집', web_app.PAGE)
        self.assertIn('id="runBatch" class="sec" disabled', web_app.PAGE)
        self.assertIn('id="datasetInfo" class="notice"', web_app.PAGE)
        self.assertIn(
            "resetBatchSource();\nif (currentPanel === 'control') refreshControlCenter();",
            web_app.PAGE,
        )
        self.assertNotIn('\nloadTestSet();\nrefreshControlCenter();', web_app.PAGE)
        self.assertIn('$("bdomain").addEventListener("change", () => {', web_app.PAGE)
        self.assertIn('async function ensureBatchCsvPath()', web_app.PAGE)

    def test_sidebar_navigation_uses_dedicated_page_routes(self):
        expected = {
            "/control-center": ("control-center", "control"),
            "/dashboard": ("dashboard", "control"),
            "/single": ("single", "single"),
            "/batch": ("batch", "batch"),
            "/quality": ("quality", "quality"),
            "/test-cases": ("test-cases", "control"),
            "/runs": ("runs", "control"),
            "/compare": ("compare", "control"),
            "/trace": ("trace", "control"),
            "/security": ("security", "quality"),
            "/approvals": ("approvals", "control"),
            "/reports": ("reports", "control"),
            "/settings": ("settings", "control"),
        }
        for path, (view, panel) in expected.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    f'<body data-page-view="{view}" data-panel="{panel}">',
                    response.text,
                )
                self.assertIn(f'href="{path}"', response.text)

        self.assertIn("function applyPageRoute()", web_app.PAGE)
        self.assertIn("element.hidden = element.dataset.pageView !== currentPageView", web_app.PAGE)
        self.assertNotIn(".side-link[data-panel]", web_app.PAGE)

    def test_text_inputs_use_reference_inspired_enterprise_style(self):
        for expected in (
            'input:not([type="checkbox"]):not([type="radio"]):not([type="file"]),',
            'min-height:44px; padding:10px 13px;',
            'border-radius:9px;',
            'background:#f1f6fc; color:#172b43;',
            'border-color:#c3d7ed !important;',
            'box-shadow:0 0 0 3px #2c72b824',
            'textarea::placeholder { color:#7e93aa;',
        ):
            self.assertIn(expected, web_app.PAGE)

        self.assertIn(':not([type="checkbox"]):not([type="radio"]):not([type="file"])', web_app.PAGE)

    def test_release_score_uses_large_rectangular_result_card(self):
        for expected in (
            '.release-score { width:220px; min-height:132px;',
            'border-radius:10px; background:#071424;',
            '.release-score-value { color:#7dd3fc; font-size:3.5rem;',
            '.release-score-status {',
            '<span class="release-score-label">통합 품질 점수</span>',
            '<strong class="release-score-value">',
            "(pass ? 'APPROVED' : 'HOLD')",
            '.release-banner { align-items:stretch; flex-direction:column; }',
        ):
            self.assertIn(expected, web_app.PAGE)

        self.assertNotIn(
            '.release-score { width: 110px; aspect-ratio: 1; border-radius: 50%;',
            web_app.PAGE,
        )

    def test_top_navigation_uses_clickable_page_links(self):
        expected_links = {
            "종합 현황": "/dashboard",
            "테스트 관리": "/test-cases",
            "품질 운영": "/quality",
            "Agent Trace": "/trace",
            "품질 증적": "/reports",
        }
        for label, path in expected_links.items():
            with self.subTest(label=label):
                self.assertIn(f'href="{path}"', web_app.PAGE)
                self.assertRegex(
                    web_app.PAGE,
                    rf'<a class="system-link[^>]*" href="{re.escape(path)}"[^>]*>{re.escape(label)}</a>',
                )

        self.assertIn('class="system-brand" href="/control-center"', web_app.PAGE)
        self.assertIn("const topNavByView = {", web_app.PAGE)
        self.assertIn("document.querySelectorAll('.system-link[data-top-nav]')", web_app.PAGE)
        self.assertIn("link.setAttribute('aria-current', 'page')", web_app.PAGE)
        self.assertNotIn('<span class="system-link', web_app.PAGE)

    def test_dashboard_summary_is_hidden_from_other_control_pages(self):
        for expected in (
            '[hidden] { display:none !important; }',
            'body:not([data-page-view="dashboard"]) #panel-control [data-page-view="dashboard"] { display:none !important; }',
            'id="dashboardAnchor" class="sr-only" data-page-view="dashboard"',
            'id="controlLiveStatus" class="control-live-status" role="status" aria-live="polite" data-page-view="dashboard"',
            '<div class="control-hero" data-page-view="dashboard">',
            '<div class="control-grid" data-page-view="dashboard">',
        ):
            self.assertIn(expected, web_app.PAGE)

        for path, view in (
            ("/dashboard", "dashboard"),
            ("/test-cases", "test-cases"),
            ("/runs", "runs"),
            ("/compare", "compare"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(f'<body data-page-view="{view}" data-panel="control">', response.text)

    @unittest.skipUnless(shutil.which("node"), "Node.js가 없어 발표 JavaScript 구문 검사를 건너뜁니다.")
    def test_presentation_page_and_javascript(self):
        response = self.client.get("/presentation")
        self.assertEqual(response.status_code, 200)
        self.assertIn("VOC IMPROVE · DEVELOPMENT STORY", response.text)
        self.assertIn("앞으로 모든 개발은 이렇게 완료한다", response.text)
        self.assertIn('href="/presentation/deck">오늘 PPTX</a>', response.text)
        self.assertIn("Anthropic Judge / 100 · 7/16", response.text)
        self.assertIn("8월 3일에는 Judge를 재실행하지 않고", response.text)
        self.assertNotIn('<b class="metric">89/95</b>', response.text)
        self.assertEqual(response.text.count('class="slide'), 18)

        script = re.search(r"<script>(.*?)</script>", PRESENTATION_PAGE, re.DOTALL)
        self.assertIsNotNone(script)
        result = subprocess.run(
            ["node", "-e", "new Function(require('fs').readFileSync(0, 'utf8'));"],
            input=script.group(1),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_presentation_supporting_documents_are_available(self):
        for path, expected in (
            ("/presentation/material", "VOC 분석 및 QA 시스템 개발 발표자료"),
            ("/presentation/ledger", "개발 진행 발표 원장"),
            ("/presentation/principles", "상시 개발 원칙"),
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(expected.encode("utf-8"), response.content)

        deck = self.client.get("/presentation/deck")
        self.assertEqual(deck.status_code, 200)
        self.assertTrue(deck.content.startswith(b"PK"))
        self.assertGreater(len(deck.content), 70_000)

        material = self.client.get("/presentation/material").content.decode("utf-8")
        self.assertIn("2026-07-16T16:33:17+09:00", material)
        self.assertIn("2026-08-03에는 라이브 E2E와 Judge를 재실행하지 않았다", material)

    def test_quality_status_has_agents_results_and_reports(self):
        response = self.client.get("/quality/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["agents"]), 6)
        self.assertIn(payload["agent_runtime"]["state"], {"ready", "partial", "stopped"})
        self.assertEqual(payload["agent_runtime"]["total"], 6)
        self.assertIn("message", payload["agent_runtime"])
        self.assertIn("minimum_score", payload["deployment_config"])
        self.assertIn("technical_pass", payload["deployment_assessment"])
        self.assertEqual(
            set(payload["api_keys"]),
            {"openai_configured", "anthropic_configured"},
        )
        self.assertIsInstance(payload["e2e_reports"], list)
        self.assertIsInstance(payload["judge_reports"], list)
        self.assertIsInstance(payload["all_reports"], list)

    def test_deployment_threshold_can_be_saved_from_web(self):
        from unittest.mock import patch

        with patch("web_app.save_deployment_config") as save:
            save.return_value = {
                "minimum_score": 96.0,
                "default_score": 95.0,
                "source": "saved",
                "updated_at": "2026-07-15T12:00:00+09:00",
                "warning": "",
            }
            response = self.client.post(
                "/quality/deployment-threshold", json={"minimum_score": 96}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deployment_config"]["minimum_score"], 96)
        save.assert_called_once_with(96)

    def test_invalid_deployment_threshold_is_rejected(self):
        response = self.client.post(
            "/quality/deployment-threshold", json={"minimum_score": 101}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "INVALID_DEPLOYMENT_THRESHOLD")

    def test_live_e2e_runs_without_cost_consent(self):
        external = {
            "policy": "mandatory-live-llm", "e2e": {"summary": {"total": 1}},
            "judge": {"average_score": 90},
        }
        with patch("web_app._run_live_external_validation", AsyncMock(return_value=external)):
            response = self.client.post(
                "/quality/run-live-e2e",
                json={"domain": "ecommerce", "limit": 1, "confirm_cost": False},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["policy"], "mandatory-live-llm")

    def test_live_e2e_rejects_excessive_concurrency_before_api_call(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "configured", "ANTHROPIC_API_KEY": "configured"}):
            response = self.client.post(
                "/quality/run-live-e2e",
                json={"domain": "ecommerce", "limit": 1, "concurrency": 5},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("동시 실행 수", response.json()["message"])

    def test_live_e2e_returns_429_with_recovery_guidance(self):
        error = RuntimeError("HTTP 429 Too Many Requests")
        error.status_code = 429
        with patch.dict(os.environ, {"OPENAI_API_KEY": "configured", "ANTHROPIC_API_KEY": "configured"}):
            with patch("web_app.run_e2e", AsyncMock(side_effect=error)):
                response = self.client.post(
                    "/quality/run-live-e2e",
                    json={"domain": "ecommerce", "limit": 1, "confirm_cost": True},
                )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error_code"], "API_RATE_LIMITED")
        self.assertIn("동시 실행을 1건", response.json()["message"])

    def test_live_judge_uses_env_profile_without_cost_consent(self):
        judged = {"average_score": 91, "json": "judge.json"}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai", "ANTHROPIC_API_KEY": "anthropic"}):
            with patch("web_app._latest_report", return_value=web_app.REPORTS_PATH / "live.json"):
                with patch("web_app.run_llm_judge", AsyncMock(return_value=judged)) as execute:
                    response = self.client.post(
                        "/quality/run-judge",
                        json={"provider": "deterministic", "confirm_cost": False},
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(execute.await_args.args[0], "anthropic")

    def test_repeatability_validates_trials_and_ignores_cost_consent(self):
        environment = {"OPENAI_API_KEY": "openai", "ANTHROPIC_API_KEY": "anthropic"}
        with patch.dict(os.environ, environment):
            invalid_trials = self.client.post(
                "/quality/run-repeatability",
                json={"mode": "offline", "domain": "ecommerce", "limit": 1, "trials": 1},
            )
        self.assertEqual(invalid_trials.status_code, 400)
        self.assertIn("2~5회", invalid_trials.json()["message"])

        result = {"summary": {"successful": True}, "results": []}
        with patch.dict(os.environ, environment):
            with patch("web_app.run_repeatability", AsyncMock(return_value=result)):
                live_without_consent = self.client.post(
                    "/quality/run-repeatability",
                    json={"mode": "offline", "domain": "ecommerce", "limit": 1, "trials": 2},
                )
        self.assertEqual(live_without_consent.status_code, 200)

    def test_repeatability_profile_is_automatically_selected_from_api_keys(self):
        cases = (
            ({}, ("live", "openai", False, False)),
            ({"OPENAI_API_KEY": "openai"}, ("live", "openai", False, False)),
            ({"ANTHROPIC_API_KEY": "anthropic"}, ("live", "anthropic", False, False)),
            ({"OPENAI_API_KEY": "openai", "ANTHROPIC_API_KEY": "anthropic"}, ("live", "anthropic", False, True)),
        )
        for environment, expected in cases:
            with self.subTest(environment=sorted(environment)):
                with patch.dict(os.environ, environment, clear=True):
                    profile = web_app._repeatability_profile()
                self.assertEqual(
                    (profile["mode"], profile["judge_provider"], profile["requires_cost_consent"], profile["ready"]),
                    expected,
                )

    def test_repeatability_endpoint_ignores_manual_mode_and_uses_key_profile(self):
        result = {"summary": {"successful": True, "total": 1, "passed": 1}, "results": []}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai", "ANTHROPIC_API_KEY": "anthropic"}):
            with patch("web_app.run_repeatability", AsyncMock(return_value=result)) as execute:
                response = self.client.post(
                    "/quality/run-repeatability",
                    json={
                        "mode": "offline", "judge_provider": "deterministic",
                        "domain": "ecommerce", "limit": 1, "trials": 2,
                        "confirm_cost": True,
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(execute.await_args.kwargs["mode"], "live")
        self.assertEqual(execute.await_args.kwargs["judge_provider"], "anthropic")
        self.assertEqual(response.json()["automatic_profile"]["label"], "라이브 E2E + 외부 LLM Judge")

    def test_security_results_are_rendered_as_qa_data_without_source_fields(self):
        response = self.client.get("/security")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("QA 검증 내용 자세히 보기", html)
        self.assertIn("실행 모드와 Judge는 설정된 API 키에 따라 자동 선택", html)
        self.assertNotIn('id="repeatMode"', html)
        self.assertNotIn('id="repeatJudge"', html)
        self.assertIn("!['runFault', 'runRedTeam', 'runQualityGate'].includes(buttonId)", html)

    def test_quality_gate_rejects_invalid_domain_before_execution(self):
        response = self.client.post(
            "/quality/run-quality-gate",
            json={"domain": "unknown", "minimum_score": 95},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "QUALITY_GATE_FAILED")

    def test_background_job_api_rejects_unknown_operation(self):
        response = self.client.post(
            "/quality/jobs", json={"operation": "delete-everything", "payload": {}}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "JOB_CREATE_FAILED")

    def test_local_quality_job_always_adds_live_external_validation(self):
        external = {"policy": "mandatory-live-llm", "e2e": {}, "judge": {}}
        with patch("web_app._run_fixed_script", AsyncMock(return_value={"output": "ok"})):
            with patch("web_app._read_json_file", return_value={"summary": {"passed": 30}}):
                with patch("web_app._run_live_external_validation", AsyncMock(return_value=external)) as live_gate:
                    result = asyncio.run(
                        web_app._execute_quality_job("quality-suite", {}, lambda *args: None)
                    )

        live_gate.assert_awaited_once()
        self.assertEqual(result["external_validation"]["policy"], "mandatory-live-llm")

    def test_optional_operator_token_protects_mutations(self):
        with patch.dict(os.environ, {"WEB_OPERATOR_TOKEN": "test-operator-token"}):
            denied = self.client.post(
                "/quality/compare",
                json={"baseline_run_id": "same", "candidate_run_id": "same"},
            )
            allowed = self.client.post(
                "/quality/compare",
                headers={"Authorization": "Bearer test-operator-token"},
                json={"baseline_run_id": "same", "candidate_run_id": "same"},
            )
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(denied.json()["error_code"], "AUTH_REQUIRED")
        self.assertEqual(allowed.status_code, 400)

    def test_sidebar_login_session_and_user_identity(self):
        self.client.post("/auth/logout")
        initial = self.client.get("/auth/status")
        self.assertEqual(initial.status_code, 200)
        self.assertFalse(initial.json()["authenticated"])

        login = self.client.post("/auth/login", json={"username": "최성우", "token": ""})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["user"]["name"], "최성우")
        status = self.client.get("/auth/status")
        self.assertTrue(status.json()["authenticated"])
        self.assertEqual(status.json()["user"]["role"], "admin")

        logout = self.client.post("/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertFalse(self.client.get("/auth/status").json()["authenticated"])

        for expected in (
            'class="nav-status"', 'id="navUserAvatar"', 'id="navUserName"',
            'id="navUserRole"', 'id="navAuthAction"', 'id="loginLayer"',
            'id="loginForm"', 'function refreshAuthState()',
        ):
            self.assertIn(expected, web_app.PAGE)

    def test_sidebar_login_requires_configured_token(self):
        self.client.post("/auth/logout")
        with patch.dict(os.environ, {"WEB_OPERATOR_TOKEN": "login-secret"}):
            denied = self.client.post("/auth/login", json={"username": "QA 사용자", "token": "wrong"})
            allowed = self.client.post("/auth/login", json={"username": "QA 사용자", "token": "login-secret"})
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)
        self.client.post("/auth/logout")

    def test_report_download_and_path_traversal_protection(self):
        report = web_app.REPORTS_PATH / "deployment_decision.md"
        if report.is_file():
            response = self.client.get(f"/quality/report/{report.name}")
            self.assertEqual(response.status_code, 200)

        with self.assertRaises(web_app.ValidationError):
            web_app._safe_report_path("../deployment_decision.md")

    def test_invalid_merge_report_is_rejected_without_file_changes(self):
        response = self.client.post(
            "/quality/merge-reports",
            json={"base_report": "missing.json", "retest_reports": []},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "REPORT_MERGE_FAILED")


if __name__ == "__main__":
    unittest.main()
