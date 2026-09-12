"""
Teste: chamadas de ferramenta que o modelo emite como TEXTO.

SINTOMA RELATADO PELO USUARIO
"o modelo fala que vai fazer e fica ali no plano de execucao e nao faz"

No print da conversa aparecia isto, cru, no meio da resposta:

    <|DSML|og7d8j9uokjb1t4tq4l459m5f3...>...</|DSML|...>

ERAM DOIS BUGS SOMADOS

1. FORMATO DESCONHECIDO (DSML do DeepSeek V3.2/V4)
   Alguns modelos — sobretudo DeepSeek V4 via OpenRouter — nao devolvem
   `tool_calls` estruturado. Eles escrevem o markup nativo dentro do TEXTO. O
   DEEP-OS so conhecia XML do Gemini, JSON e `bash("...")`, entao nao reconhecia
   nada e nenhuma ferramenta rodava.
   O delimitador usa a barra vertical de LARGURA TOTAL (U+FF5C, "｜"), nao o "|"
   ASCII — comparar com o caractere errado faz o parser nunca casar.

2. FALTAVA O FALLBACK NO CAMINHO DAS TAREFAS
   `stream_chat_with_tools` TINHA fallback de texto; `complete_chat_with_tools`
   NAO tinha. As tarefas usam o nao-streaming, entao um modelo que emite a
   chamada em texto tinha o texto tratado como "resposta final" e o loop
   TERMINAVA — exatamente "anuncia e nao faz".

Este teste roda OFFLINE: nao chama nenhum provedor, so exercita o parser.
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
sys.path.insert(0, str(BACKEND))

falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


from core.llm_native import (  # noqa: E402
    extrair_dsml,
    extrair_tools_do_texto,
    limpar_markup_dsml,
)

V = "\uff5c"          # barra vertical de largura total (U+FF5C)
P = "|"               # barra vertical ASCII (U+007C)


def vl(tag: str) -> str:
    """Tag de abertura DSML (ajuda a montar os casos de teste)."""
    return f"<{V}DSML{V}{tag}>"


def vf(tag: str) -> str:
    """Fecha uma tag DSML: vf('invoke') -> </｜DSML｜invoke>"""
    return f"</{V}DSML{V}{tag}>"


print("=== 1. O caractere do delimitador importa ===")
check(V != P, "U+FF5C (largura total) != U+007C (ASCII)",
      "os dois caracteres sao iguais — a premissa do teste esta errada")
check(ord(V) == 0xFF5C, f"o delimitador correto e U+FF5C (0x{ord(V):04X})",
      f"codigo inesperado: 0x{ord(V):04X}")

print()
print("=== 2. Formato do DeepSeek V4: container tool_calls + parametros XML ===")
# Montado por concatenacao de proposito: deixar o U+FF5C explicito e mais
# legivel (e menos sujeito a erro) do que f-string com aninhamento.
v4 = (
    "<" + V + "DSML" + V + "tool_calls>\n"
    '<' + V + "DSML" + V + 'invoke name="bash">\n'
    '<' + V + "DSML" + V + 'parameter name="command" string="true">ls -la /root</' + V + "DSML" + V + "parameter>\n"
    "</" + V + "DSML" + V + "invoke>\n"
    "</" + V + "DSML" + V + "tool_calls>"
)
chamadas = extrair_dsml(v4)
check(len(chamadas) == 1, "extraiu 1 chamada", f"extraiu {len(chamadas)}")
if chamadas:
    c = chamadas[0]
    check(c["function"]["name"] == "bash", "nome da ferramenta = bash",
          f"nome extraido: {c['function']['name']}")
    args = json.loads(c["function"]["arguments"])
    check(args.get("command") == "ls -la /root",
          "parametro 'command' preservado como texto",
          f"parametros: {args}")
    check(c["type"] == "function" and c.get("id"),
          "formato OpenAI (type=function + id)", f"formato inesperado: {c}")

print()
print("=== 3. Formato do DeepSeek V3.2: container function_calls ===")
v32 = (
    "<" + V + "DSML" + V + "function_calls>"
    '<' + V + "DSML" + V + 'invoke name="read">'
    '{"path": "config.yaml"}'
    "</" + V + "DSML" + V + "invoke>"
    "</" + V + "DSML" + V + "function_calls>"
)
ch32 = extrair_dsml(v32)
check(len(ch32) == 1, "extraiu 1 chamada do container function_calls",
      f"extraiu {len(ch32)}")
if ch32:
    check(ch32[0]["function"]["name"] == "read", "nome = read",
          f"nome: {ch32[0]['function']['name']}")
    check(json.loads(ch32[0]["function"]["arguments"]).get("path") == "config.yaml",
          "JSON direto dentro do invoke foi lido",
          f"args: {ch32[0]['function']['arguments']}")

print()
print("=== 4. Varias chamadas na mesma resposta ===")
multi = (
    "<" + V + "DSML" + V + "tool_calls>"
    '<' + V + "DSML" + V + 'invoke name="bash">'
    '<' + V + "DSML" + V + 'parameter name="command" string="true">pwd</' + V + "DSML" + V + "parameter>"
    "</" + V + "DSML" + V + "invoke>"
    '<' + V + "DSML" + V + 'invoke name="glob">'
    '<' + V + "DSML" + V + 'parameter name="pattern" string="true">**/*.gguf</' + V + "DSML" + V + "parameter>"
    "</" + V + "DSML" + V + "invoke>"
    "</" + V + "DSML" + V + "tool_calls>"
)
cm = extrair_dsml(multi)
check(len(cm) == 2, "extraiu as 2 chamadas", f"extraiu {len(cm)}")
if len(cm) == 2:
    nomes = [c["function"]["name"] for c in cm]
    check(nomes == ["bash", "glob"], f"nomes na ordem: {nomes}", f"nomes: {nomes}")
    ids = [c["id"] for c in cm]
    check(len(set(ids)) == 2, "cada chamada tem id proprio", f"ids repetidos: {ids}")

print()
print("=== 5. Tipagem dos parametros (string=true/false/ausente) ===")
tipos = (
    "<" + V + "DSML" + V + "tool_calls>"
    '<' + V + "DSML" + V + 'invoke name="x">'
    '<' + V + "DSML" + V + 'parameter name="n" string="false">42</' + V + "DSML" + V + "parameter>"
    '<' + V + "DSML" + V + 'parameter name="b" string="false">true</' + V + "DSML" + V + "parameter>"
    '<' + V + "DSML" + V + 'parameter name="s" string="true">downloads</' + V + "DSML" + V + "parameter>"
    '<' + V + "DSML" + V + 'parameter name="cmd" string="true">ls -la</' + V + "DSML" + V + "parameter>"
    '<' + V + "DSML" + V + 'parameter name="sem" >texto solto</' + V + "DSML" + V + "parameter>"
    "</" + V + "DSML" + V + "invoke>"
    "</" + V + "DSML" + V + "tool_calls>"
)
ct = extrair_dsml(tipos)
if ct:
    a = json.loads(ct[0]["function"]["arguments"])
    check(a.get("n") == 42, "string=false com numero -> int 42", f"n = {a.get('n')!r}")
    check(a.get("b") is True, "string=false com booleano -> True", f"b = {a.get('b')!r}")
    check(a.get("s") == "downloads", "string=true -> texto", f"s = {a.get('s')!r}")
    check(a.get("cmd") == "ls -la",
          "COMANDO COM ESPACO nao e corrompido (texto preservado)",
          f"cmd = {a.get('cmd')!r}  <-- se virou lista/dict, quebra a ferramenta bash")
    check(a.get("sem") == "texto solto",
          "sem o atributo string, texto continua texto",
          f"sem = {a.get('sem')!r}")
else:
    check(False, "extraiu a chamada de tipagem", "nao extraiu nada")

print()
print("=== 6. Tolerancias: barra ASCII, invoke solto, sem fechamento perfeito ===")
# 6a. Barra vertical ASCII (alguns servidores normalizam o caractere)
ascii_dsml = (
    "<" + P + "DSML" + P + "tool_calls>"
    '<' + P + "DSML" + P + 'invoke name="bash">'
    '<' + P + "DSML" + P + 'parameter name="command" string="true">whoami</' + P + "DSML" + P + "parameter>"
    "</" + P + "DSML" + P + "invoke>"
    "</" + P + "DSML" + P + "tool_calls>"
)
ca = extrair_dsml(ascii_dsml)
check(len(ca) == 1 and ca[0]["function"]["name"] == "bash",
      "aceita barra ASCII (|) alem de U+FF5C",
      f"extraiu {len(ca)} do formato ASCII")

# 6b. Invoke SEM container (o modelo as vezes solta so o invoke)
solto = (
    '<' + V + "DSML" + V + 'invoke name="bash">'
    '<' + V + "DSML" + V + 'parameter name="command" string="true">df -h</' + V + "DSML" + V + "parameter>"
    "</" + V + "DSML" + V + "invoke>"
)
cs = extrair_dsml(solto)
check(len(cs) == 1, "aceita invoke sem o container tool_calls", f"extraiu {len(cs)}")

# 6c. Aspas simples no nome
simples = (
    "<" + V + "DSML" + V + "tool_calls>"
    "<" + V + "DSML" + V + "invoke name='bash'>"
    '<' + V + "DSML" + V + "parameter name='command' string='true'>pwd</" + V + "DSML" + V + "parameter>"
    "</" + V + "DSML" + V + "invoke>"
    "</" + V + "DSML" + V + "tool_calls>"
)
csi = extrair_dsml(simples)
check(len(csi) == 1, "aceita aspas simples", f"extraiu {len(csi)}")

print()
print("=== 7. O markup NAO pode aparecer para o usuario ===")
sujo = "Vou fazer a varredura agora.\n\n" + multi + "\n\nAguarde."
limpo = limpar_markup_dsml(sujo)
check("DSML" not in limpo, "o texto limpo nao contem mais 'DSML'",
      f"ainda contem markup: {limpo[:120]!r}")
check(V not in limpo, "nenhum delimitador U+FF5C sobrou",
      f"sobrou delimitador: {limpo[:120]!r}")
check("Vou fazer a varredura agora." in limpo,
      "o texto normal em volta foi preservado",
      f"o texto util foi perdido: {limpo!r}")
check("Aguarde." in limpo, "o texto depois do bloco foi preservado",
      f"o texto posterior foi perdido: {limpo!r}")

# Caso do print do usuario: tag com nome ilegivel
ilegivel = "Vou executar " + "<" + V + "DSML" + V + "og7d8j9uokjb1t4tq4l459m5f3??ehco</" + V + "DSML" + V + "og7d8j9t?" + " agora"
li = limpar_markup_dsml(ilegivel)
check("DSML" not in li, "tag com nome ilegivel tambem e removida",
      f"sobrou: {li!r}")

# Texto sem DSML nao pode ser alterado
intacto = "Resposta normal, com | pipe ASCII e {json: 1} no meio."
check(limpar_markup_dsml(intacto) == intacto,
      "texto sem DSML volta intacto (nao corrompe resposta normal)",
      f"alterou o texto: {limpar_markup_dsml(intacto)!r}")

print()
print("=== 8. extrair_tools_do_texto: cobre DSML e os formatos antigos ===")
check(len(extrair_tools_do_texto(multi)) == 2, "DSML com 2 chamadas -> 2",
      "nao extraiu as 2 do DSML")
# Formato antigo (JSON) precisa continuar funcionando
antigo = '```json\n{"tool": "bash", "params": {"command": "ls"}}\n```'
ca2 = extrair_tools_do_texto(antigo)
check(len(ca2) == 1 and ca2[0]["function"]["name"] == "bash",
      "formato JSON antigo continua sendo extraido",
      f"quebrou o formato antigo: {ca2}")
# Gemini XML
gem = '<tc_call><function=bash>ls</function></tc_call>'
check(len(extrair_tools_do_texto(gem)) >= 0, "Gemini XML nao levanta excecao", "")
# Texto comum nao pode virar chamada
check(extrair_tools_do_texto("Bom dia! Como posso ajudar?") == [],
      "conversa normal NAO vira chamada de ferramenta",
      "texto comum foi interpretado como ferramenta")

print()
print("=== 9. A assimetria dos dois caminhos foi corrigida ===")
LLM = BACKEND / "core" / "llm_native.py"
texto = LLM.read_text(encoding="utf-8")


def corpo_da_funcao(nome: str) -> str:
    m = re.search(rf"(?:async )?def {nome}\(.*?(?=\n(?:@|async def |def ))", texto, re.S)
    return m.group(0) if m else ""


c_stream = corpo_da_funcao("stream_chat_with_tools")
c_complete = corpo_da_funcao("complete_chat_with_tools")

check("extrair_tools_do_texto" in c_stream,
      "o caminho STREAMING usa extrair_tools_do_texto",
      "o caminho streaming nao usa o extrator que conhece DSML")
check("extrair_tools_do_texto" in c_complete,
      "o caminho NAO-STREAMING (tarefas) usa extrair_tools_do_texto",
      "o caminho das tarefas continua SEM fallback — era a causa do bug relatado")

# O guarda `if tools:` no fallback evita inventar ferramenta em conversa normal
check(re.search(r"if tools:\s*\n\s*do_texto = extrair_tools_do_texto", c_complete) is not None,
      "o fallback do nao-streaming so roda quando ferramentas foram oferecidas",
      "sem o guarda `if tools:`, uma conversa que cite JSON viraria chamada de ferramenta")

check("limpar_markup_dsml" in c_stream and "limpar_markup_dsml" in c_complete,
      "os dois caminhos removem o markup do texto visivel",
      "o markup ainda pode aparecer cru no chat")

print()
print("=== 10. FiltroDSML: o marcador nao pode vazar no FLUXO ===")
# O usuario continuou vendo o markup na tela MESMO com o parser funcionando. O
# motivo: a limpeza existia so no texto FINAL; num stream, os tokens chegam em
# pedacos arbitrarios e limpar token a token nao pega nada.
from core.llm_native import FiltroDSML  # noqa: E402

# 10a. Marcador PARTIDO em varios tokens (o caso que vazava)
f = FiltroDSML()
partes = [
    "Vou executar agora: ",
    "<" + V + "DS",
    "ML" + V + "tool_calls>",
    '<' + V + "DSML" + V + 'invoke name="bash">',
    '<' + V + "DSML" + V + 'parameter name="command" string="true">ls</' + V + "DSML" + V + "parameter>",
    "</" + V + "DSML" + V + "invoke>",
    "</" + V + "DSML" + V + "tool_calls>",
    " pronto.",
]
saida = "".join(f.alimentar(p) for p in partes) + f.finalizar()
check("DSML" not in saida,
      f"marcador partido entre tokens nao vaza (saida: {saida!r})",
      f"o marcador vazou no fluxo: {saida!r}")
check(f.viu_markup, "o filtro registra que houve markup", "viu_markup nao foi marcado")
check("Vou executar agora:" in saida and "pronto." in saida,
      "o texto util em volta foi preservado",
      f"o texto util foi perdido: {saida!r}")

# 10b. O caso EXATO do print do usuario: tag ilegivel, sem nome nem parametros
f2 = FiltroDSML()
saida2 = "".join(f2.alimentar(p) for p in [
    "Sistema operacional, kernel, hostname ",
    "<" + V + "DSML" + V + "og7d8j9uokjb1t4tq4l459m5f3>",
]) + f2.finalizar()
check("DSML" not in saida2, "tag ilegivel tambem nao vaza",
      f"vazou: {saida2!r}")
check(f2.viu_markup, "viu_markup detecta a tentativa de ferramenta",
      "viu_markup nao detectou — o aviso ao usuario nao apareceria")

# 10c. Texto comum precisa passar INTACTO e sem atraso
f3 = FiltroDSML()
normal = "".join(f3.alimentar(p) for p in ["Bom ", "dia, ", "Wilson. ", "Tudo ", "certo?"]) + f3.finalizar()
check(normal == "Bom dia, Wilson. Tudo certo?",
      "texto comum passa intacto (espacos entre tokens preservados)",
      f"o texto foi alterado: {normal!r}")

# 10d. Um "<" solto (sinal de menor, uso normal) nao pode travar o texto
f4 = FiltroDSML()
menor = "".join(f4.alimentar(p) for p in ["o valor e ", "< ", "10."]) + f4.finalizar()
check("< 10." in menor or "<10" in menor.replace(" ", "<") or "10" in menor,
      "um '<' de comparacao nao engole o texto seguinte",
      f"o texto apos o '<' foi perdido: {menor!r}")
check(len(menor) >= 12, f"o texto do '<' foi devolvido (len={len(menor)})",
      f"o '<' segurou texto demais: {menor!r}")

print()
print("=== 11. Aviso honesto quando a chamada vem inutilizavel ===")
# Sem isto, a resposta fica "concluida" e vazia — o usuario acha que ele
# prometeu e nao entregou, sem entender por que.
CHAT = BACKEND / "routes" / "chat.py"
texto_chat = CHAT.read_text(encoding="utf-8")
check("FiltroDSML" in texto_chat,
      "o caminho de chat usa o filtro de fluxo",
      "o chat simples continua transmitindo tokens CRUS (era o vazamento)")
check("viu_markup" in texto_chat,
      "o chat avisa quando o modelo tentou ferramenta e nada saiu",
      "sem o aviso, a resposta fica vazia como se tivesse funcionado")
check("limpar_markup_dsml" in texto_chat,
      "o texto final salvo tambem e limpo",
      "o texto final continua com markup (é o que fica na tela)")

print()
print("=" * 70)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("RESULTADO: TODOS OS TESTES PASSARAM — DSML parseado nos dois caminhos")
