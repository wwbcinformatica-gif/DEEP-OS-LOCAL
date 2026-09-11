"""
Identidade por tenant — nome do assistente e do usuario.

Motivacao
---------
Antes deste modulo, `assistant_name` e `user_name` viviam apenas em
`config.yaml` (arquivo GLOBAL). Ou seja: todos os assinantes compartilhavam
o mesmo nome, e o ultimo que salvasse sobrescrevia o de todos.

Agora a identidade e resolvida nesta ordem:

1. Banco de dados, por `tenant_id` (isolamento real) — via colunas
   `tenants.assistant_name` / `tenants.user_name`
2. `config.yaml` global (fallback para chamadas sem autenticacao)
3. `api_keys.json` / default

A resolucao e server-side: quem identifica o tenant e o JWT, nunca o
cliente. Assim um usuario nao consegue ler nem sobrescrever a identidade
de outro.
"""
from contextvars import ContextVar
from datetime import timedelta
from typing import Optional

DEFAULT_ASSISTANT_NAME = "DEEP-OS"
DEFAULT_VOICE = "Charon"

# Contas master do projeto (hardcoded em routes/auth.py). Cada uma recebe uma
# chave de identidade PROPRIA, derivada do e-mail.
#
# Por que: as duas contas emitiam o MESMO `sub` ("master-admin") e nenhuma
# tinha linha em `tenants`. Resultado: as duas caiam no config.yaml global,
# entao a voz (e o nome) que uma escolhia aparecia na outra — e tambem nos
# assinantes que nunca personalizaram.
MASTER_EMAILS = ("wwbcinformatica@gmail.com", "wwbc22@gmail.com")


def master_identity_key(email: Optional[str]) -> str:
    """
    Chave de identidade de uma conta master, unica por e-mail.

    Ex.: 'master-admin:wwbc22@gmail.com'
    """
    return f"master-admin:{(email or '').strip().lower()}"


def master_email_from_key(key: Optional[str]) -> Optional[str]:
    """Extrai o e-mail de uma chave master (ou None se nao for uma)."""
    if key and key.startswith("master-admin:"):
        return key.split(":", 1)[1] or None
    return None


def is_master_key(key: Optional[str]) -> bool:
    return bool(key and key.startswith("master-admin"))


def _ensure_master_row(tenant_id: str) -> bool:
    """
    Garante que a conta master tenha uma linha em `tenants`.

    Sem isso ela sempre cai no config.yaml global. Cria com os campos de
    identidade VAZIOS, para herdar o padrao ate o usuario personalizar.
    """
    email = master_email_from_key(tenant_id) or tenant_id
    try:
        from database.connection import get_conn

        conn = get_conn()
        try:
            existe = conn.execute(
                "SELECT 1 FROM tenants WHERE id = ?", (tenant_id,)
            ).fetchone()
            if existe:
                return True

            conn.execute(
                """
                INSERT INTO tenants (id, name, email, password_hash, plan, status)
                VALUES (?, ?, ?, ?, 'master', 'active')
                """,
                (
                    tenant_id,
                    "Master Admin",
                    email,
                    # Sem senha utilizavel: o login master e hardcoded e nao
                    # consulta esta tabela. Placeholder claro de proposito.
                    "!conta-master-hardcoded-sem-senha!",
                ),
            )
            conn.commit()
            print(f"[tenant_identity] Linha de identidade criada para a conta master {email}")
            return True
        finally:
            conn.close()
    except Exception as e:
        print(f"[tenant_identity] Nao consegui criar linha da conta master {email}: {e}")
        return False

# Tenant da requisicao/conexao atual.
#
# Preenchido em DOIS pontos:
#   - routes/config.py  (via JWT, por requisicao HTTP)
#   - routes/voice_ws.py (via ?token=, por conexao de WebSocket)
#
# Fica aqui (e nao no middleware) porque o `middleware/tenant.py` nao e
# montado no main.py — e codigo morto. ContextVar e copiado para threads
# do run_in_executor, entao as actions do Charon tambem enxergam.
current_tenant_id: ContextVar[Optional[str]] = ContextVar("current_tenant_id", default=None)


def get_current_tenant() -> Optional[str]:
    """Tenant da execucao atual (None = app desktop, sem login)."""
    return current_tenant_id.get()


def set_current_tenant(tenant_id: Optional[str]) -> None:
    """Define o tenant da execucao atual."""
    current_tenant_id.set(tenant_id)


def tenant_slug(tenant_id: Optional[str]) -> Optional[str]:
    """
    Nome de pasta SEGURO para um tenant_id. FONTE UNICA — use sempre esta.

    Por que existe (bug real corrigido):
    Havia DOIS sanitizadores diferentes no projeto, e o script de migracao usava
    o id CRU. Resultado: os arquivos ficaram em `downloads/master-admin:wwbc22@gmail.com/`
    (com `:` e `@`) enquanto o backend procurava em
    `downloads/master-adminwwbc22gmail.com/` — pasta diferente. Todo download
    dava 404.

    Regra: apenas [A-Za-z0-9._-]. Tudo o mais vira `_`. Nunca retorna vazio
    (usa 'desconhecido' como ultimo recurso) para nao criar pasta na raiz.
    """
    if not tenant_id:
        return None
    seguro = "".join(c if (c.isalnum() or c in "._-") else "_" for c in str(tenant_id))
    return seguro or "desconhecido"


# ─── Fuso horario do usuario ────────────────────────────────────────────────
#
# O SERVIDOR RODA EM UTC. O usuario esta em Brasilia (UTC-3).
#
# Sem isto, a action `reminder` calculava "agora" com datetime.now() do
# servidor e um lembrete pedido para "14:30" parecia ja ter passado (UTC esta
# 3h a frente daqui). Este ContextVar carrega o fuso do usuario (IANA, ex
# "America/Sao_Paulo") e e preenchido:
#   - em routes/voice_ws.py, do campo `timezone` que o frontend envia
#   - em core/reminders.py, do fuso gravado em cada lembrete
DEFAULT_TZ = "America/Sao_Paulo"

current_timezone: ContextVar[Optional[str]] = ContextVar("current_timezone", default=None)


def get_current_timezone() -> str:
    """Fuso do usuario (IANA). Cai no padrao do projeto se nao definido."""
    return current_timezone.get() or DEFAULT_TZ


def set_current_timezone(tz: Optional[str]) -> None:
    """Define o fuso do usuario na execucao atual."""
    current_timezone.set(tz or None)


def get_tzinfo(tz: Optional[str] = None):
    """
    Objeto de fuso do usuario.

    Usa `safe_zoneinfo`, que tem fallback de offset fixo para ambientes sem
    banco de fusos (Windows sem tzdata). Isso e essencial: sem o fallback o
    horario cairia em UTC e lembretes ficariam 3h errados no Brasil.
    """
    from datetime import timezone as _tz

    return (
        safe_zoneinfo(tz)
        or safe_zoneinfo(get_current_timezone())
        or safe_zoneinfo(DEFAULT_TZ)
        or _tz.utc
    )


def now_utc():
    """Agora em UTC (naive, para bater com o formato gravado no banco)."""
    from datetime import datetime

    return datetime.utcnow()


def now_local(tz: Optional[str] = None):
    """Agora na hora local do usuario (aware)."""
    from datetime import datetime

    return datetime.now(get_tzinfo(tz))


# Offsets fixos para quando o banco de fusos nao esta disponivel.
#
# Windows NAO tem /usr/share/zoneinfo: `ZoneInfo('America/Sao_Paulo')` levanta
# ZoneInfoNotFoundError ("No time zone found with key ...") sem o pacote tzdata.
# Sem este fallback, safe_zoneinfo devolvia None, o fuso caia em UTC e um
# lembrete pedido para as 23:35 (Brasilia) era interpretado como 23:35 UTC —
# 3 horas errado.
#
# O Brasil aboliu o horario de verao em 2019, entao UTC-3 e sempre correto
# para America/Sao_Paulo (nao ha mais mudanca sazonal a considerar).
_OFFSETS_FIXOS: dict[str, int] = {
    "America/Sao_Paulo": -3,
    "America/Argentina/Buenos_Aires": -3,
    "America/Belem": -3,
    "America/Fortaleza": -3,
    "America/Recife": -3,
    "America/Bahia": -3,
    "America/Cuiaba": -4,
    "America/Manaus": -4,
    "America/Porto_Velho": -4,
    "America/Rio_Branco": -5,
    "America/Noronha": -2,
    "UTC": 0,
    "Etc/UTC": 0,
}


def safe_zoneinfo(tz: Optional[str]):
    """
    ZoneInfo tolerante; cai em offset fixo quando o banco de fusos nao existe
    (Windows sem tzdata). Devolve None apenas se nem o offset for conhecido.
    """
    from datetime import timezone as _tz

    if not tz:
        return None
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(tz)
    except Exception:
        pass

    # Fallback: offset fixo conhecido (exato para o Brasil pos-2019)
    horas = _OFFSETS_FIXOS.get(tz)
    if horas is not None:
        return _tz(timedelta(hours=horas))

    return None


def _default_identity() -> dict:
    """Identidade global (fallback) — le config.yaml via config_manager."""
    try:
        from memory.config_manager import get_assistant_name, get_user_name

        return {
            "assistant_name": get_assistant_name() or DEFAULT_ASSISTANT_NAME,
            "user_name": get_user_name() or "",
            "voice": _default_voice(),
        }
    except Exception:
        return {
            "assistant_name": DEFAULT_ASSISTANT_NAME,
            "user_name": "",
            "voice": _default_voice(),
        }


def _default_voice() -> str:
    """Voz padrao, lida do config.yaml global."""
    try:
        import yaml
        from pathlib import Path

        cfg = Path(__file__).resolve().parent.parent.parent / "config.yaml"
        if cfg.exists():
            with open(cfg, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            v = data.get("identity", {}).get("voice", "")
            if v:
                return v
    except Exception:
        pass
    return DEFAULT_VOICE


def get_identity(tenant_id: Optional[str]) -> dict:
    """
    Retorna a identidade do tenant.

    Se `tenant_id` for None ou o tenant nao existir, devolve a identidade
    global (compatibilidade com o app desktop, que nao tem login).

    Inclui `voice`: a voz escolhida e preferencia PESSOAL. Antes era global,
    entao um assinante trocando a voz mudava a de todos os outros.
    """
    fallback = _default_identity()
    if not tenant_id:
        return fallback

    # Conta master: garante a linha propria na primeira consulta. Sem isso ela
    # cairia no global e a voz de um admin apareceria na do outro.
    if is_master_key(tenant_id):
        _ensure_master_row(tenant_id)

    try:
        from database.connection import get_conn

        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT assistant_name, user_name, voice FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        return fallback

    if not row:
        return fallback

    try:
        db_assistant = row["assistant_name"]
        db_user = row["user_name"]
        db_voice = row["voice"]
    except (KeyError, IndexError, TypeError):
        return fallback

    return {
        # None ou vazio = tenant nunca personalizou -> usa o padrao global
        "assistant_name": (db_assistant or "").strip() or fallback["assistant_name"],
        "user_name": (db_user or "").strip(),
        "voice": (db_voice or "").strip() or fallback.get("voice", DEFAULT_VOICE),
    }


def set_identity(
    tenant_id: str,
    assistant_name: str,
    user_name: str,
    voice: Optional[str] = None,
) -> bool:
    """
    Grava a identidade do tenant. Retorna True se gravou no banco.

    Nao toca em `config.yaml`: o padrao global fica intocado, garantindo
    que quem nunca personalizou continue vendo o nome/voz original.

    `voice=None` preserva a voz ja gravada (permite salvar so o nome sem
    apagar a escolha de voz).
    """
    if not tenant_id:
        return False

    # Conta master pode ainda nao ter linha (nunca leu a identidade antes).
    # Sem isto o UPDATE afetaria 0 linhas e a gravacao seria PERDIDA em
    # silencio — bug pego por tests-manual/test_master_identity.py.
    if is_master_key(tenant_id):
        _ensure_master_row(tenant_id)

    assistant = (assistant_name or "").strip() or DEFAULT_ASSISTANT_NAME
    user = (user_name or "").strip()
    voz = (voice or "").strip()

    try:
        from database.connection import get_conn

        conn = get_conn()
        try:
            if voz:
                cur = conn.execute(
                    """
                    UPDATE tenants
                       SET assistant_name = ?, user_name = ?, voice = ?,
                           updated_at = datetime('now')
                     WHERE id = ?
                    """,
                    (assistant, user, voz, tenant_id),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE tenants
                       SET assistant_name = ?, user_name = ?,
                           updated_at = datetime('now')
                     WHERE id = ?
                    """,
                    (assistant, user, tenant_id),
                )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except Exception as e:
        print(f"[tenant_identity] Falha ao salvar identidade do tenant {tenant_id}: {e}")
        return False


def get_assistant_name(tenant_id: Optional[str]) -> str:
    """Atalho: apenas o nome do assistente do tenant."""
    return get_identity(tenant_id)["assistant_name"]


def get_user_name(tenant_id: Optional[str]) -> str:
    """Atalho: apenas o nome do usuario do tenant."""
    return get_identity(tenant_id)["user_name"]


def get_voice(tenant_id: Optional[str]) -> str:
    """Atalho: apenas a voz do tenant."""
    return get_identity(tenant_id)["voice"]
