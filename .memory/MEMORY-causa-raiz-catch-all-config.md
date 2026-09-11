# MEMORY — CAUSA RAIZ do vazamento de identidade: catch-all antes das rotas literais

Descoberto em 2026-09-11, **depois** de várias correções que tratavam sintoma.
Commit da correção: `a54c84c`.

---

## O BUG

Em `backend/routes/config.py`, a rota **catch-all** estava registrada **antes**
das rotas literais:

```python
# linha 102 — catch-all, registrada PRIMEIRO
@router.get("/{section}")
async def get_config_section(section: str):
    data = _read_config()
    return data.get(section, {})     # devolve o config.yaml GLOBAL

# linha 147 — rota literal, registrada DEPOIS (NUNCA alcancada)
@router.get("/identity")
async def get_identity(...):
    ...  # identidade por tenant
```

**O FastAPI resolve rotas na ORDEM DE REGISTRO.** Então `GET /api/config/identity`
casava com `/{section}` e caía no `get_config_section("identity")`, que lê o
`config.yaml` **global**.

### Consequências (o que o usuário via)

- O frontend **sempre** leu a identidade GLOBAL — nunca a do tenant.
- **Toda** a implementação de isolamento por tenant (`assistant_name`,
  `user_name`, `voice`) ficava **inacessível por HTTP**.
- Daí "trocar a voz/nome muda para todos os usuários".
- O `PUT` **funcionava** (o catch-all era só GET), gravava certo no banco — e o
  `GET` devolvia o global. Isso produzia o sintoma mais confuso de todos:
  **"salva, mas aparece para todos"**.

### Correção

Catch-all movido para o **FIM** do arquivo, com um bloco de aviso em destaque.
Verificado que as outras rotas continuam funcionando: `/voice`,
`/accent-theme`, `/agent-models`, `/mcp-servers`, `/api-key`, `/agent`.

---

## REGRA APRENDIDA (a mais importante desta sessão)

**Rotas catch-all (`/{param}`) DEVEM ficar por último em qualquer router FastAPI.**

Se um path literal não responde como esperado, **verifique a ordem de registro
ANTES de suspeitar da lógica**. Sintoma típico: a função "não executa", o valor
lido não corresponde ao gravado, ou o problema aparece só via HTTP (e não na
chamada direta da função).

### Como diagnosticar

```python
# Lista as rotas na ORDEM real de registro
for r in app.routes:
    print(sorted(getattr(r, 'methods', []) or []), r.path, '->', r.endpoint.__name__)
```

Se uma rota literal aparecer **depois** de um catch-all que a casaria, é isso.

### Erro metodológico que me custou muitas rodadas

Eu testava a **função** `get_identity(...)` diretamente — e ela sempre
funcionava. O bug estava no **roteamento HTTP**. Passei várias rodadas
convencido de que "o código está certo" (estava!) sem perceber que **não era
ele que respondia**.

**Regra: teste pela rota (HTTP), não só pela função.** Foi
`tests-manual/test_identity_endpoint.py` que expôs o problema — ele usa
`TestClient`/ASGI e compara o que a API devolve com o que está no banco.

---

## Outras causas tratadas antes (todas reais, mas secundárias)

Estas correções continuam válidas e eram necessárias — só não eram a causa raiz:

1. `/api/config/identity` não tinha autenticação nenhuma (`candidate` sem JWT).
2. `voice` era gravada no `config.yaml` global junto com `custom_color`; agora
   é coluna por tenant (`tenants.voice`).
3. As duas contas master emitiam o **mesmo** `sub` (`master-admin`) e nenhuma
   tinha linha em `tenants` → caíam no global. Agora cada uma tem chave própria
   (`master-admin:<email>`) e linha criada automaticamente.
4. `require_plan` devolvia 404 para o admin (sem linha em `tenants`), fazendo
   rota existente parecer inexistente.
5. `ZoneInfo` sem banco de fusos (Windows sem `tzdata`) fazia o fuso cair em
   UTC — lembretes 3h errados. Fallback de offset fixo + `tzdata` no
   requirements.
6. `_parse_fire_at` truncava a string em 19 chars e rejeitava
   `YYYY-MM-DD HH:MM` (16 chars) → HTTP 400 para horário válido.

---

## CORREÇÃO DE UMA AFIRMAÇÃO MINHA ERRADA

Em memórias anteriores eu escrevi que `middleware/tenant.py` era **"código
morto"** / "não montado no main.py". **ESTÁ ERRADO** — ele é montado em
`main.py:65` (`app.add_middleware(TenantMiddleware)`).

A conclusão errada veio de uma busca que falhou em silêncio: usei
`Select-String -Path ... -Recurse` e `-Recurse` **não é um parâmetro válido**
para `Select-String` (é de `Get-ChildItem`). O comando deu erro, o resultado
vazio parecia "não existe", e eu tomei isso como evidência.

**Regra: quando uma busca retorna vazio, confirme que o comando de busca em si
funcionou.** Um erro de sintaxe na ferramenta não é evidência de ausência.

---

## Estado final verificado em produção

```
commit publicado: fcf3120

A = wwbc22@gmail.com          B = wwbcinformatica@gmail.com
A salva voz=Kore nome=Atena   scope: tenant
A releitura: {"assistant_name":"Atena","voice":"Kore"}      OK persistiu
B releitura: {"assistant_name":"Charon","voice":"Charon"}   OK nao afetado

>>> ISOLAMENTO FUNCIONANDO
```
