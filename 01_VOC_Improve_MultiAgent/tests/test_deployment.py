"""Deployment-facing health and cookie security tests."""

import os
import unittest
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

import web_app


class DeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(web_app.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_healthz_requires_all_six_agents(self):
        with patch("web_app._endpoint_ready", new=AsyncMock(return_value=True)):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agents_ready"], 6)
        self.assertNotIn("endpoint", response.text)

    def test_healthz_reports_unhealthy_without_agents(self):
        with patch("web_app._endpoint_ready", new=AsyncMock(return_value=False)):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["ok"])

    def test_https_deployment_sets_secure_session_cookie(self):
        environment = {
            "WEB_ADMIN_TOKEN": "deployment-test-token",
            "WEB_COOKIE_SECURE": "true",
        }
        with patch.dict(os.environ, environment, clear=False):
            response = self.client.post(
                "/auth/login",
                json={"username": "deployment-test", "token": "deployment-test-token"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Secure", response.headers["set-cookie"])


if __name__ == "__main__":
    unittest.main()
