import base64
import contextlib
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

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


def _csrf_signature(nonce: str) -> str:
    secret = get_settings().CSRF_SECRET.encode("utf-8")
    digest = hmac.new(secret, nonce.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_csrf_token() -> str:
    """Gera token CSRF assinado (`nonce.assinatura`, HMAC-SHA256 com CSRF_SECRET).

    A assinatura impede que quem consegue plantar um cookie (ex.: subdomínio comprometido) forje
    o par cabeçalho/cookie do double-submit.
    """
    nonce = secrets.token_urlsafe(24)
    return f"{nonce}.{_csrf_signature(nonce)}"


def is_valid_csrf_token(token: str | None) -> bool:
    """Confere a assinatura do token em tempo constante."""
    if not token or token.count(".") != 1:
        return False
    nonce, signature = token.split(".")
    if not nonce or not signature:
        return False
    return hmac.compare_digest(signature, _csrf_signature(nonce))


def verify_csrf_tokens(token_a: str | None, token_b: str | None) -> bool:
    """Compara cabeçalho e cookie em tempo constante e exige assinatura válida."""
    if not token_a or not token_b:
        return False
    if not hmac.compare_digest(token_a, token_b):
        return False
    return is_valid_csrf_token(token_a)
