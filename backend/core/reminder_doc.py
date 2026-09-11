"""
Gera lembretes como documento para download.

Motivacao
---------
O usuario acessa o Charon por uma interface sem pagina propria, entao o jeito
confiavel de entregar informacao e o mesmo que ja funciona para resumos:
gerar um documento e devolver um link de download (/api/download?path=...).

Aqui ficam:
- `build_summary_markdown()` — o texto do resumo (usado em voz e no arquivo)
- `save_summary_document()`  — grava o arquivo e devolve (caminho, url, nome)
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

_DIAS = [
    "segunda-feira", "terca-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sabado", "domingo",
]


def _downloads_dir() -> Path:
    """
    Diretorio de downloads DO TENANT ATUAL.

    Fica em `<raiz>/downloads/<tenant_id>/` para que um assinante nao consiga
    baixar arquivos de outro so por adivinhar o nome (antes todos caiam no
    mesmo `downloads/`). Sem tenant (app desktop), usa a raiz de `downloads/`.
    """
    raiz = Path(__file__).resolve().parent.parent.parent
    base = raiz / "downloads"

    try:
        # FONTE UNICA de sanitizacao (core.tenant_identity.tenant_slug).
        # Antes cada modulo tinha a sua, e o script de migracao usava o id cru:
        # o arquivo ia para uma pasta e o download procurava em outra.
        from core.tenant_identity import get_current_tenant, tenant_slug

        seguro = tenant_slug(get_current_tenant())
        if seguro:
            base = base / seguro
    except Exception:
        pass

    base.mkdir(parents=True, exist_ok=True)
    return base


def tenant_downloads_dir() -> Path:
    """
    Diretorio de downloads do tenant atual (para uso pelas actions/tools).

    Substitui os caminhos HARDCODED que existiam em `routes/voice_ws.py`
    (`Path("/root/DEEP-OS/downloads")`), que quebravam se o projeto mudasse
    de pasta e nao isolavam por assinante.
    """
    return _downloads_dir()


def _fmt_humano(fire_at: str, tz: Optional[str] = None) -> str:
    """
    Converte o horario gravado (UTC) para a hora local do usuario e formata.

    '2026-09-11 17:30:00' (UTC) -> '11/09/2026 as 14:30 (sexta-feira)' em Brasilia

    Usa o fuso do proprio lembrete (coluna `tz`); se nao houver, usa o do
    contexto e, por ultimo, o padrao do projeto.
    """
    try:
        from datetime import timezone as _tz

        from core.tenant_identity import DEFAULT_TZ, get_current_timezone, safe_zoneinfo

        raw = str(fire_at).strip()
        dt = None
        # Tenta os formatos do mais longo para o mais curto, sobre o texto todo
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
            try:
                dt = datetime.strptime(raw[:19] if len(raw) >= 19 else raw, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return raw

        # O banco guarda UTC (naive). Reinterpreta como UTC e converte.
        nome_tz = tz or get_current_timezone() or DEFAULT_TZ
        zone = safe_zoneinfo(nome_tz)
        if zone is not None:
            dt = dt.replace(tzinfo=_tz.utc).astimezone(zone)

        return f"{dt.strftime('%d/%m/%Y as %H:%M')} ({_DIAS[dt.weekday()]})"
    except Exception:
        return str(fire_at)


def build_summary_markdown(reminders: list[dict], titulo: str = "Meus Lembretes") -> str:
    """Resumo em markdown, legivel tanto em voz quanto no arquivo."""
    agora = datetime.now()
    linhas = [f"# {titulo}", ""]

    if not reminders:
        linhas.append("Nenhum lembrete agendado no momento.")
        linhas.append("")
        linhas.append(f"_Gerado em {agora.strftime('%d/%m/%Y as %H:%M')}_")
        return "\n".join(linhas)

    pendentes = [r for r in reminders if (r.get("status") or "pending") == "pending"]
    linhas.append(f"Total: **{len(reminders)}** lembrete(s) — {len(pendentes)} pendente(s).")
    linhas.append("")

    for r in reminders:
        status = r.get("status") or "pending"
        marca = {"pending": "Agendado", "fired": "Ja disparado", "cancelled": "Cancelado"}.get(status, status)
        linhas.append(f"## {_fmt_humano(r.get('fire_at', ''), r.get('tz'))}")
        linhas.append("")
        linhas.append(f"- **{r.get('message', '(sem texto)')}**")
        linhas.append(f"- Situacao: {marca}")
        if r.get("created_at"):
            linhas.append(f"- Criado em: {r['created_at']}")
        linhas.append("")

    linhas.append("---")
    linhas.append(f"_Gerado em {agora.strftime('%d/%m/%Y as %H:%M')}_")
    return "\n".join(linhas)


def save_summary_document(
    reminders: list[dict],
    titulo: str = "Meus Lembretes",
) -> Optional[dict]:
    """
    Grava o resumo em downloads/ e devolve os dados do link de download.

    Retorna None se nao conseguir gravar.
    """
    try:
        conteudo = build_summary_markdown(reminders, titulo)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome = f"lembretes_{stamp}.md"
        caminho = _downloads_dir() / nome
        caminho.write_text(conteudo, encoding="utf-8")

        return {
            "filename": nome,
            "path": str(caminho),
            "url": f"/api/download?path={quote(str(caminho))}",
            "count": len(reminders),
        }
    except Exception as e:
        print(f"[reminders.doc] Falha ao gerar documento: {e}")
        return None


def build_spoken_summary(reminders: list[dict]) -> str:
    """
    Resumo curto para o Charon FALAR (a voz nao deve ler markdown nem URL).

    Ex.: "Voce tem 2 lembretes. Em 11/09 as 14:30, tomar remedio.
          E em 12/09 as 09:00, reuniao."
    """
    if not reminders:
        return "Voce nao tem nenhum lembrete agendado."

    pendentes = [r for r in reminders if (r.get("status") or "pending") == "pending"]
    if not pendentes:
        return "Voce nao tem lembretes pendentes."

    total = len(pendentes)
    cabeca = f"Voce tem {total} lembrete{'s' if total > 1 else ''}. "
    partes = []
    for r in pendentes[:5]:
        partes.append(f"{_fmt_humano(r.get('fire_at', ''), r.get('tz'))}: {r.get('message', '')}")
    corpo = " E ".join(partes)
    if total > 5:
        corpo += f" E mais {total - 5}."
    return cabeca + corpo
