# RAG LOCAL — assistente que conhece o DEEP-OS

Um assistente rodando **na sua maquina**, que responde sobre este projeto usando
a sua propria documentacao. Sem nuvem, sem enviar nada para fora.

## Como funciona

```
sua pergunta
     │
     ├─ 1. busca os trechos relevantes em memory.md, STATUS.md, docs/, .memory/
     │     (busca lexical com IDF + sinonimos do dominio — sem dependencias)
     │
     ├─ 2. monta um prompt com esses trechos
     │
     └─ 3. envia para um modelo LOCAL (Ollama) → resposta
```

O ponto-chave: **o modelo nao precisa "saber" o DEEP-OS.** Ele recebe os
trechos certos e responde com base neles. Por isso um modelo de 7B ja resolve —
quem carrega o conhecimento e a sua documentacao.

## Uso

```bash
# 1. (uma vez) construir o indice a partir da documentacao
python tools/rag_local.py indexar

# 2. perguntar (precisa do Ollama rodando: `ollama serve`)
python tools/perguntar.py "por que a voz nao salvava por usuario?"

# escolher outro modelo
python tools/perguntar.py --modelo llama-3.2-3b:latest "como faco o deploy?"

# ver quais modelos voce tem
python tools/perguntar.py --modelos

# so mostrar os trechos (sem chamar o modelo)
python tools/perguntar.py --contexto "duas units systemd na porta 8001"
```

### Ferramentas separadas

```bash
python tools/rag_local.py indexar                  # reconstroi o indice
python tools/rag_local.py buscar "sua pergunta"    # ranking dos trechos
python tools/rag_local.py contexto "sua pergunta"  # contexto pronto p/ colar
python tools/rag_local.py stats                    # o que esta indexado
```

## Criar um modelo proprio do projeto

Embutir a documentacao no modelo, para nao precisar passar contexto sempre:

```bash
python tools/perguntar.py --modelfile
ollama create deepos -f Modelfile
ollama run deepos
```

## Reindexar quando a documentacao mudar

O indice **nao** se atualiza sozinho. Depois de editar `memory.md`,
`STATUS.md` ou qualquer arquivo em `docs/`/`.memory/`:

```bash
python tools/rag_local.py indexar
```

## O que esta indexado

`memory.md`, `STATUS.md`, `RECUPERAR-VPS.md`, `AGENTS.md`, `CLAUDE.md`,
`README.md`, `manual.md`, `docs/*.md`, `.memory/MEMORY-*.md` — cerca de
**32 arquivos / 493 trechos**.

O indice fica em `.rag/indice.json` (no `.gitignore` — e gerado).

## Por que sem FAISS / sentence-transformers

Nao estao instalados no venv, e a busca lexical funciona bem para documentacao
tecnica: o vocabulario e especifico (nomes de funcao, arquivo, erro), o que da
muito sinal ao IDF.

Para busca **semantica** (melhor quando a pergunta usa palavras diferentes das
do texto):

```bash
pip install faiss-cpu sentence-transformers
```
e troque `buscar()` por embeddings — o projeto ja tem esqueleto em
`backend/memory/vector_memory.py` e `backend/core/rag.py`.

## Limitacoes conhecidas (honestamente)

1. **Atribuicao de fonte pode errar.** Quando dois trechos pontuam perto, o
   modelo pequeno as vezes cita a secao errada. O *conteudo* costuma estar
   certo; a *citacao* nao. Confira o arquivo citado antes de confiar.
2. **Sinonimos sao uma lista curada**, nao aprendida. Se a pergunta usar uma
   palavra que nao esta no mapa (`SINONIMOS` em `rag_local.py`), a busca pode
   perder o trecho certo. Adicionar la e barato.
3. **Chunks por secao de markdown.** Uma resposta muito espalhada (ex: "como
   funciona o Charon inteiro") vem fragmentada.
4. **Modelos de 3B alucinam mais.** Prefira 7B+ para respostas tecnicas.
5. **O indice fica velho** se voce nao reindexar depois de editar a doc.

## Dica de uso

Para perguntas sobre um problema especifico, use as **palavras que aparecem na
documentacao** (nomes de arquivo, de funcao, texto do erro). Ex:

- bom: `"Errno 98 address already in use"`, `"catch-all antes de literal"`
- pior: `"o servidor nao funciona"`

A busca lexical recompensa vocabulario preciso.
