import contextlib
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Configuração estável de Argon2id (RFC 9106)
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
)

# Hash sintético fixo para mitigação de enumeração de usuários (timing attacks)
_DUMMY_HASH = _hasher.hash("dummy_password_for_timing_mitigation_12345")


def hash_password(password: str) -> str:
    """Gera hash criptográfico seguro usando Argon2id."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verifica uma senha contra o hash Argon2id."""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def dummy_verify_password(password: str) -> None:
    """Executa verificação contra hash dummy para garantir tempo constante em falhas."""
    with contextlib.suppress(Exception):
        _hasher.verify(_DUMMY_HASH, password)


def generate_session_token() -> tuple[str, str]:
    """Gera um token de sessão opaco e seu hash SHA-256 para persistência segura no banco.

    Retorna:
        (raw_token_para_cookie, token_hash_para_banco)
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_session_token(raw_token)
    return raw_token, token_hash


def hash_session_token(raw_token: str) -> str:
    """Gera o hash SHA-256 do token de sessão."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    """Gera um token CSRF seguro e aleatório."""
    return secrets.token_urlsafe(32)


def verify_csrf_tokens(token_a: str | None, token_b: str | None) -> bool:
    """Compara dois tokens CSRF usando tempo constante para evitar timing attacks."""
    if not token_a or not token_b:
        return False
    return hmac.compare_digest(token_a, token_b)
