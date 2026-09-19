import contextvars
import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# ContextVar para propagação transparente do request_id nos logs
request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id_ctx", default=None
)

# ContextVar com o job em execução no worker (correlação de logs de jobs assíncronos)
job_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("job_id_ctx", default=None)

# Chaves sensíveis que devem ser mascaradas nos logs
SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|token|secret|key|authorization|cookie|credential|csrf)",
    re.IGNORECASE,
)
REDACTED_TEXT = "[REDACTED]"


def redact_sensitive_data(data: Any) -> Any:
    """Recursivamente mascara campos sensíveis em dicionários ou listas."""
    if isinstance(data, dict):
        clean_dict: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(k, str) and SENSITIVE_KEY_PATTERN.search(k):
                clean_dict[k] = REDACTED_TEXT
            else:
                clean_dict[k] = redact_sensitive_data(v)
        return clean_dict
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


class JSONFormatter(logging.Formatter):
    """Formatador de log estruturado em JSON com sanitização de segredos."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Injetar request_id se disponível no contexto
        req_id = request_id_ctx.get()
        if req_id:
            log_entry["request_id"] = req_id

        job_id = job_id_ctx.get()
        if job_id:
            log_entry["job_id"] = job_id

        # Capturar atributos extras passados no log
        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "asctime",
        }
        extra_data = {k: v for k, v in record.__dict__.items() if k not in standard_attrs}
        if extra_data:
            log_entry["extra"] = redact_sensitive_data(extra_data)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(log_level: str = "INFO") -> None:
    """Configura o logger raiz para usar formatação JSON estruturada."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Limpar handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Ajustar verbosidade de bibliotecas de terceiros
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado para o módulo."""
    return logging.getLogger(name)
