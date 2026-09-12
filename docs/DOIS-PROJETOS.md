# DEEP-OS — Os dois projetos gêmeos: regra de sincronização

**Última atualização:** 2026-09-12

> ## ⛔ REGRA OBRIGATÓRIA
>
> **TODA alteração feita em `C:\DEEP-OS` DEVE ser feita também em
> `C:\DEEP-OS-LOCAL` — e vice-versa.**
>
> Vale para qualquer modelo de IA que trabalhe neste projeto. Não termine uma
> tarefa deixando os dois diferentes.

---

## 1. Por que existem dois

| Projeto | Caminho | Papel |
|---------|---------|-------|
| **DEEP-OS** | `C:\DEEP-OS` | principal — é o que roda na VPS (`deep-os.tech`) |
| **DEEP-OS-LOCAL** | `C:\DEEP-OS-LOCAL` | mesma aplicação, para rodar na máquina do usuário |

O usuário usa o LOCAL no dia a dia (`C:\DEEP-OS-LOCAL\start-saas.bat`) e o
DEEP-OS para publicar. **São o mesmo produto**: um bug corrigido em um e não no
outro significa que o usuário vai encontrar o bug de novo no outro.

---

## 1.1 Um é para a VPS, o outro é para uso LOCAL

Esta é a diferença **conceitual** mais importante: não são duas cópias iguais em
ambientes iguais — são **o mesmo código em ambientes opostos**.

| | **DEEP-OS** → VPS | **DEEP-OS-LOCAL** → máquina do usuário |
|---|---|---|
| **Para que serve** | produção, público, multi-tenant | uso diário dele, sozinho |
| **Onde roda** | servidor Linux `2.25.143.185` | o PC dele (Windows) |
| **Tela** | **nenhuma** (headless) | desktop completo |
| **RAM** | **4 GB** (disco 48 GB) | muito mais, com **GPU** |
| **Como inicia** | systemd `deepos-backend.service` + nginx | `start-saas.bat` (3 janelas) |
| **Acesso** | internet, via HTTPS + proxy reverso | `localhost:5176` |
| **Ollama** | instalado, **zero modelos** | **25+ modelos** (≈110 GB) |
| **Ferramentas de GUI** | ❌ removidas por `is_headless()` | ✅ funcionam |
| **Deploy** | `scripts/deploy-faf8f93.sh` | não se aplica |
| **Portas** | 8001 (API), 80/443 (nginx) | 8001, 5176, + chatbot 8010 |

### O que um modelo de IA precisa entender disso

**1. A sincronização é do CÓDIGO, não do resultado.**
A mesma correção entra nos dois, mas o efeito depende do ambiente. Um recurso
pode funcionar no LOCAL e não na VPS (ou o contrário) **sem que nada esteja
errado na sincronização**.

**2. Certos bugs só aparecem em um dos lados — teste no ambiente certo:**

| Tipo de problema | Onde aparece | Por quê |
|---|---|---|
| Proxy / `Host` / nginx / JWT 401 | **só na VPS** | localmente o `Host` é `localhost` e o middleware `ProtecaoSensiveis` **libera**; na VPS o `Host` é externo e **exige** auth |
| Ferramenta que abre app, controla tela, captura tela | **só no LOCAL** | na VPS não há display; as tools são filtradas |
| Falta de modelo local | **só na VPS** | Ollama lá está sem nenhum modelo |
| Memória / swap / OOM | **só na VPS** | 4 GB de RAM |
| Caminho com `:` no nome | **só na VPS** | Linux aceita, Windows proíbe |
| Permissão de pasta / caminho `/root/...` | **só na VPS** | estrutura Linux |

**3. Não "conserte" um quebrando o outro.**
Exemplos reais do que **não** fazer:
- remover o filtro `is_headless()` para uma tool de GUI "funcionar na VPS" — ela
  vai falhar em produção;
- assumir GPU ou RAM sobrando na VPS;
- usar caminho `C:\...` em código que roda na VPS (ou `/root/...` no LOCAL).

**4. O `.gguf` da VPS é uma armadilha.**
Existe **um** modelo em `/root/models/qwen2.5-coder-7b.gguf` (4,4 GB). Parece que
dá para usar na VPS, mas **não dá**: são 4 GB de RAM, e um 7B em Q4 mais o cache
de contexto não cabe — entraria em swap e derrubaria o backend junto. Esse
arquivo é útil no PC, que tem GPU.

**5. O que é específico de cada um e NÃO deve ser sincronizado:**
`.env`, `backend/config/api_keys.json`, `backend/config/provedores_custom.json`,
`data/`, `downloads/`, `Pessoal/`, `venv/`, `node_modules/`, `dist-saas/` e
`tools/verificar-deploy.cjs` (só faz sentido onde há VPS).

---

## 2. O que os torna diferentes (e por que não dá para "só copiar a pasta")

### 2.1 São repositórios git SEPARADOS — cada um com o SEU no GitHub

| | DEEP-OS | DEEP-OS-LOCAL |
|---|---------|---------------|
| Caminho | `C:\DEEP-OS` | `C:\DEEP-OS-LOCAL` |
| **Repositório** | `github.com/wwbcinformatica-gif/DEEP-OS.git` | `github.com/wwbcinformatica-gif/DEEP-OS-LOCAL.git` |
| **Branch** | **`master`** | **`main`** |
| Histórico | SHAs próprios | SHAs próprios (diferentes!) |

Os commits **não são os mesmos objetos** — as mensagens até se parecem, mas os
hashes são distintos. Os dois repositórios não compartilham ancestral comum
utilizável.

> ### ⚠️ UM PUSH NÃO ATUALIZA O OUTRO
>
> São **dois repositórios independentes**. `git push` no `DEEP-OS.git` **não**
> altera nada no `DEEP-OS-LOCAL.git` — e vice-versa.
>
> Se você sincronizou os arquivos mas deu push em apenas um, o outro ficou com o
> código novo **só na máquina**: na próxima vez que alguém clonar, ou fizer
> `git reset --hard origin/<branch>`, a alteração **desaparece**.
>
> **São DOIS commits e DOIS pushes, sempre** — e atenção: as branches têm nomes
> diferentes (`master` no principal, `main` no gêmeo). Um `git push origin
> master` no LOCAL falharia, porque lá a branch é `main`.

> ### ⚠️ NUNCA faça `git reset --hard` de um para o outro
>
> Isso substituiria o histórico inteiro do outro projeto. Você apagaria:
> - todos os commits dele;
> - `README-LOCAL.md`, `INICIAR-LOCAL.bat`, `START-TOTAL.bat`, `STOP-TOTAL.bat`;
> - `chatbot-server/` (gateway Node na porta 8010, que só existe no LOCAL);
> - `generated/`, `config/` e o que mais for específico dele.

### 2.2 Diferenças estruturais conhecidas

| Item | DEEP-OS | DEEP-OS-LOCAL |
|------|---------|---------------|
| Ambiente Python (venv) | `C:\DEEP-OS\venv\` | `C:\DEEP-OS-LOCAL\backend\venv\` |
| Inicialização | `START-TOTAL.bat` / deploy | `start-saas.bat` |
| Portas | 8001 / 5175–5176 | 8001 / 5176 (+ chatbot 8010) |
| Arquivos só dele | `RECUPERAR-VPS.md` | `README-LOCAL.md`, `chatbot-server/`, `generated/` |

O venv em pastas diferentes é uma armadilha real: o `tests-manual/run_all.py`
procurava só em `<raiz>/venv` e, no LOCAL, a suíte falhava na largada dizendo que
o Python não existia — parecia bug do código, era do runner. Já corrigido (o
runner procura em 6 caminhos), mas **é o tipo de detalhe que difere entre os
dois**.

---

## 3. O procedimento correto

### Passo 1 — Faça a alteração no DEEP-OS normalmente

Trabalhe, teste, e **commite** (isso é essencial: o passo 2 compara commits).

### Passo 2 — Descubra o commit ANTERIOR à sua mudança

```powershell
cd C:\DEEP-OS
git log --oneline -5
```

Guarde o hash do commit **de antes** das suas alterações.

### Passo 3 — Compare (NÃO PULE ESTE PASSO)

```powershell
python tools\comparar-local.py <commit-anterior>
```

O resultado classifica cada arquivo alterado:

| Classificação | Significado | Ação |
|---------------|-------------|------|
| **IDENTICO** | o gêmeo estava igual ao DEEP-OS antes da mudança | copiar é seguro |
| **NOVO** | o arquivo nem existia antes | copiar é seguro |
| **AUSENTE** | não existe no gêmeo | copiar (ou avaliar se se aplica) |
| **DIFERENTE** | **o gêmeo tem código próprio nesse arquivo** | 🛑 **PARAR e revisar à mão** |

> **Por que o passo 3 é obrigatório:** sem ele, copiar sobrescreveria qualquer
> trabalho específico do gêmeo **sem aviso**. O comparador é a rede de proteção.

### Passo 4 — Aplique

Se o passo 3 não acusou nenhum **DIFERENTE**:

```powershell
python tools\aplicar-no-local.py <commit-anterior>
```

Além de copiar, ele confere as **dependências** que as correções usam
(middleware de segurança, `auth.py`, `tenant_identity.py`…) e as pastas que só o
gêmeo tem, para não destruir nada.

### Passo 5 — Verifique os DOIS

```powershell
cd C:\DEEP-OS
.\venv\Scripts\python.exe tests-manual\run_all.py

cd C:\DEEP-OS-LOCAL
.\backend\venv\Scripts\python.exe tests-manual\run_all.py
```

Ambos precisam passar. Suítes diferentes = sincronização incompleta.

### Passo 6 — Commit + push nos DOIS

Cada um no **seu** remoto e na **sua** branch:

```powershell
cd C:\DEEP-OS        ; git push origin master
cd C:\DEEP-OS-LOCAL  ; git push origin main
```

---

## 4. Resultados reais desta prática

| Sincronização | Arquivos | Divergências | Suíte no gêmeo |
|---------------|----------|--------------|----------------|
| Sessão 49 (chaves, modelos, Charon, provedores) | 33 | **0** | 16/16 |
| Sessão 49b (parser DSML, painel VS Code) | 8 | **0** | 17/17 |

Zero divergências nas duas vezes — ou seja, os dois projetos realmente evoluíram
em paralelo com o mesmo conteúdo. Mas isso **só foi confirmado porque o passo 3
foi executado**; sem ele seria uma suposição.

---

## 5. Ferramentas

| Ferramenta | O que faz |
|-----------|-----------|
| `tools/comparar-local.py <commit>` | Classifica cada arquivo alterado: IDENTICO / NOVO / AUSENTE / DIFERENTE |
| `tools/aplicar-no-local.py <commit>` | Copia os arquivos e valida dependências e pastas exclusivas do gêmeo |

Ambas aceitam o commit base como argumento. Sem argumento, usam `06d620c`
(padrão histórico) — **prefira sempre passar o commit explícito**.

> **Nota para o LOCAL:** as duas ferramentas ficam no DEEP-OS e também são
> copiadas para o gêmeo, para que um modelo trabalhando a partir de qualquer um
> dos dois consiga fazer a sincronização.

---

## 6. O que NÃO deve ser sincronizado

| Item | Por quê |
|------|---------|
| `backend/.env` | cada máquina tem as suas chaves |
| `backend/config/api_keys.json` | idem |
| `backend/config/provedores_custom.json` | idem (provedores de cada instalação) |
| `data/`, `downloads/`, `Pessoal/` | dados de cada máquina |
| `tools/verificar-deploy.cjs` | confere o deploy no VPS; o LOCAL não tem VPS |
| `venv/`, `node_modules/`, `dist-saas/` | gerados localmente |

---

## Ver também

- [`../AGENTS.md`](../AGENTS.md) — a regra no topo, para todo modelo ler primeiro
- [`../memory.md`](../memory.md) — regras e armadilhas do projeto
- [`FERRAMENTAS.md`](FERRAMENTAS.md) — execução de ferramentas (DSML)
- [`MODELOS.md`](MODELOS.md) — por que modelos davam 404
- [`PROVEDORES.md`](PROVEDORES.md) — provedores comuns e personalizados
