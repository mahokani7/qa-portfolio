from services.k6_service import K6RunSettings, build_k6_script, normalize_k6_summary


def test_build_k6_script_contains_thresholds_and_target_url():
    settings = K6RunSettings(
        target_url="http://localhost:8000/health",
        vus=5,
        duration_seconds=30,
        ramp_up_seconds=10,
        p95_threshold_ms=1500,
        failure_rate_threshold_pct=2.5,
        checks_threshold_pct=97.0,
    )

    script = build_k6_script(settings)

    assert "http://localhost:8000/health" in script
    assert "target: 5" in script
    assert "p(95)<1500" in script
    assert "rate<0.0250" in script
    assert "rate>0.9700" in script


def test_normalize_k6_summary_converts_ms_and_rates():
    summary = {
        "metrics": {
            "http_reqs": {"count": 200, "rate": 20},
            "http_req_failed": {"rate": 0.015},
            "http_req_duration": {"avg": 1850, "p(90)": 3200, "p(95)": 3920, "p(99)": 5000},
            "checks": {"rate": 0.985},
            "vus_max": {"value": 20},
        }
    }

    normalized = normalize_k6_summary(summary)

    assert normalized["total_requests"] == 200
    assert normalized["failure_rate"] == 1.5
    assert normalized["avg_duration_seconds"] == 1.85
    assert normalized["p95_duration_seconds"] == 3.92
    assert normalized["checks_rate"] == 98.5
    assert normalized["vus"] == 20
