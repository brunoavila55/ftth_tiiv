# ADR 0003: Autenticação, Sessões Opacas, CSRF e Controle de Acesso RBAC

## Status
Aceito

## Contexto
O FTTH Manager é um sistema corporativo para documentação física e óptica de infraestrutura de telecomunicações. As operações manipulam dados críticos de rota, clientes, topologia e cabos. Conforme estabelecido no documento de especificação `backend.md`:
1. Não há cadastro público de usuários; o provisionamento é feito exclusivamente por administradores e a inicialização de acesso deve ocorrer via CLI segura.
2. Não deve ser utilizado JWT no `localStorage` por riscos de extração via XSS.
3. Não deve ser introduzido Redis exclusivamente para controle de concorrência ou limitação de taxa de autenticação.
4. Deve haver mitigação contra timing attacks e enumeração de usuários.
5. Devem ser suportados perfis hierárquicos com granularidade de permissões (`admin`, `engineer`, `technician`, `viewer`).
6. A proteção contra CSRF deve ser exigida em todas as operações de mutação de estado, incluindo login e logout.
7. O último administrador ativo do sistema nunca pode ser desativado, rebaixado ou excluído.

## Decisões Arquiteturais

### 1. Hashing Criptográfico com Argon2id
- Utilização da biblioteca mantida `argon2-cffi` configurada com os parâmetros recomendados pela RFC 9106 (tempo = 2, memória = 64 MB, paralelismo = 1, hash_len = 32).
- Mitigação de timing attacks em tentativas de login: quando um e-mail não existe no banco de dados, executa-se uma verificação sintética contra um hash dummy persistido em memória (`dummy_verify_password`), garantindo que o tempo de resposta seja indistinguível de uma senha errada para usuário existente.

### 2. Sessões Opacas no Banco de Dados
- Em vez de JWTs stateless (que dificultam revogação instantânea e expõem claims ao cliente), adota-se token opaco de alta entropia gerado com `secrets.token_urlsafe(48)`.
- O banco de dados armazena apenas o hash criptográfico SHA-256 do token (`token_hash`), impedindo que o vazamento do banco comprometa sessões ativas.
- Política de expiração de sessão em duas camadas:
  - **Expiração absoluta**: 7 dias após a criação.
  - **Expiração por inatividade**: 24 horas sem requisições (atualizando `last_activity_at` a cada minuto).
- Rotação do token de sessão a cada novo login bem-sucedido.
- Transporte exclusivo através de cookie seguro HttpOnly (`ftth_session`), com flag `SameSite=Lax` e `Secure` ativo em produção/configuração.

### 3. Proteção CSRF com Vínculo e Validação de Origem
- Implementação do padrão Double-Submit com token de alta entropia (`ftth_csrf_token`), obtido via endpoint `GET /auth/csrf`.
- Mutações de estado (`POST`, `PUT`, `PATCH`, `DELETE`) exigem a presença simultânea do cookie `ftth_csrf_token` e do cabeçalho `X-CSRF-Token`, validados via comparação de tempo constante (`hmac.compare_digest`).
- Validação estrita de cabeçalho `Origin` contra as origens autorizadas pelo CORS (`CORS_ORIGINS`) e o próprio host da requisição.
- Aplicação de CSRF inclusive nos fluxos de login e logout para prevenir Login/Logout CSRF.

### 4. Rate Limiting Persistido no PostgreSQL
- Persistência das tentativas de login na tabela `login_attempts`.
- Janela deslizante de 15 minutos com tolerância de até 5 tentativas consecutivas com falha por endereço IP ou e-mail de destino.
- A 6ª tentativa consecutiva com falha dentro da janela bloqueia temporariamente a autenticação com código HTTP `429 Too Many Requests` (`rate_limit_exceeded`).
- Permite funcionamento seguro em múltiplos workers (Gunicorn/Uvicorn) sem adicionar Redis ao ambiente.

### 5. Controle de Acesso Baseado em Perfis (RBAC)
- Matriz centralizada de permissões granulares (`app/core/permissions.py`) mapeando os 4 perfis (`admin`, `engineer`, `technician`, `viewer`).
- Validação em nível de rota no FastAPI através de dependências tipadas (`require_permission("recurso:ação")`).
- Ocultamento de botões no frontend é tratado como conveniência visual; a autorização reside integralmente e de forma inviolável no backend.

### 6. CLI de Bootstrap do Administrador
- Criação do script seguro `app/cli/bootstrap_admin.py` para provisionamento inicial do primeiro administrador e recuperação de senha emergencial.
- Exige validação de senha forte (mínimo 8 caracteres) e solicita confirmação segura via terminal quando não informada por variável de ambiente.
- Não exibe a senha digitada ou gerada em stdout/stderr ou logs.

### 7. Proteção do Último Administrador Ativo
- Validação atômica no serviço de identidade: operações de atualização (`PATCH /users/{id}`) ou desativação (`DELETE /users/{id}`) verificam a contagem de outros administradores ativos.
- Caso o usuário seja o único administrador ativo restante, a operação é rejeitada com HTTP `409 Conflict` (`last_admin_protection`).

## Consequências

### Positivas
- Elevado nível de segurança operacional contra ataques comuns (força bruta, timing attacks, roubo de token em localStorage, CSRF, login spoofing).
- Revogação imediata de credenciais: a desativação de um usuário invalida automaticamente todas as suas sessões ativas no banco.
- Simplicidade operacional: dispensa Redis ou serviços externos de cache para controle de rate limit e sessões.
- Auditoria rastreável com `ip_address` e `user_agent` nas sessões e tentativas de login.

### Negativas / Trade-offs
- Toda requisição autenticada realiza consulta para validar a sessão ativa no PostgreSQL (mitigado pelo pool de conexões otimizado e índices B-Tree em `token_hash` e `user_id`).
- Necessidade de limpeza periódica de sessões e tentativas de login antigas no banco de dados (previsto na manutenção e jobs da aplicação).
