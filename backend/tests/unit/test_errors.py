from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    TopologyRevisionConflictError,
    register_exception_handlers,
)


class SamplePayload(BaseModel):
    name: str
    port_count: int


def create_error_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test-not-found")
    def route_not_found() -> None:
        raise NotFoundError("Caixa CTO-01 não encontrada.")

    @app.get("/test-precondition-required")
    def route_precondition_required() -> None:
        raise PreconditionRequiredError()

    @app.get("/test-precondition-failed")
    def route_precondition_failed() -> None:
        raise PreconditionFailedError()

    @app.get("/test-conflict")
    def route_conflict() -> None:
        raise ConflictError("Porta já ocupada por outra fibra.")

    @app.get("/test-topology-conflict")
    def route_topo_conflict() -> None:
        raise TopologyRevisionConflictError()

    @app.post("/test-validation")
    def route_validation(data: SamplePayload) -> dict[str, str]:
        return {"result": "ok"}

    @app.get("/test-unhandled")
    def route_unhandled() -> None:
        raise RuntimeError("Unexpected internal crash")

    return app


def test_rfc7807_not_found_response() -> None:
    client = TestClient(create_error_test_app(), raise_server_exceptions=False)
    resp = client.get("/test-not-found")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["code"] == "resource_not_found"
    assert body["title"] == "Recurso não encontrado"
    assert body["detail"] == "Caixa CTO-01 não encontrada."
    assert body["status"] == 404


def test_rfc7807_precondition_errors() -> None:
    client = TestClient(create_error_test_app(), raise_server_exceptions=False)

    resp_req = client.get("/test-precondition-required")
    assert resp_req.status_code == status.HTTP_428_PRECONDITION_REQUIRED
    assert resp_req.json()["code"] == "precondition_required"

    resp_fail = client.get("/test-precondition-failed")
    assert resp_fail.status_code == status.HTTP_412_PRECONDITION_FAILED
    assert resp_fail.json()["code"] == "precondition_failed"


def test_rfc7807_conflict_errors() -> None:
    client = TestClient(create_error_test_app(), raise_server_exceptions=False)

    resp_conf = client.get("/test-conflict")
    assert resp_conf.status_code == status.HTTP_409_CONFLICT
    assert resp_conf.json()["code"] == "conflict"

    resp_topo = client.get("/test-topology-conflict")
    assert resp_topo.status_code == status.HTTP_409_CONFLICT
    assert resp_topo.json()["code"] == "topology_revision_conflict"


def test_rfc7807_validation_error_422() -> None:
    client = TestClient(create_error_test_app(), raise_server_exceptions=False)
    resp = client.post("/test-validation", json={"name": "CTO", "port_count": "invalid_int"})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["code"] == "validation_error"
    assert "errors" in body
    assert any(e["field"] == "port_count" for e in body["errors"])


def test_rfc7807_unhandled_500() -> None:
    client = TestClient(create_error_test_app(), raise_server_exceptions=False)
    resp = client.get("/test-unhandled")
    assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["code"] == "internal_server_error"
    assert "Unexpected internal crash" not in body["detail"]  # No internal trace leak
