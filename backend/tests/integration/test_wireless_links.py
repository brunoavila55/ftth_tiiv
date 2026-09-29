from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import create_test_user, login_test_client


def test_radio_link_lifecycle_and_endpoint_integrity(client: TestClient, db_session: Session) -> None:
    user = create_test_user(db_session, "wireless-engineer@example.com", role="engineer")
    csrf = login_test_client(client, user.email)
    headers = {"X-CSRF-Token": csrf}
    site_ids: list[str] = []
    radio_ids: list[str] = []

    for code, kind in (("WPOP-01", "wireless_pop"), ("TORRE-01", "radio_tower")):
        response = client.post(
            "/api/v1/sites",
            json={
                "code": code,
                "name": code,
                "kind": kind,
                "location": {"type": "Point", "coordinates": [-53.0, -30.0]},
            },
            headers=headers,
        )
        assert response.status_code == 201
        site_ids.append(response.json()["id"])

    for code, site_id in zip(("RADIO-01", "RADIO-02"), site_ids, strict=True):
        response = client.post(
            "/api/v1/devices",
            json={
                "code": code,
                "kind": "radio",
                "manufacturer": "Fabricante",
                "model": "Modelo",
                "site_id": site_id,
            },
            headers=headers,
        )
        assert response.status_code == 201
        radio_ids.append(response.json()["id"])

    filtered_radios = client.get(
        "/api/v1/devices", params={"kind": "radio", "site_id": site_ids[0]}
    )
    assert filtered_radios.status_code == 200
    assert filtered_radios.json()["total"] == 1
    assert filtered_radios.json()["items"][0]["id"] == radio_ids[0]

    payload = {
        "code": "ENLACE-01",
        "name": "Tronco wireless",
        "site_a_id": site_ids[0],
        "site_b_id": site_ids[1],
        "radio_a_id": radio_ids[0],
        "radio_b_id": radio_ids[1],
        "frequency_mhz": 5800,
        "channel_width_mhz": 40,
        "status": "installed",
    }
    invalid = client.post(
        "/api/v1/radio-links", json={**payload, "radio_b_id": radio_ids[0]}, headers=headers
    )
    assert invalid.status_code == 422
    mismatched = client.post(
        "/api/v1/radio-links", json={**payload, "radio_a_id": radio_ids[1]}, headers=headers
    )
    assert mismatched.status_code == 422

    created = client.post("/api/v1/radio-links", json=payload, headers=headers)
    assert created.status_code == 201
    link_id = created.json()["id"]
    assert created.headers["etag"] == '"1"'

    changed_site_type = client.patch(
        f"/api/v1/sites/{site_ids[0]}",
        json={"kind": "pop"},
        headers={**headers, "If-Match": '"1"'},
    )
    assert changed_site_type.status_code == 409

    listed = client.get("/api/v1/radio-links", params={"site_id": site_ids[1]})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == link_id

    missing_version = client.patch(
        f"/api/v1/radio-links/{link_id}", json={"channel_width_mhz": 20}, headers=headers
    )
    assert missing_version.status_code == 428
    updated = client.patch(
        f"/api/v1/radio-links/{link_id}",
        json={"channel_width_mhz": 20},
        headers={**headers, "If-Match": '"1"'},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["channel_width_mhz"] == 20
    stale = client.patch(
        f"/api/v1/radio-links/{link_id}",
        json={"channel_width_mhz": 10},
        headers={**headers, "If-Match": '"1"'},
    )
    assert stale.status_code == 412

    moved_radio = client.patch(
        f"/api/v1/devices/{radio_ids[0]}",
        json={"site_id": site_ids[1]},
        headers={**headers, "If-Match": '"1"'},
    )
    assert moved_radio.status_code == 409

    removed = client.delete(
        f"/api/v1/radio-links/{link_id}", headers={**headers, "If-Match": '"2"'}
    )
    assert removed.status_code == 204
