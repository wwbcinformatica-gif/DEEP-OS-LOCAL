"""
Middleware de protecao de rotas sensiveis.

PROBLEMA ENCONTRADO (auditoria automatica)
------------------------------------------
O teste `tests-manual/test_all_routes.py` revelou que ~48 rotas respondiam
**HTTP 200 sem nenhuma autenticacao**. As piores:

    GET /secrets   -> nomes E valores (mascarados) das API keys do .env
    GET /logs      -> conteudo dos logs + caminhos internos do servidor
    GET /memory    -> conteudo da memoria do projeto
    GET /tool/list -> schema de todas as ferramentas (reconhecimento)

Qualquer pessoa que descobrisse a URL lia isso do servidor de producao sem
login.

ESTRATEGIA
----------
Bloqueio por LISTA (nao "negar tudo"), por dois motivos:
  1. Nao arrisca quebrar o app desktop, que usa varias rotas locais sem login
     (o backend roda em 127.0.0.1 nesse caso);
  2. Fecha imediatamente o que realmente vaza dados.

O que NAO esta na lista continua acessivel — esta documentado como pendencia
em `STATUS.md` (endurecimento gradual).

AUTENTICACAO
------------
Aceita duas formas, para nao quebrar o frontend:
  - `Authorization: Bearer <JWT>` (usado pelo SaaS e pelo painel admin)
  - `X-Admin-Token: <token de admin>` (alternativa simples para o desktop)

APP DESKTOP (sem login)
-----------------------
Detectado pelo **header `Host`**, NAO pelo IP.

Por que isso importa (erro corrigido): eu havia escrito "se o IP do cliente for
127.0.0.1, libera (app desktop)". Mas em producao o nginx faz proxy para
127.0.0.1:8001 — ou seja, TODA requisicao externa chega vinda do localhost.
A regra liberava o mundo inteiro e o vazamento continuou aberto.

Agora a deteccao e:
  - Host local (127.0.0.1 / localhost / testserver) -> app desktop, libera
  - Host externo (deep-os.tech, IP publico)         -> exige autenticacao

O nginx repassa `Host: deep-os.tech` (proxy_set_header Host $host), entao
requisicoes vindas da internet caem no segundo caso.

Tambem aceita a variavel de ambiente DESKTOP_MODE=1 para liberar tudo
explicitamente, se algum dia for rodar so em maquina local.
"""
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("security")

# Prefixos que devolvem dados sensiveis e exigem autenticacao.
#
# IMPORTANTE (corrigido depois de medir a PRODUCAO):
# apenas caminhos que o nginx REALMENTE encaminha ao backend podem ser
# explorados pela internet. O nginx encaminha os prefixos:
#   /api/ /auth/ /admin/ /plans/ /shop/ /chat/ /voice/ /ws/
# Todo o resto cai no `location /` e recebe o frontend (HTML), nunca o backend.
#
# Por isso os antigos "/secrets", "/logs", "/memory" (sem /api) NAO eram
# alcancaveis de fora — eram protecao em profundidade, nao correcao de falha.
# O que ESTAVA exposto de verdade:
#   GET /api/config              -> config completa (system prompt, toolset)
#   GET /api/config/agent, /mcp-servers, /api-key
#   GET /api/instances           -> instancias de OUTROS tenants, com tenant_id
PREFIXOS_PROTEGIDOS = (
    # --- alcancaveis pela internet (o que importa de fato) ---
    "/api/config",
    "/api/instances",
    "/api/tasks",
    "/api/secrets",
    "/api/logs",
    "/api/memory",
    "/api/plugins",
    "/api/monitor",
    "/api/tools",
    # --- defesa em profundidade (so acessiveis localmente) ---
    "/secrets",
    "/logs",
    "/memory",
    "/tool/list",
    "/tool/read",
    "/tool/bash",
    "/knowledge",
    "/history",
    "/openclaude",
    "/opencode",
    "/api/stt",
)

# Estes continuam PUBLICOS de proposito (usados antes do login):
#   /plans/public, /shop/products, /auth/*, /health, /,
#   /api/config/identity (lido no boot do frontend; devolve so o nome/voz)
ISENCOES = (
    "/api/config/identity",
)

# Hosts considerados "local" (app desktop acessando o backend direto).
# NAO usar o IP do cliente: atras de proxy reverso ele e sempre 127.0.0.1.
_HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1", "testserver"}


def _modo_desktop() -> bool:
    """DESKTOP_MODE=1 libera tudo (uso local explicito)."""
    return os.environ.get("DESKTOP_MODE", "").strip().lower() in ("1", "true", "sim", "yes")


def _host_local(request) -> bool:
    """
    True apenas se o HOST da requisicao for local.

    Ex.: `Host: 127.0.0.1:8001` (app desktop) -> local
         `Host: deep-os.tech`      (via nginx) -> externo, exige auth
    """
    try:
        host = (request.headers.get("host") or "").strip().lower()
        if not host:
            return False
        # remove porta
        host_sem_porta = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
        return host_sem_porta in _HOSTS_LOCAIS
    except Exception:
        return False


def _token_valido(request) -> bool:
    """
    Verifica se a requisicao traz credencial valida.

    Nao levanta excecao: devolve bool, para o middleware decidir.
    """
    from core.auth import AuthManager

    # 1. Authorization: Bearer <JWT>
    cabecalho = request.headers.get("authorization", "")
    if cabecalho.lower().startswith("bearer "):
        token = cabecalho[7:].strip()
        try:
            AuthManager.decode_token(token)
            return True
        except Exception:
            pass

    # 2. X-Admin-Token (token de admin do painel)
    admin_token = request.headers.get("x-admin-token", "").strip()
    if admin_token:
        try:
            payload = AuthManager.decode_token(admin_token)
            if payload.get("is_admin") or payload.get("is_master"):
                return True
        except Exception:
            pass

    # 3. Sessao de admin via cookie (se o frontend usar)
    if request.cookies.get("admin_token"):
        try:
            payload = AuthManager.decode_token(request.cookies["admin_token"])
            if payload.get("is_admin") or payload.get("is_master"):
                return True
        except Exception:
            pass

    return False


def _precisa_protecao(caminho: str) -> bool:
    # Isencoes explicam primeiro (ex: /api/config/identity e lido no boot)
    for isento in ISENCOES:
        if caminho == isento or caminho.startswith(isento + "/"):
            return False
    return any(
        caminho == p or caminho.startswith(p + "/") or caminho.startswith(p + "?")
        for p in PREFIXOS_PROTEGIDOS
    )


class ProtecaoRotasSensiveis(BaseHTTPMiddleware):
    """Bloqueia acesso anonimo a rotas que devolvem dados sensiveis."""

    async def dispatch(self, request, call_next):
        caminho = request.url.path

        if not _precisa_protecao(caminho):
            return await call_next(request)

        # Modo desktop explicito (env) ou Host local: app desktop sem login
        if _modo_desktop() or _host_local(request):
            return await call_next(request)

        if _token_valido(request):
            return await call_next(request)

        logger.warning(
            "Acesso negado a rota sensivel: %s %s (host=%s)",
            request.method, caminho, request.headers.get("host", "?"),
        )
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Autenticacao necessaria para acessar este recurso",
                "path": caminho,
            },
        )
