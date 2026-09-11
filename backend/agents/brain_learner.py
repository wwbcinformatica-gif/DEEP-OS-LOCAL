"""
brain_learner.py â€” Motor de Neuroplasticidade Epistêmica do DEEP-OS

Responsabilidade:
- Analisar o brain_log de cada tarefa executada pelo agente
- Destilar um insight técnico ultra-compacto via LLM
- Persistir o aprendizado no faq.json + reconstruir o índice FAISS
- Garantir que futuros agentes (mesmo de outros modelos) herdem o conhecimento

Integrado ao loop.py: chamado automaticamente ao final de cada tarefa bem-sucedida.
"""

import json
import os

from core.config import faq_path
from core.llm_native import build_messages, complete_chat_with_tools
from core.rag import rebuild_vectorstore

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PROMPT DE SÃNTESE DE NEURÃ”NIO
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
BRAIN_EVOLUTION_PROMPT = """
Você é o Cérebro Central do DEEP-OS. Sua função é a Neuroplasticidade Epistêmica: extrair aprendizados eternos.
Analise a TAREFA executada e o LOG resumido de passos/erros.
Gere um insight de conhecimento altamente compacto, técnico e direto (máximo 3 linhas) para que futuros agentes (você ou outros modelos) saibam exatamente como agir ou contornar esse problema direto da próxima vez.

REGRAS:
1. Seja extremamente conciso. Vá direto ao ponto técnico (ex: "Ao manipular a pasta X, use sempre o comando Y pois Z falha").
2. Nunca use tom de conversa. Forneça pura sabedoria procedural.
3. Se o log não contiver nenhum erro ou insight relevante, responda exatamente: "Nenhum aprendizado novo necessário."
"""


async def aprender_com_a_tarefa(
    task: str,
    brain_log: list,
    provider: str = "groq",
    model: str = "mixtral-8x7b-32768"
) -> dict:
    """
    Analisa os acertos/erros da tarefa recente, destila um neurÃ´nio ultra-compacto
    e injeta direto no ecossistema de conhecimento compartilhado (faq.json + FAISS).

    Args:
        task: Descrição da tarefa executada
        brain_log: Lista de passos registrados pelo loop.py
        provider: Provider LLM para gerar o insight
        model: Modelo LLM para gerar o insight

    Returns:
        dict com status e informação do neurÃ´nio criado (se houver)
    """
    # â”€â”€ 1. Monta um resumo compacto do log para o prompt â”€â”€
    log_resumido = []
    for step in brain_log:
        acao = step.get("action", "")
        log_resumido.append({
            "step": step.get("step"),
            "action": acao,
            "success": not any(
                palavra in str(acao).lower()
                for palavra in ["falha", "bloqueado", "erro", "abortado"]
            )
        })

    payload_analise = (
        f"TAREFA: {task}\n\n"
        f"LOG DOS PASSOS:\n{json.dumps(log_resumido, ensure_ascii=False, indent=2)}"
    )

    messages = build_messages(
        system_prompt=BRAIN_EVOLUTION_PROMPT,
        user_message=payload_analise
    )

    try:
        # â”€â”€ 2. Gera o insight técnico via LLM â”€â”€
        response = await complete_chat_with_tools(
            provider=provider,
            model=model,
            messages=messages,
            tools=[],
            temperature=0.1
        )

        insight_tecnico = (response.get("data") or "").strip()

        # Se o modelo diz que não há aprendizado novo, apenas retorna
        if not insight_tecnico or "nenhum aprendizado novo" in insight_tecnico.lower():
            return {
                "status": "skipped",
                "reason": "Nenhum insight novo detectado pelo modelo.",
                "neuronio_id": None
            }

        # â”€â”€ 3. Monta o bloco de neurÃ´nio no formato markdown â”€â”€
        titulo_resumido = task[:60].strip()
        texto_neuronio = (
            f"# ðŸ§  NEURÃ”NIO EVOLUTIVO DE AGENTE\n"
            f"**Contexto:** {titulo_resumido}...\n"
            f"**Aprendizado Técnico:** {insight_tecnico}\n"
            f"*Consolidado automaticamente pelo motor de Neuroplasticidade Epistêmica.*"
        )

        # â”€â”€ 4. Persiste no faq.json â”€â”€
        if os.path.exists(faq_path):
            try:
                with open(faq_path, encoding="utf-8") as f:
                    dados_conhecimento = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                dados_conhecimento = []
        else:
            dados_conhecimento = []

        novo_id = max(
            (item.get("id", 0) for item in dados_conhecimento),
            default=0
        ) + 1

        dados_conhecimento.append({
            "id": novo_id,
            "texto": texto_neuronio
        })

        with open(faq_path, "w", encoding="utf-8") as f:
            json.dump(dados_conhecimento, f, indent=2, ensure_ascii=False)

        # â”€â”€ 5. Reconstrói o índice FAISS para efeito imediato â”€â”€
        rebuild_vectorstore(str(faq_path))

        print(
            f"[CÃ‰REBRO VIVO] NeurÃ´nio ID {novo_id} integrado ao ecossistema global!\n"
            f"          Insight: {insight_tecnico[:100]}..."
        )

        return {
            "status": "success",
            "neuronio_id": novo_id,
            "insight": insight_tecnico,
            "message": f"NeurÃ´nio {novo_id} criado e indexado no FAISS."
        }

    except Exception as e:
        print(f"[CÃ‰REBRO VIVO] Falha ao fundir memórias: {e}")
        return {
            "status": "error",
            "reason": str(e),
            "neuronio_id": None
        }
