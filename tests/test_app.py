import os

import pytest
from dotenv import load_dotenv

load_dotenv(".env-test")

from main import app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)

    with app.test_client() as client:
        yield client


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "ok"
    assert data["version"] == "0.1.4"


def test_login(client):
    response = client.post(
        "/login",
        data={
            "email": "test@test.com",
            "password": os.environ["TEST_PASSWORD"],
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_flight_search(client):
    login_response = client.post(
        "/login",
        data={
            "email": "test@test.com",
            "password": os.environ["TEST_PASSWORD"],
        },
    )

    assert login_response.status_code == 302

    response = client.post(
        "/find-flights",
        data={
            "departure_state": "Delaware",
            "arrival_state": "Illinois",
            "departure_time": "2026-07-28",
        },
    )

    assert response.status_code == 200
    assert b"Delaware" in response.data
    assert b"Illinois" in response.data
