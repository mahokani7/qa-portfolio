import time

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_normal_response():
    response = client.get(
        "/fault-lab?scenario=normal"
    )

    assert response.status_code == 200
    assert response.json()["scenario"] == "normal"


def test_delay_response():
    start_time = time.time()

    response = client.get(
        "/fault-lab?scenario=delay&delay_seconds=1"
    )

    elapsed_time = time.time() - start_time

    assert response.status_code == 200
    assert response.json()["scenario"] == "delay"
    assert elapsed_time >= 1


def test_error500_response():
    response = client.get(
        "/fault-lab?scenario=error500"
    )

    assert response.status_code == 500


def test_timeout_response():
    response = client.get(
        "/fault-lab?scenario=timeout&delay_seconds=1"
    )

    assert response.status_code == 504