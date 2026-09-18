from fastapi.testclient import TestClient


def test_dashboard_summary_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    data = response.json()

    assert "total_sites" in data
    assert "total_structures" in data
    assert "total_cables" in data
    assert "topology_revision" in data
    assert "ctos_occupancy" in data
    assert "incomplete_documentation_alerts" in data

    assert isinstance(data["total_sites"], int)
    assert isinstance(data["total_structures"], int)
    assert isinstance(data["total_cables"], int)
    assert isinstance(data["incomplete_documentation_alerts"], list)


def test_global_search_endpoint(client: TestClient) -> None:
    # Busca com termo válido
    response = client.get("/api/v1/search?q=POP")
    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "POP"
    assert "total_results" in data
    assert "groups" in data
    assert isinstance(data["groups"], list)

    # Rejeita busca com termo muito curto (<2 caracteres)
    invalid_resp = client.get("/api/v1/search?q=a")
    assert invalid_resp.status_code == 422
