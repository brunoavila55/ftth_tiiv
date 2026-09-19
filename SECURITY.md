# Política de Segurança — FTTH Manager

A segurança da infraestrutura de telecomunicações e dos dados operacionais dos provedores é prioridade máxima no projeto **FTTH Manager**.

---

## 1. Versões Suportadas

Recebem correções de segurança ativas as versões mais recentes das branches principais:

| Versão | Suporte Ativo a Patches de Segurança |
|:---|:---:|
| `master` / `main` | ✅ Sim |
| Tags v1.x | ✅ Sim |

---

## 2. Como Reportar uma Vulnerabilidade de Segurança

Se você identificou uma vulnerabilidade de segurança no FTTH Manager, solicitamos que adote o processo de **divulgação responsável e coordenada**:

1. **NÃO crie uma Issue pública no GitHub** para reportar falhas de segurança não corrigidas.
2. Envie um e-mail para a equipe de mantenedores em: `seguranca@provedor.com.br` (ou através do recurso de [GitHub Security Advisories](https://github.com/brunoavila55/ftth_tiiv/security/advisories)).
3. Inclua no relatório:
   - Descrição detalhada da vulnerabilidade.
   - Passos reprodutíveis ou código de prova de conceito (PoC).
   - Componente ou endpoint afetado.
   - Avaliação de impacto potencial (ex: escalonamento de privilégio, vazamento de dados, negação de serviço).
4. Nossa equipe responderá em até **48 horas úteis**, confirmando o recebimento e o plano de mitigação.

---

## 3. Modelo de Ameaças e Controles de Defesa em Profundidade

O FTTH Manager implementa os seguintes controles de segurança nativos:

### 3.1. Autenticação e Gestão de Credenciais
- **Hashing de Senhas**: Algoritmo Argon2id conforme RFC 9106 com parâmetros de memória e tempo recomendados pela OWASP.
- **Mitigação de Ataques de Tempo (Timing Attacks)**: Uso de dummy hash constante quando o e-mail não existe para impedir enumeração de operadores.
- **Sessões Ocas**: Tokens de sessão aleatórios de 256 bits (`secrets.token_urlsafe`), armazenados no banco exclusivamente em forma de hash SHA-256.
- **Rate Limiting Distribuído**: Limite de 5 tentativas de login por IP/usuário a cada 15 minutos persistido no banco de dados relacional.

### 3.2. Proteção de Transporte e Navegação
- **Proteção CSRF**: Validação rigorosa em tempo constante via token duplo (`X-CSRF-Token` + cookie) e validação do cabeçalho `Origin`.
- **Cookies Seguros**: Cookies com flags `HttpOnly`, `SameSite=Lax` e `Secure` (em produção com TLS).
- **Content-Security-Policy (CSP)**: política por resposta com **nonce**, gerada pelo Next.js (`frontend/src/middleware.ts`): `script-src 'self' 'nonce-…' 'strict-dynamic'` — sem `unsafe-inline` nem `unsafe-eval` (o `unsafe-eval` existe só em desenvolvimento) —, workers `blob:` para o MapLibre e conexões/imagens restritas ao próprio site e aos servidores de tiles autorizados. As respostas da API recebem `default-src 'none'; frame-ancestors 'none'` no Caddy.
- **TLS e HSTS**: com `SITE_ADDRESS=<domínio>` o Caddy obtém/renova certificados (Let's Encrypt), redireciona HTTP→HTTPS e envia `Strict-Transport-Security` (1 ano, `includeSubDomains`). Se o TLS for terminado em um balanceador externo, ele deve enviar `X-Forwarded-Proto: https` (o HSTS é emitido nesse caso também) e o backend deve listar o proxy em `TRUSTED_PROXIES`. Sem TLS (padrão `:80`) o cookie de sessão `Secure` só funciona em `localhost`.
- **Endpoint de métricas**: `/api/v1/metrics` não é publicado pelo proxy (404 externo); o Prometheus deve acessá-lo pela rede interna com `X-Metrics-Token`.

### 3.3. Isolamento e Ambiente de Execução
- **Usuários Não-Root em Contêineres**: Backend executado sob `ftthuser` (UID 1000) e frontend sob `nextjs` (UID 1001).
- **Banco de Dados em Rede Privada**: O PostgreSQL/PostGIS não expõe portas públicas no host em produção, operando exclusivamente em rede interna do Docker.
- **Upload Seguro de Arquivos**: Inspeção de magic bytes reais de conteúdo (rejeição de binários disfarçados de imagem), verificação de tamanho máximo e sanitização estrita de nomes de arquivos para impedir path traversal.
