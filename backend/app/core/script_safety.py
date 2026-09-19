"""Guarda de ambiente dos scripts operacionais que criam dados/credenciais de demonstração (SEC-12).

`seed_demo.py`, `generate_synthetic_load.py` e `benchmark_endpoints.py` escrevem dados sintéticos e
usuários com credenciais conhecidas. Eles só podem rodar contra um banco **local** e **fora de
produção**; para um alvo remoto (ex.: banco de homologação num host de rede) é preciso a flag
explícita `--i-know-this-is-not-prod`. Produção é sempre recusada, com ou sem a flag.
"""

import ipaddress
import os
import sys
from urllib.parse import urlparse

ALLOW_FLAG = "--i-know-this-is-not-prod"
LOCAL_HOSTS = frozenset({"localhost", "ip6-localhost", "::1"})


class UnsafeTargetError(Exception):
    """O script se recusou a rodar contra este ambiente/banco."""


def is_local_host(host: str | None) -> bool:
    if not host:  # conexão por socket Unix (sem host)
        return True
    if host.lower() in LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def raw_environment() -> str | None:
    """`ENVIRONMENT` como o operador o definiu (sem validar o resto das `Settings`).

    Em produção com configuração incompleta o `Settings()` falha antes de o script poder recusar
    com uma mensagem clara; a guarda de ambiente, por isso, olha a variável direto.
    """
    return os.environ.get("ENVIRONMENT")


def assert_environment_allowed(environment: str | None, *, script: str = "este script") -> None:
    if (environment or "").strip().lower() == "production":
        raise UnsafeTargetError(
            f"{script} não pode rodar com ENVIRONMENT=production: cria dados e credenciais de "
            "demonstração. Nada foi alterado."
        )


def assert_safe_target(
    db_url: str,
    *,
    environment: str | None,
    allow_non_local: bool = False,
    script: str = "este script",
) -> None:
    """Levanta `UnsafeTargetError` se o ambiente for produção ou o banco não for local (sem a flag)."""
    assert_environment_allowed(environment, script=script)
    host = urlparse(db_url.replace("postgresql+psycopg://", "postgresql://")).hostname
    if not is_local_host(host) and not allow_non_local:
        raise UnsafeTargetError(
            f"{script} recusou o banco '{host}': não é local. Se este alvo NÃO for produção, "
            f"repita com {ALLOW_FLAG}. Nada foi alterado."
        )


def guard_or_exit(
    db_url: str,
    *,
    environment: str | None,
    allow_non_local: bool,
    script: str,
) -> None:
    """Versão para `main()` de scripts: imprime o motivo e sai com código 2 (sem tocar no banco)."""
    try:
        assert_safe_target(
            db_url, environment=environment, allow_non_local=allow_non_local, script=script
        )
    except UnsafeTargetError as err:
        print(f"ERRO: {err}", file=sys.stderr)
        raise SystemExit(2) from err


def guard_environment_or_exit(*, environment: str | None, script: str) -> None:
    """Recusa produção o mais cedo possível (antes de ler `Settings` ou abrir qualquer conexão)."""
    try:
        assert_environment_allowed(environment, script=script)
    except UnsafeTargetError as err:
        print(f"ERRO: {err}", file=sys.stderr)
        raise SystemExit(2) from err
