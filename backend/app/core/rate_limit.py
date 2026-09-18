"""Rate limit reutilizável (429 + Retry-After) para rotas caras (EST-11).

Uso: `dependencies=[Depends(rate_limit("search", "RATE_LIMIT_SEARCH_PER_MINUTE"))]`.

O limitador padrão é **em memória, por processo** (janela deslizante por usuário autenticado). Com
mais de um worker/réplica o teto efetivo é multiplicado pelo número de processos; a interface
`RateLimiter` permite trocar por um backend compartilhado (Postgres/Redis) sem mexer nas rotas.
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Protocol

from fastapi import Depends, Request

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.errors import TooManyRequestsError
from app.modules.identity.models import User

# Teto defensivo de chaves (usuário × bucket) mantidas em memória
_MAX_TRACKED_KEYS = 50_000


class RateLimiter(Protocol):
    def hit(self, bucket: str, subject: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Registra uma tentativa. Retorna (permitida, segundos_até_liberar)."""
        ...

    def reset(self) -> None: ...


class InMemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, bucket: str, subject: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = self._clock()
        key = (bucket, subject)
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                if len(self._hits) >= _MAX_TRACKED_KEYS:
                    self._evict(now, window_seconds)
                hits = self._hits[key] = deque()
            while hits and now - hits[0] >= window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(window_seconds - (now - hits[0])) + 1)
                return False, min(retry_after, window_seconds)
            hits.append(now)
            return True, 0

    def _evict(self, now: float, window_seconds: int) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] >= window_seconds]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_limiter: RateLimiter = InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _limiter


def set_rate_limiter(limiter: RateLimiter) -> None:
    global _limiter
    _limiter = limiter


def reset_rate_limits() -> None:
    _limiter.reset()


def rate_limit(name: str, limit_setting: str, window_seconds: int = 60) -> Callable[..., None]:
    """Fábrica de dependência: `limit_setting` é o nome do campo de Settings com o teto/janela."""

    def _dependency(request: Request, current_user: User = Depends(get_current_user)) -> None:
        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED:
            return
        limit = int(getattr(settings, limit_setting))
        allowed, retry_after = get_rate_limiter().hit(
            name, str(current_user.id), limit, window_seconds
        )
        if not allowed:
            raise TooManyRequestsError(retry_after)

    _dependency.rate_limit_name = name  # type: ignore[attr-defined]
    return _dependency
