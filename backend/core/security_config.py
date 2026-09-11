"""
Configuracao de seguranca centralizada.

Motivo: as contas master estavam com e-mail e SENHA hardcoded em
`routes/auth.py`, repetidos em dois lugares. A senha (`admin123@`) tambem
aparecia em texto puro na documentacao do projeto.

Agora tudo vem de variavel de ambiente, com fallback para o valor antigo
(para o sistema continuar funcionando sem quebrar o login dos clientes) e um
AVISO no log avisando que o padrao deve ser trocado.

Como trocar em producao (no VPS, em `/etc/systemd/system/deepos-backend.service`
ou num arquivo `Environment=`):

    MASTER_PASSWORD=uma-senha-forte-aqui
    JWT_SECRET=<gerado automaticamente se ausente>
    ADMIN_PASSWORD=<senha do painel admin>
"""
import os

_DEFAULT_MASTER_PASSWORD = "admin123@"
_DEFAULT_MASTER_EMAILS = ("wwbcinformatica@gmail.com", "wwbc22@gmail.com")


def master_emails() -> list[str]:
    """E-mails com privilegio master (separados por virgula no env)."""
    env = os.environ.get("MASTER_EMAILS", "").strip()
    if env:
        return [e.strip().lower() for e in env.split(",") if e.strip()]
    return list(_DEFAULT_MASTER_EMAILS)


def master_password() -> str:
    """Senha das contas master."""
    return os.environ.get("MASTER_PASSWORD", "").strip() or _DEFAULT_MASTER_PASSWORD


def using_default_master_password() -> bool:
    """True se ainda estiver usando a senha padrao (insegura)."""
    return master_password() == _DEFAULT_MASTER_PASSWORD


def check_master_credentials(email: str, password: str) -> bool:
    """
    Valida credenciais de uma conta master.

    Comparacao em tempo constante para nao vazar informacao por timing.
    """
    import hmac

    emails = master_emails()
    if (email or "").strip().lower() not in emails:
        return False
    return hmac.compare_digest(password or "", master_password())


def avisar_se_inseguro() -> None:
    """Registra um aviso unico quando a senha padrao esta em uso."""
    if using_default_master_password():
        print(
            "[seguranca] AVISO: MASTER_PASSWORD esta com o valor PADRAO. "
            "Defina a variavel de ambiente MASTER_PASSWORD antes de expor o sistema."
        )
