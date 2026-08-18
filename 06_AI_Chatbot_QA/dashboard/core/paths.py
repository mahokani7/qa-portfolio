from pathlib import Path

TOPBAR_HEIGHT = "60px"
DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = DASHBOARD_DIR.parent
WORKSPACE_DIR = PROJECT_DIR.parent
RULE_PROJECT_DIR = PROJECT_DIR
DATA_DIR = PROJECT_DIR / "data"
REPORTS_DIR = PROJECT_DIR / "reports"
K6_RUNS_DIR = REPORTS_DIR / "k6_runs"
RULE_KNOWLEDGE_UPLOAD_DIR = PROJECT_DIR / "data" / "knowledge" / "uploads"
SUPPORTED_KNOWLEDGE_EXTENSIONS = {".txt", ".md", ".docx", ".pdf"}
TESTCASE_DATA_DIR = DATA_DIR / "testcases"
TESTCASE_UPLOADS_DIR = TESTCASE_DATA_DIR / "uploads"
TESTCASE_RUNS_DIR = REPORTS_DIR / "test_runs"
TESTCASE_UPLOADS_FILE = TESTCASE_DATA_DIR / "testcase_uploads.json"
TESTCASE_HISTORY_FILE = TESTCASE_DATA_DIR / "testcase_execution_history.json"
JIRA_REGISTERED_ISSUES_FILE = DATA_DIR / "jira_registered_issues.json"
LEGACY_TESTCASE_UPLOADS_FILE = DATA_DIR / "testcase_uploads.json"
LEGACY_TESTCASE_HISTORY_FILE = DATA_DIR / "testcase_execution_history.json"
