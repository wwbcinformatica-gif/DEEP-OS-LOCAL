---
id: continuous-learning
name: 'Continuous Learning & Memory Protocol'
description: "Protocol for storing and retrieving knowledge, solutions, and context into the Obsidian Vault's memory bank."
---

# 🧠 Continuous Learning Protocol

> **MANDATORY:** Apply this skill whenever an agent reaches a conclusion, resolves an issue, performs complex analysis, or explicitly discovers a new "best practice" in the workspace.

## 🌍 Universal Memory (Model Agnostic)

This memory bank is the **primary source of truth** for all conversational models using this toolkit.

- **Format over Flavor:** By using standard Markdown and YAML, we ensure that whether the agent is Gemini, Claude, GPT, or a local Qwen model, the context is interpreted identically.
- **Shared Context:** Always treat `Conhecimento_AI` as the collective intelligence of the vault.

## 📥 1. Retrieval Phase (Read Context)

Before starting complex tasks or analyses:

1. **Search Memory:** Use the `grep_search` or `list_dir` tool on `c:\Users\User\Documents\Obsidian Vault\Conhecimento_AI`.
2. **Contextualize:** Identify if there are previous notes related to the current task (e.g., previous PDF analyses, device repair history, or coding guidelines).
3. **Apply:** Integrate the retrieved knowledge into the current task's execution plan.

## 📤 2. Storage Phase (Write Memory)

When you successfully finish a task, create a meaningful conclusion, or perform a valuable bench analysis ("análise de bancada"):

1. **Don't Forget:** You MUST document the learning.
2. **Path:** `c:\Users\User\Documents\Obsidian Vault\Conhecimento_AI\`
3. **Naming Convention:** Use descriptive filenames replacing spaces with hyphens, e.g., `Diagnostic-Power-Supply-Failure.md`.

## 📝 3. Note Format

Notes must be created as standard Markdown with YAML Frontmatter for Obsidian Dataview:

```markdown
---
data: YYYY-MM-DD
tipo: [Analise | Resolucao | Diretriz | Discussao]
projeto: 'Name of the project or context'
tags: ['#conhecimento-ai', '#tag-relevante1', '#tag-relevante2']
---

# [Title of Knowledge]

## Contexto

(Briefly explain what was the problem, task, or request).

## Conclusão / Solução

(Document what was discovered, what was the correct technical resolution, or what was the final guideline established).

## Por que guardar isso?

(Explain why this is an important memory for future agent interactions).
```
