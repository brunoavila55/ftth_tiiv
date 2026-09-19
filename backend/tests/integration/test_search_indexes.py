"""R23 (PERF-06 / PERF-07): busca segura (escape de curingas), mínimo de 3 caracteres e índices."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.search import MIN_SEARCH_LENGTH, contains, escape_like
from app.modules.inventory.models import Site
from tests.conftest import create_test_user, login_test_client

TRIGRAM = [
    ("sites", "code"),
    ("sites", "name"),
    ("structures", "code"),
    ("cables", "code"),
    ("cables", "model"),
    ("devices", "code"),
    ("devices", "manufacturer"),
    ("devices", "model"),
    ("devices", "serial_number"),
    ("customers", "code"),
    ("customers", "name"),
    ("customers", "phone"),
    ("customers", "email"),
    ("users", "name"),
    ("users", "email"),
    ("ports", "notes"),
]
LIST_TABLES = ["sites", "structures", "devices", "ports", "users", "optical_profiles"]


def plan(db: Session, sql: str) -> str:
    db.execute(text("SET LOCAL enable_seqscan = off"))
    rows = db.execute(text("EXPLAIN " + sql)).all()
    db.rollback()
    return "\n".join(r[0] for r in rows)


def test_expected_indexes_exist(db_session: Session) -> None:
    names = set(db_session.scalars(text("SELECT indexname FROM pg_indexes")).all())
    for table, column in TRIGRAM:
        assert f"idx_{table}_{column}_trgm" in names, (table, column)
    for table in LIST_TABLES:
        assert f"idx_{table}_created_desc_id" in names, table
    assert {"idx_connections_created_desc", "idx_attachments_created_desc"} <= names
    assert (
        db_session.scalar(text("SELECT count(*) FROM pg_extension WHERE extname = 'pg_trgm'")) == 1
    )


def test_like_wildcards_in_the_term_are_escaped() -> None:
    assert escape_like("50%_\\x") == "50\\%\\_\\\\x"
    rendered = str(contains(Site.code, "a%b").compile(compile_kwargs={"literal_binds": True}))
    assert "ESCAPE" in rendered.upper() and "\\%" in rendered


@pytest.fixture
def engineer_client(client: TestClient, db_session: Session) -> TestClient:
    create_test_user(db_session, "busca@provedor.com.br", "engineer")
    login_test_client(client, "busca@provedor.com.br")
    return client


def add_sites(db: Session, *codes: str) -> None:
    for code in codes:
        db.add(
            Site(
                code=code,
                name=f"Nome {code}",
                kind="pop",
                status="installed",
                location="POINT(-46 -23)",
                version=1,
            )
        )
    db.commit()


def codes(resp: object) -> set[str]:
    return {item["code"] for item in resp.json()["items"]}  # type: ignore[attr-defined]


def test_percent_and_underscore_in_search_are_literal(
    engineer_client: TestClient, db_session: Session
) -> None:
    add_sites(db_session, "S-100%", "S-1000", "S-1005", "A_B-01", "AXB-01", "PLAIN-01")
    assert codes(engineer_client.get("/api/v1/sites", params={"q": "100%"})) == {"S-100%"}
    assert codes(engineer_client.get("/api/v1/sites", params={"q": "A_B"})) == {"A_B-01"}
    # termos comuns continuam funcionando (contém, sem diferenciar maiúsculas)
    assert codes(engineer_client.get("/api/v1/sites", params={"q": "plain"})) == {"PLAIN-01"}
    assert codes(engineer_client.get("/api/v1/sites", params={"q": "S-10"})) == {
        "S-100%",
        "S-1000",
        "S-1005",
    }
    # um curinga sozinho não casa "tudo"
    assert codes(engineer_client.get("/api/v1/sites", params={"q": "%"})) == {"S-100%"}


def test_global_search_requires_at_least_three_characters(
    engineer_client: TestClient, db_session: Session
) -> None:
    add_sites(db_session, "SITE-ALFA")
    assert MIN_SEARCH_LENGTH == 3
    assert engineer_client.get("/api/v1/search", params={"q": "AL"}).status_code == 422
    ok = engineer_client.get("/api/v1/search", params={"q": "ALF"})
    assert ok.status_code == status.HTTP_200_OK
    assert any(g["entity_type"] == "site" for g in ok.json()["groups"])


def test_global_search_treats_wildcards_literally(
    engineer_client: TestClient, db_session: Session
) -> None:
    add_sites(db_session, "PON-50%", "PON-500")
    resp = engineer_client.get("/api/v1/search", params={"q": "50%"})
    items = [i["code"] for g in resp.json()["groups"] for i in g["items"]]
    assert items == ["PON-50%"]


def populate(db: Session, table_sql: dict[str, str]) -> None:
    for sql in table_sql.values():
        db.execute(text(sql))
    db.commit()
    db.execute(text("ANALYZE"))


def test_ilike_searches_use_trigram_indexes(db_session: Session) -> None:
    populate(
        db_session,
        {
            "sites": "INSERT INTO sites (id, code, name, kind, status, location, version, created_at, updated_at) "
            "SELECT gen_random_uuid(), 'SITE-'||g, 'Local '||g, 'pop', 'installed', "
            "ST_GeomFromText('POINT(-46 -23)', 4326), 1, now(), now() FROM generate_series(1, 4000) g",
            "customers": "INSERT INTO customers (id, code, name, phone, email, version, created_at, updated_at) "
            "SELECT gen_random_uuid(), 'CLI-'||g, 'Cliente '||g, '119'||g, 'c'||g||'@x.com', 1, now(), now() "
            "FROM generate_series(1, 4000) g",
        },
    )
    sites_plan = plan(
        db_session, "SELECT * FROM sites WHERE code ILIKE '%2345%' OR name ILIKE '%2345%'"
    )
    assert "Bitmap Index Scan" in sites_plan and "_trgm" in sites_plan, sites_plan
    cust_plan = plan(
        db_session,
        "SELECT * FROM customers WHERE code ILIKE '%777%' OR name ILIKE '%777%' "
        "OR phone ILIKE '%777%' OR email ILIKE '%777%'",
    )
    assert cust_plan.count("Bitmap Index Scan") >= 4 and "_trgm" in cust_plan, cust_plan


def test_listing_order_uses_the_composite_created_at_index(db_session: Session) -> None:
    populate(
        db_session,
        {
            "sites": "INSERT INTO sites (id, code, name, kind, status, location, version, created_at, updated_at) "
            "SELECT gen_random_uuid(), 'LST-'||g, 'Lista '||g, 'pop', 'installed', "
            "ST_GeomFromText('POINT(-46 -23)', 4326), 1, now() - (g||' seconds')::interval, now() "
            "FROM generate_series(1, 4000) g",
        },
    )
    listing = plan(
        db_session, "SELECT * FROM sites ORDER BY created_at DESC, id OFFSET 2000 LIMIT 50"
    )
    assert "idx_sites_created_desc_id" in listing, listing
    assert "Sort" not in listing  # a ordenação vem do índice, sem ordenar a tabela toda
