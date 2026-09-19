"""R26 (SEC-12): scripts de demonstração/carga não rodam em produção nem contra banco remoto."""

import sys
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine as real_create_engine

from app.core.script_safety import (
    ALLOW_FLAG,
    UnsafeTargetError,
    assert_safe_target,
    is_local_host,
)
from app.core.security import verify_password

LOCAL = "postgresql+psycopg://u:p@127.0.0.1:5432/ftth_manager"
REMOTE = "postgresql+psycopg://u:p@db.interna.example.com:5432/ftth_manager"


def test_local_hosts_are_recognized() -> None:
    for host in ("localhost", "127.0.0.1", "127.0.1.1", "::1", None, ""):
        assert is_local_host(host)
    for host in ("db", "10.0.0.5", "db.example.com", "192.168.0.10"):
        assert not is_local_host(host)


def test_production_is_always_refused_even_with_the_flag() -> None:
    for env in ("production", "PRODUCTION", " production "):
        with pytest.raises(UnsafeTargetError, match="production"):
            assert_safe_target(LOCAL, environment=env, allow_non_local=True)


def test_remote_host_needs_the_explicit_flag() -> None:
    with pytest.raises(UnsafeTargetError, match=ALLOW_FLAG):
        assert_safe_target(REMOTE, environment="development")
    assert_safe_target(REMOTE, environment="development", allow_non_local=True)


def test_local_dev_and_test_are_allowed() -> None:
    assert_safe_target(LOCAL, environment="development")
    assert_safe_target(LOCAL, environment="test")


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    argv: list[str],
    env: str,
    db_url: str,
) -> tuple[int | str | None, list[str]]:
    """Executa `main()` do script capturando se algum engine chegou a ser criado."""
    engines: list[str] = []

    def spy(url: str, *a: Any, **kw: Any) -> Any:
        engines.append(str(url))
        return real_create_engine(url, *a, **kw)

    monkeypatch.setattr(module, "create_engine", spy)
    monkeypatch.setenv("ENVIRONMENT", env)
    monkeypatch.setenv("DATABASE_URL", db_url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    code: int | str | None = None
    try:
        with patch.object(sys, "argv", ["script", *argv]):
            module.main()
    except SystemExit as exit_:
        code = exit_.code
    finally:
        get_settings.cache_clear()
    return code, engines


def _modules() -> list[tuple[str, Any, list[str]]]:
    from scripts import benchmark_endpoints, generate_synthetic_load, seed_demo

    return [
        ("seed_demo", seed_demo, ["--target-db", "dev"]),
        ("generate_synthetic_load", generate_synthetic_load, ["--db-url", REMOTE]),
        ("benchmark_endpoints", benchmark_endpoints, ["--target-db", "dev"]),
    ]


@pytest.mark.parametrize("index", [0, 1, 2])
def test_scripts_abort_in_production_without_touching_the_db(
    monkeypatch: pytest.MonkeyPatch, index: int
) -> None:
    name, module, argv = _modules()[index]
    code, engines = _run_main(monkeypatch, module, argv, "production", LOCAL)
    assert code == 2, name
    assert engines == [], f"{name} criou engine antes de recusar produção"


def test_remote_db_is_accepted_by_the_guard_with_the_flag() -> None:
    from app.core.script_safety import guard_or_exit

    guard_or_exit(REMOTE, environment="development", allow_non_local=True, script="x")  # não sai
    with pytest.raises(SystemExit) as exc:
        guard_or_exit(REMOTE, environment="production", allow_non_local=True, script="x")
    assert exc.value.code == 2


@pytest.mark.parametrize("index", [0, 1])  # o benchmark tem alvo fixo em 127.0.0.1
def test_scripts_abort_on_remote_db_without_the_flag(
    monkeypatch: pytest.MonkeyPatch, index: int
) -> None:
    name, module, argv = _modules()[index]
    code, engines = _run_main(monkeypatch, module, argv, "development", REMOTE)
    assert code == 2, name
    assert engines == [], f"{name} criou engine antes de recusar banco remoto"


def test_benchmark_checks_the_real_environment_not_the_one_it_forces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O benchmark força ENVIRONMENT=test para si; a guarda tem de olhar o valor de ANTES."""
    from scripts import benchmark_endpoints

    code, engines = _run_main(monkeypatch, benchmark_endpoints, [], "production", LOCAL)
    assert code == 2
    assert engines == []


def test_seed_admin_password_is_random_printed_once_and_works(
    db_session: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    from sqlalchemy import select

    from app.modules.identity.models import User
    from scripts.seed_demo import seed_demo_scenario

    seed_demo_scenario(db_session)
    out = capsys.readouterr().out
    admin = db_session.scalar(select(User).where(User.email == "admin@provedor.com.br"))
    assert admin is not None
    assert "AdminPass123!" not in out
    assert not verify_password(admin.password_hash, "AdminPass123!")
    marker = "anote agora): "
    assert marker in out
    printed = out.split(marker, 1)[1].splitlines()[0].strip()
    assert len(printed) >= 20
    assert verify_password(admin.password_hash, printed)


def test_no_fixed_credentials_left_in_the_scripts() -> None:
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    for name in ("seed_demo.py", "benchmark_endpoints.py", "generate_synthetic_load.py"):
        text = (scripts / name).read_text()
        for fixed in ("AdminPass123!", "BenchmarkAdminSecret123!"):
            assert fixed not in text, (name, fixed)
