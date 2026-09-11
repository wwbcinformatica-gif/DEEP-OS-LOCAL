# ⚠️ AVISO CRÍTICO — FORMATO DEFINITIVO

**NUNCA altere o formato da transcricao do painel direito.**

Cada palavra/trecho aparece como uma entrada SEPARADA com timestamp, empilhando em tempo real. NAO acumular em uma unica mensagem. NAO esperar turn_complete. Enviar cada pedaco imediatamente.

Este formato e DEFINITIVO e sempre funcionou assim. Qualquer mudanca causa lentidao e quebra a conversa em tempo real.

---

# CharonPage — Layout Oficial (NÃO ALTERAR)

**Arquivo:** `frontend/src/components/saas/CharonPage.tsx`

Este documento define o layout EXATO do painel do Charon. Outros modelos devem SEGUIR este layout. NÃO mover elementos de posição.

---

## Estrutura do Painel Central (Chat)

```
┌─────────────────────────────────────────────────────────────┐
│ ATIVIDADES  [+ limpar]          ● ● registros              │  ← Header
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Log de atividades — pesquisas, tools, resultados]         │  ← chatArea (flex:1, scroll)
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ── (drag handle — redimensionar textarea) ──               │  ← inputSection
│  ┌─────────────────────────────────────────────────────┐    │
│  │ [textarea — campo de mensagem]                      │    │  ← Linha 1 (acima)
│  ├─────────────────────────────────────────────────────┤    │
│  │ ● Charon ativo  [barra áudio]        [▶ enviar]     │    │  ← Linha 2 (abaixo)
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Regras do inputSection (campo de mensagem):

1. **Drag handle** (topo): barra fina horizontal para redimensionar o textarea (pointer events, `ns-resize`)
2. **Linha 1:** `<textarea>` — ocupa largura total (`width: 100%`)
3. **Linha 2:** flex row com `justifyContent: 'space-between'`:
   - Esquerda: dot verde + "Charon ativo"/"Charon inativo" (fonte 11, cor `sc`)
   - Esquerda (opcional): barra de áudio (quando `audioLevel > 0`)
   - Direita: botão enviar (`sendBtn`)

### CSS:
```css
/* textarea base — NÃO colocar width no flex item do inputSection */
textarea: { width: '100%', height: 60, resize: 'none', ... }

/* no JSX do inputSection — usar: */
<div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
  <textarea style={{ ...s.textarea, height: textareaHeight, resize: 'none', ... }} />
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
    {/* Charon ativo + áudio à esquerda, botão enviar à direita */}
  </div>
</div>
```

---

## Painel Direito (Voz)

```
┌─────────────────────────┐
│ ⚡ Charon    [ouvindo]  │  ← Header (toggle on/off)
├─────────────────────────┤
│                         │
│  [Transcrição da voz]   │  ← messagesList (flex:1, scroll)
│  (user + Charon)        │
│                         │
├─────────────────────────┤
│ ● Charon ativo · Voz: X │  ← Footer
└─────────────────────────┘
```

### Regras do painel direito:
- Largura variável (240-600px) — drag handle na borda esquerda
- Transcrição acumulada (palavras juntam no turn_complete)
- NÃO envia mensagem de texto (apenas no painel central)

---

## Painel de Configurações

Abas: Chat | Configuracoes

Seções em Configurações:
1. **Identidade** — Nome assistente (read-only), Seu nome
2. **Aparencia** — Cor de acento
3. **Voz do Charon** — Grid de 8 vozes
4. **Filtro de Contexto** — Textarea para tópicos relevantes (localStorage `charon_context_filter`)
5. **Chaves API** — Google Gemini, Groq

---

## Estados

| Estado | Cor | Uso |
|--------|-----|-----|
| idle | #666 | Charon desligado |
| connecting | #ff0 | Conectando ao Gemini |
| listening | #0c0 | Ouvindo (verde) |
| speaking | #0af | Falando |
| processing | #f80 | Processando tool |
| error | #f44 | Erro |

---

## Mensagens WebSocket

| Tipo | Origem | Destino |
|------|--------|---------|
| `status` | backend | console/log |
| `transcript` | backend | painel direito |
| `tool_start` | backend | painel central |
| `tool_result` | backend | painel central |
| `turn_complete` | backend | painel direito (limpa áudio) |
| `error` | backend | painel central + status |
| `connected` | backend | painel direito (ativa) |
| `disconnected` | backend | painel direito (desativa) |

---

## ⚠️ AVISO

Este layout foi validado pelo usuário. Qualquer mudança deve ser aprovada explicitamente. Não alterar posições, cores ou estrutura sem permissão.
