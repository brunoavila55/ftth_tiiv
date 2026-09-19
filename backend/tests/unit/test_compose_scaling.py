"""R21 (EST-14): o compose precisa permitir `--scale`, agendar backup e rodar os scripts do worker."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = yaml.safe_load((ROOT / "compose.yaml").read_text())


def test_scalable_services_have_no_fixed_container_name() -> None:
    for name in ("backend", "worker", "frontend"):
        assert "container_name" not in COMPOSE["services"][name], (
            f"{name}: container_name fixo impede `docker compose --scale`"
        )


def test_worker_has_heartbeat_healthcheck() -> None:
    assert COMPOSE["services"]["worker"]["healthcheck"]["test"][-1].endswith(
        "check_worker_heartbeat.py"
    )


def test_backup_service_is_opt_in_and_uses_a_dedicated_volume() -> None:
    backup = COMPOSE["services"]["backup"]
    assert backup["profiles"] == ["backup"]  # não sobe por padrão
    assert any(v.startswith("backups:") for v in backup["volumes"])
    assert "backups" in COMPOSE["volumes"]
    assert "BACKUP_SIGNING_KEY" in backup["environment"]


def test_backend_image_can_import_app_from_scripts() -> None:
    """`python scripts/run_worker.py` roda com sys.path[0]=/app/scripts: precisa de PYTHONPATH=/app."""
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text()
    assert "ENV PYTHONPATH=/app" in dockerfile


def test_ci_smoke_imports_the_worker_inside_the_image() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "scripts/run_worker.py" in ci
