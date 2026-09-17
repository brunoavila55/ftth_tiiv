import uuid

from fastapi import status
from fastapi.testclient import TestClient


def test_request_id_generated_automatically(client: TestClient) -> None:
    resp = client.get("/health/live")
    assert resp.status_code == status.HTTP_200_OK
    assert "X-Request-ID" in resp.headers

    req_id = resp.headers["X-Request-ID"]
    # Valida se é um UUID válido
    parsed_uuid = uuid.UUID(req_id)
    assert str(parsed_uuid) == req_id


def test_request_id_propagates_client_provided_id(client: TestClient) -> None:
    custom_id = "custom-test-req-id-12345"
    resp = client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.headers.get("X-Request-ID") == custom_id
