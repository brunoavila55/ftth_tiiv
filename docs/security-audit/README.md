# Auditoria de segurança, estrutura e performance — FTTH Manager

> **Confidencial.** Descreve vulnerabilidades reais (já corrigidas — ver `resolucao.md`).
>
> Os artefatos brutos da auditoria (`findings.json`, `issues.md`, `inventario-rotas.md`, o PDF do relatório e `tools/`, os scripts que os geravam) foram removidos em 2026-09-19, com a auditoria já concluída e mesclada na `master`; seguem no histórico do git se precisar reconsultar o "retrato antes das correções". `resolucao.md` é o resumo técnico por achado que permanece como registro; `evidencias/` (medições e saídas de `pip-audit`/`pnpm audit`) permanece porque `resolucao.md` cita seus números diretamente.

| Arquivo | Conteúdo |
|---|---|
| `resolucao.md` | Resumo técnico por achado (o que foi encontrado, o que foi corrigido, evidência de antes/depois) |
| `evidencias/` | `medicoes.md` (saídas literais), `routes.json`, `pip-audit-backend.json`, `pnpm-audit-frontend.json` |
