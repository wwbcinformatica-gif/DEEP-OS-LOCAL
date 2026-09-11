"""
DEEP-OS — Cérebro Evolutivo (Brain)
============================================
Neuroplasticidade Epistêmica: extrai aprendizados eternos de tarefas executadas.

Complementa o sistema de memória elástica (elastic_memory.py) com:
- Extração de insight técnico via LLM
- Persistência em faq.json (retrocompatibilidade)
- Integração com o sistema RAG vetorial
"""

import asyncio
import json
import os

from core.config import faq_path
from core.llm_native import complete_chat_with_tools
from core.rag import rebuild_vectorstore

BRAIN_EVOLUTION_PROMPT = """
Você é o Cérebro Central do DEEP-OS. Sua função é a Neuroplasticidade Epistêmica: extrair aprendizados eternos.
Analise a TAREFA executada e o LOG resumido de passos/erros.
Gere um insight de conhecimento altamente compacto, técnico e direto (máximo 3 linhas) para que futuros agentes saibam exatamente como agir ou contornar esse problema direto da próxima vez.
REGRAS:
1. Seja extremamente conciso. Vá direto ao ponto técnico.
2. Nunca use tom de conversa. Forneça pura sabedoria procedural.
"""

STRUCTURED_SUMMARY_PROMPT = """
Analise a tarefa executada e gere um resumo estruturado em JSON com os seguintes campos:
{
  "problema": "descrição curta do problema resolvido",
  "solucao": "descrição da solução aplicada",
  "ferramentas": ["lista", "de", "ferramentas", "usadas"],
  "lições": "lições aprendidas (1-2 frases técnicas)"
}
Retorne APENAS o JSON, sem texto adicional.
"""


async def extrair_resumo_estruturado(task: str, brain_log: list, provider: str, model: str) -> dict | None:
    """Extrai resumo estruturado da tarefa para indexação na memória elástica."""
    log_resumido = []
    for step in brain_log:
        log_resumido.append({
            "step": step.get("step"),
            "action": step.get("action"),
            "success": "falha" not in str(step.get("action")).lower()
                       and "bloqueado" not in str(step.get("action")).lower()
        })

    payload = f"TAREFA: {task}\n\nLOG DOS PASSOS:\n{json.dumps(log_resumido, ensure_ascii=False)}"
    messages = [
        {"role": "system", "content": STRUCTURED_SUMMARY_PROMPT},
        {"role": "user", "content": payload},
    ]

    try:
        response = await complete_chat_with_tools(provider, model, messages, [], temperature=0.1)
        raw = (response.get("data") or "").strip()
        if raw:
            # Tenta extrair JSON do resposta
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[CÉREBRO] Falha ao extrair resumo estruturado: {e}")
    return None


async def aprender_com_a_tarefa(task: str, brain_log: list, provider: str, model: str):
    log_resumido = []
    for step in brain_log:
        log_resumido.append({
            "step": step.get("step"),
            "action": step.get("action"),
            "success": "falha" not in str(step.get("action")).lower() and "bloqueado" not in str(step.get("action")).lower()
        })
    payload_analise = f"TAREFA: {task}\n\nLOG DOS PASSOS:\n{json.dumps(log_resumido, ensure_ascii=False)}"
    messages = [
        {"role": "system", "content": BRAIN_EVOLUTION_PROMPT},
        {"role": "user", "content": payload_analise}
    ]
    try:
        response = await complete_chat_with_tools(provider, model, messages, [], temperature=0.1)
        insight_tecnico = (response.get("data") or "").strip()
        if insight_tecnico and not insight_tecnico.startswith("ERR:"):
            texto_neuronio = f"# [🧠 NEURÔNIO EVOLUTIVO DE AGENTE] - Contexto: {task[:50]}...\n**APRENDIZADO TÉCNICO:** {insight_tecnico}\n*Consolidado de forma autônoma para o aprendizado eterno.*"

            def _sync_read_faq():
                if os.path.exists(faq_path):
                    try:
                        with open(faq_path, encoding="utf-8") as f:
                            return json.load(f)
                    except (json.JSONDecodeError, OSError) as e:
                        print(f"[CÉREBRO] Erro ao ler faq.json: {e}")
                        return []
                return []

            def _sync_write_faq(dados):
                with open(faq_path, "w", encoding="utf-8") as f:
                    json.dump(dados, f, indent=2, ensure_ascii=False)

            dados_conhecimento = await asyncio.to_thread(_sync_read_faq)
            novo_id = max([item.get("id", 0) for item in dados_conhecimento], default=0) + 1
            dados_conhecimento.append({"id": novo_id, "texto": texto_neuronio})
            await asyncio.to_thread(_sync_write_faq, dados_conhecimento)
            rebuild_vectorstore(faq_path)

            # ── Elastic Memory: também indexa o insight ──
            try:
                from memory.elastic_memory import index_task_memory
                await index_task_memory(
                    task=task,
                    solution_summary=insight_tecnico[:1000],
                    tools_used=[],
                    lessons_learned=insight_tecnico[:500],
                )
            except (OSError, json.JSONDecodeError, ValueError) as e:
                print(f"[CÉREBRO] Elastic memory indexação secundária falhou (I/O ou dados): {e}")
            except Exception as e:
                print(f"[CÉREBRO] Elastic memory indexação secundária falhou (inesperado): {type(e).__name__}: {e}")

            return {"status": "success", "neuronio_id": novo_id, "insight": insight_tecnico}
    except Exception as e:
        print(f"[CÉREBRO VIVO] Falha ao fundir memórias: {e}")
    return {"status": "failed"}
