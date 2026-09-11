# MEMORY — Auditoria das tools do Charon no VPS + resumo de lembretes em documento

Continuação da sessão de correções (ver `MEMORY-identidade-tenant-lembretes-audio.md`).

---

## 1. BUG GRAVE ENCONTRADO: `backend/config/` sombreava o `config.py` da raiz

### Sintoma
Três actions **não importavam** — e uma delas (`youtube_video`) era oferecida como
tool do Charon mesmo assim:

```
flight_finder  IMPORT FALHOU: cannot import name 'is_windows' from 'config'
game_updater   IMPORT FALHOU: cannot import name 'get_os' from 'config'
youtube_video  IMPORT FALHOU: cannot import name 'get_os' from 'config'
```

### Causa raiz (sutil)
Existe um **diretório** `backend/config/` (com `api_keys.json` e `permissions.json`)
que **não tem `__init__.py`**. O Python o trata como *namespace package*:

```python
>>> import config
>>> config.__file__   # None  -> pacote VAZIO, sem get_os/is_headless
>>> importlib.util.find_spec('config')
ModuleSpec(name='config', loader=None,
  submodule_search_locations=NamespacePath([...'backend\\config']))
```

O namespace package `backend/config/` **venceu** o `config.py` real da raiz do
projeto, porque rodando `uvicorn main:app` de dentro de `backend/` o `sys.path`
tem `backend/` antes da raiz.

### Correção
Criado **`backend/config.py`** (um arquivo real tem precedência sobre o
diretório de mesmo nome). Ele carrega o `config.py` da raiz via `importlib` e
re-exporta: `get_os`, `is_windows`, `is_mac`, `is_linux`, `is_headless`.
Tem fallback próprio caso o arquivo da raiz não exista.

**NÃO mover nem renomear `backend/config.py`** — a posição é o que faz o shim
funcionar. **NÃO criar `backend/config/__init__.py`.**

Resultado: 21/21 actions importam (antes: 18/21).

### Como detectar de novo
```bash
cd backend && python -c "import config; print(config.__file__, hasattr(config,'get_os'))"
# Esperado: /root/DEEP-OS/backend/config.py True
# Se der None False -> o sombreamento voltou
```

---

## 2. Tools que NÃO funcionam em VPS headless

`_HEADLESS_EXCLUDED` (em `routes/voice_ws.py`) estava **incompleto** — o
`send_message` ficou de fora, mas usa pyautogui/pyperclip para colar texto em
apps de mensagem, o que não existe num servidor.

### Lista corrigida
```python
_HEADLESS_EXCLUDED = {
    "open_app", "browser_control", "desktop_control", "computer_control",
    "computer_settings", "screen_process", "game_updater", "send_message",
}
```

### Por que o guard antigo não bastava
Vários actions usam o padrão:

```python
try:
    import pyautogui
    _PYAUTOGUI = True
except Exception:
    _PYAUTOGUI = False
```

Isso **funciona** (usam `except Exception`), mas só significa "pyautogui
importou". Em Linux **com** X11 o import passa e o uso é que falha. Pior:
`screen_processor._capture_screen()` só checa `if not _MSS` (instalação), não
se há tela — no VPS o `mss` está instalado, então ele passa do guard e falha
no `mss.mss()` com `ScreenShotError`.

Por isso a filtragem por **lista de nomes** é o mecanismo certo, não depender
do guard interno de cada action.

### Observações de nomes
- `game_updater` está na lista de exclusão mas **não é uma tool declarada**
  para o Gemini (só existe como arquivo de action). Filtro inócuo — mantido por
  segurança caso vire tool.
- `_HEADLESS_EXCLUDED` usa nomes de **tool** (`desktop_control`,
  `screen_process`), não de arquivo (`desktop.py`, `screen_processor.py`).
  Manter essa convenção.

---

## 3. Resumo de lembretes como DOCUMENTO (feature pedida)

### Contexto
O usuário acessa o Charon por uma interface **sem página própria** — ele não
"abre a página". O que funciona é o padrão que já era usado para resumos:
gerar um documento e devolver um **link de download**.

Mecanismo (o mesmo do `save_document`):
1. grava o arquivo em `<raiz>/downloads/`
2. devolve link `/api/download?path=<caminho-url-encoded>`
3. `routes/download.py` serve via `FileResponse` com `Content-Disposition: attachment`
4. `ALLOWED_DIRS` inclui `<raiz>/docs` e `<raiz>/downloads` — **só esses** são servíveis

### Implementado
**`core/reminder_doc.py`** (novo):
- `build_summary_markdown()` — resumo em markdown para o arquivo
- `build_spoken_summary()` — resumo CURTO para a voz (sem markdown nem URL)
- `save_summary_document()` — grava em `downloads/` e devolve
  `{filename, path, url, count}`

**Tool `list_reminders`** (nova, adicionada em `BASIC_TOOL_DECLARATIONS` e
`MEDIUM_TOOL_DECLARATIONS`):
- parâmetro `document='sim'` -> gera o documento e devolve o link
- sem `document` -> só fala o resumo em voz

**Rotas novas** (`routes/reminders.py`):
- `GET /api/reminders/summary` — resumo em texto
- `GET /api/reminders/export` — gera o documento e devolve o link

### Regra para a voz
A IA **nunca** deve ler a URL em voz alta — só dizer que o link foi enviado.
Reforçado na system instruction (modo headless) junto com a orientação de
entregar listas/resumos como documento.

### Verificado
`tests-manual/test_reminder_summary.py` — todos passando:
resumo vazio, resumo em voz sem markdown/URL, markdown completo, documento
gravado em `downloads/`, link no formato `/api/download?path=`, e isolamento
por tenant (resumo do t2 não contém lembretes do t1).

---

## 4. Armadilhas conhecidas do `/api/download`

- `ALLOWED_DIRS` tem caminhos **hardcoded** (`C:/DEEP-OS/docs`,
  `/root/DEEP-OS/docs`, ...). Se o projeto mudar de lugar, o download quebra.
- **`downloads/` é compartilhado entre tenants.** Um tenant que descubra o
  nome do arquivo de outro consegue baixá-lo. Pendência de segurança conhecida —
  o caminho ideal seria `downloads/<tenant_id>/`.

## 5. Verificação no VPS (rodar de lá, não do Windows)
O audit roda de verdade só no Linux:
```bash
cd /root/DEEP-OS/backend
python -c "
import config; print('config:', config.__file__, hasattr(config,'get_os'))
from config import is_headless; print('headless:', is_headless())
import pyautogui; print('pyautogui.size:', pyautogui.size())
"
```
No VPS, `pyautogui.size()` deve **falhar** com `KeyError: 'DISPLAY'` —
confirmando por que essas tools precisam ser filtradas.
