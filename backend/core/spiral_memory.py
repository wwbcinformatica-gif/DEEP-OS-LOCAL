"""
DEEP-OS â€” Spiral Memory (DEEP-OS)
=============================================
Sistema de memoria em espiral onde dois modelos trabalham em sincronia:

  Modelo A (Worker): executa ferramentas, gera codigo, resolve a tarefa
  Modelo B (Keeper): monitora o contexto do Worker, extrai o essencial,
                     e reinjeta um "snapshot" compacto periodico para
                     evitar que o Worker perca o fio da meada.

O Keeper e chamado a cada N passos para:
  1. Varrer o historico de ferramentas executadas
  2. Extrair: arquivo atual, ultima acao, erros, decisoes, progresso
  3. Gerar um bloco de contexto compacto
  4. Injeta-lo como mensagem de sistema no Worker
"""

from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger("wbc.spiral_memory")

INTERVALO_PADRAO = 4

def extrair_snapshot(mensagens: list[dict], tool_logs: list[dict]) -> dict:
    """
    Extrai um snapshot compacto do estado atual SEM chamar LLM.
    Usa regras deterministicas para extrair o essencial do historico recente.
    """
    snapshot = {
        "arquivo_atual": "",
        "ultima_acao": "",
        "erros_recentes": [],
        "comandos_executados": [],
        "arquivos_modificados": [],
        "total_passos": len(tool_logs),
        "decisoes": [],
    }

    recentes = tool_logs[-6:] if tool_logs else []

    for log in recentes:
        ferramenta = log.get("tool", "")
        params = log.get("params", {})
        resultado = log.get("result", {})

        if ferramenta in ("read", "write", "edit", "delete", "rename"):
            caminho = params.get("path", params.get("filePath", params.get("new_path", "")))
            if caminho:
                nome = caminho.split("/")[-1] or caminho
                if ferramenta == "read":
                    snapshot["arquivo_atual"] = nome
                elif ferramenta in ("write", "edit"):
                    if nome not in snapshot["arquivos_modificados"]:
                        snapshot["arquivos_modificados"].append(nome)
                    snapshot["arquivo_atual"] = nome
                elif ferramenta == "delete":
                    snapshot["decisoes"].append(f"deletado {nome}")

        if ferramenta == "bash":
            cmd = params.get("command", "")
            if any(kw in cmd for kw in ("git commit", "git add", "git push")):
                snapshot["decisoes"].append(f"commit: {cmd[:50]}")
            elif "npm install" in cmd or "pip install" in cmd:
                pass  # trivial, nao polui
            elif cmd and not cmd.startswith("cd "):
                snapshot["comandos_executados"].append(cmd[:50])
                snapshot["ultima_acao"] = f"bash: {cmd[:60]}"

        if ferramenta == "web_search":
            query = params.get("query", "")
            snapshot["decisoes"].append(f"buscou: {query[:40]}")

        if isinstance(resultado, dict) and resultado.get("error"):
            erro = str(resultado["error"])[:120]
            if erro not in snapshot["erros_recentes"]:
                snapshot["erros_recentes"].append(erro)

    return snapshot


def formatar_snapshot_para_prompt(snapshot: dict) -> str:
    """Formata o snapshot como mensagem de sistema comprimida."""
    linhas = ["[DEEP-OS MEMORY REFRESH] Resumo do estado atual do trabalho:"]

    if snapshot["arquivo_atual"]:
        linhas.append(f"  Arquivo atual: {snapshot['arquivo_atual']}")

    if snapshot["arquivos_modificados"]:
        mods = ", ".join(snapshot["arquivos_modificados"][-3:])
        linhas.append(f"  Arquivos modificados: {mods}")

    if snapshot["ultima_acao"]:
        linhas.append(f"  Ultima acao: {snapshot['ultima_acao']}")

    if snapshot["erros_recentes"]:
        for e in snapshot["erros_recentes"][:2]:
            linhas.append(f"  Erro: {e}")

    if snapshot["decisoes"]:
        dec = "; ".join(snapshot["decisoes"][-3:])
        linhas.append(f"  Decisoes recentes: {dec}")

    if snapshot["total_passos"]:
        linhas.append(f"  Passos de ferramentas executados: {snapshot['total_passos']}")

    linhas.append(
        "\n[CONTEXTO PRESERVADO] Este e um resumo do que voce estava fazendo. "
        "Nao repita acoes ja realizadas. Continue o trabalho de onde parou."
    )

    return "\n".join(linhas)


async def gerar_snapshot_com_llm(
    mensagens: list[dict],
    tool_logs: list[dict],
    provider: str,
    model: str,
    api_key: str = "",
) -> str | None:
    """
    Versao avancada: usa o Modelo B (Keeper) para gerar um snapshot
    mais inteligente, com sumarizacao semantica do que foi feito.

    Esta funcao so e chamada se o Keeper estiver configurado com um
    modelo especifico (ex: deepseek-r1:7b para rapidez).
    """
    try:
        ultimas_msgs = []
        for m in mensagens[-8:]:
            if m.get("content"):
                ultimas_msgs.append({"role": m["role"], "content": str(m["content"])[:300]})

        ferramentas_resumo = []
        for log in tool_logs[-7:]:
            ferr = log.get("tool", "?")
            params = log.get("params", {})
            res = log.get("result", {})
            if isinstance(res, dict):
                resumo_res = "ok" if not res.get("error") else f"erro: {res['error'][:60]}"
            else:
                resumo_res = str(res)[:60]
            ferramentas_resumo.append(f"[{ferr}] {resumo_res}")

        prompt_keep = (
            "Voce e o Keeper de memoria do sistema DEEP-OS.\n"
            "Sua funcao: analisar o historico abaixo e gerar UM PARAGRAFO curto "
            "respondendo: o que o Worker estava fazendo, qual arquivo estava editando, "
            "qual o proximo passo esperado.\n"
            "Seja OBJETIVO. Nao use markdown. Nao saudacoes.\n\n"
            f"Ferramentas executadas:\n{chr(10).join(ferramentas_resumo)}\n\n"
            f"Ultimas mensagens:\n{json.dumps(ultimas_msgs, ensure_ascii=False)[:2000]}\n\n"
            "Resumo do estado atual (uma linha):"
        )

        from core.llm_native import complete_chat_with_tools
        resposta = await complete_chat_with_tools(
            provider, model,
            [{"role": "user", "content": prompt_keep}],
            tools=[],
            temperature=0.2,
            api_key=api_key,
        )
        conteudo = resposta.get("content") or resposta.get("data") or ""
        if conteudo.strip():
            return (
                "[DEEP-OS MEMORY REFRESH] Resumo semantico do Keeper:\n"
                f"  {conteudo.strip()[:400]}\n\n"
                "[CONTEXTO PRESERVADO] Continue o trabalho de onde parou."
            )
    except Exception as e:
        _log.warning("[DEEP-OS] Keeper LLM falhou: %s. Usando snapshot raw.", e)

    return None


def deve_refrescar(
    passo: int,
    tool_logs: list[dict],
    ultimo_refresh: int,
    intervalo: int = INTERVALO_PADRAO,
) -> bool:
    """Decide se e hora de refrescar a memoria espiral."""
    if passo < 2:
        return False
    if passo - ultimo_refresh < intervalo:
        return False
    recentes = tool_logs[-intervalo:] if tool_logs else []
    return len(recentes) > 0
