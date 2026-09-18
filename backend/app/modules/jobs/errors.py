"""Erros de jobs assíncronos.

Só `JobValidationError` tem mensagem própria segura para o cliente; qualquer outra exceção do
worker (IntegrityError, OSError, bugs...) é registrada em log com o job_id e o cliente recebe uma
mensagem genérica (SEC-14 — nada de SQL, nomes de tabela ou caminhos de servidor na API).
"""

GENERIC_JOB_ERROR = (
    "Falha interna ao processar o job. Informe o identificador do job ao administrador."
)


class JobValidationError(Exception):
    """Erro de validação de negócio do job, com mensagem segura para exibir ao usuário."""
