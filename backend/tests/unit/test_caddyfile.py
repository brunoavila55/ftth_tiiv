"""R17 (SEC-11): regressão estática do Caddyfile (TLS por variável, HSTS, /metrics, CSP)."""

from pathlib import Path

RAW = (Path(__file__).resolve().parents[3] / "Caddyfile").read_text()
# só o que é configuração (comentários explicam e podem citar os termos proibidos)
CADDYFILE = "\n".join(
    line.split(" #")[0] for line in RAW.splitlines() if not line.strip().startswith("#")
)


def test_site_address_is_parametrized_and_auto_https_is_not_disabled() -> None:
    assert "{$SITE_ADDRESS::80}" in CADDYFILE
    assert "auto_https off" not in CADDYFILE  # com domínio, o Caddy emite/renova certificados


def test_hsts_is_sent_only_over_secure_connections() -> None:
    assert "Strict-Transport-Security" in CADDYFILE
    assert "header @secure Strict-Transport-Security" in CADDYFILE
    assert "X-Forwarded-Proto" in CADDYFILE  # TLS terminado em balanceador externo


def test_no_unsafe_script_policy_in_the_proxy() -> None:
    lowered = CADDYFILE.lower()
    assert "unsafe-inline" not in lowered and "unsafe-eval" not in lowered
    # o CSP das páginas (com nonce) vem do Next.js; o proxy só restringe a API
    assert "default-src 'none'" in CADDYFILE


def test_metrics_endpoint_is_never_proxied() -> None:
    assert "@metrics path /api/v1/metrics" in CADDYFILE
    metrics_block = CADDYFILE.split("handle @metrics", 1)[1].split("}", 1)[0]
    assert "respond" in metrics_block and "404" in metrics_block
    assert "reverse_proxy" not in metrics_block


def test_compose_passes_site_address_to_caddy() -> None:
    compose = (Path(__file__).resolve().parents[3] / "compose.yaml").read_text()
    assert "SITE_ADDRESS" in compose
