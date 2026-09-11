"""
DEEP-OS Tool Definitions
============================
OpenAI-compatible function definitions for tool-calling agents.
Can be filtered by toolset using ``get_tools_by_toolset()``.
"""

from tools.toolsets import filter_function_defs, resolve_multiple_toolsets

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Le o conteudo de um arquivo ou lista arquivos de um diretorio. Aceita paths absolutos (ex: C:\\DEEP-OS, C:\\Users) ou relativos. Retorna o conteudo COMPLETO por padrao. Use offset/limit para paginação se o arquivo for muito grande.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho do arquivo ou diretorio. Aceita paths absolutos (C:\\pasta) ou relativos (backend/core)"},
                    "root": {"type": "string", "description": "Diretorio raiz do projeto (opcional)"},
                    "offset": {"type": "integer", "description": "Pagina para ler (0=primeira). Use com limit para paginação."},
                    "limit": {"type": "integer", "description": "Caracteres por pagina (ex: 50000). Sem limit = arquivo completo."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Cria ou sobrescreve um arquivo com conteudo. Aceita paths absolutos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho do arquivo. Aceita paths absolutos (C:\\pasta\\arquivo.py)"},
                    "content": {"type": "string", "description": "Conteudo do arquivo"},
                    "root": {"type": "string", "description": "Diretorio raiz do projeto (opcional)"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Executa um comando no terminal do sistema. Tem acesso TOTAL a todas as unidades (C:\\, D:\\, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando a ser executado (ex: dir C:\\, ls C:\\Users)"},
                    "workdir": {"type": "string", "description": "Diretorio de trabalho (opcional)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explorer",
            "description": "Lista o conteudo de um diretorio. Aceita paths absolutos (ex: C:\\, C:\\Users\\Desktop).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho absoluto (C:\\pasta) ou subpasta relativa"},
                    "root": {"type": "string", "description": "Diretorio raiz (opcional)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Busca um padrao de texto em arquivos do projeto",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Texto ou regex para buscar"},
                    "path": {"type": "string", "description": "Diretorio onde buscar (opcional)"},
                    "include": {"type": "string", "description": "Filtro de extensao ex: *.py (opcional)"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "Executa codigo Python em ambiente isolado",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Codigo Python para executar"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Cria uma ou mais pastas",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho da pasta a criar"},
                    "root": {"type": "string", "description": "Diretorio raiz do projeto (opcional)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete",
            "description": "Deleta um arquivo ou pasta",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho do arquivo ou pasta"},
                    "root": {"type": "string", "description": "Diretorio raiz do projeto (opcional)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename",
            "description": "Renomeia ou move um arquivo ou pasta",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_path": {"type": "string", "description": "Caminho atual"},
                    "new_path": {"type": "string", "description": "Novo caminho"},
                    "root": {"type": "string", "description": "Diretorio raiz do projeto (opcional)"}
                },
                "required": ["old_path", "new_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_mcp_servers",
            "description": "Lista todos os servidores MCP do OpenClaude ativos e suas ferramentas disponiveis",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "init_mcp_plugin",
            "description": "Inicializa um plugin MCP do OpenClaude pelo nome (ex: github, discord, telegram). Apos iniciar, as ferramentas do plugin ficam disponiveis automaticamente com o formato plugin__nomeDaFerramenta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome do plugin MCP (ex: github, discord, telegram, fakechat)"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Abre um programa ou executavel no sistema. Procura em Program Files, AppData, PATH e Start Menu. Use quando o usuario pedir para abrir qualquer programa (ex: 'abra o Chrome', 'abra o Spotify', 'abra calculadora').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Nome do programa (ex: chrome, spotify, notepad, calc, explorer)"},
                    "path": {"type": "string", "description": "Caminho completo do executavel (opcional, se souber)"},
                    "args": {"type": "string", "description": "Argumentos adicionais (opcional)"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_file",
            "description": "Procura arquivos em TODA a maquina por nome parcial. Use quando o usuario pedir para encontrar musicas, videos, documentos ou qualquer arquivo. Procura em todas as unidades (C:, D:, G:, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome parcial do arquivo (ex: Jefferson, musica, .mp3, hino)"},
                    "pattern": {"type": "string", "description": "Padrao wildcard (ex: *.mp3, *Jefferson*)"},
                    "drive": {"type": "string", "description": "Unidade especifica (ex: C:, D:). Vazio = todas as unidades."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Fecha um processo ou arquivo aberto no sistema",
            "parameters": {
                "type": "object",
                "properties": {
                    "process_name": {"type": "string", "description": "Nome do processo (ex: notepad.exe)"},
                    "file_path": {"type": "string", "description": "Caminho do arquivo aberto para fechar"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "media_play",
            "description": "Abre um arquivo de midia no player interno do projeto",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome do arquivo de midia"},
                    "path": {"type": "string", "description": "Caminho completo do arquivo"},
                    "isVideo": {"type": "boolean", "description": "true para video, false para musica"}
                },
                "required": ["name", "path"]
            }
        }
    },

    # â”€â”€ Task Management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    {
        "type": "function",
        "function": {
            "name": "task_create",
            "description": "Cria uma nova tarefa no sistema de gerenciamento de tarefas",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Titulo da tarefa"},
                    "description": {"type": "string", "description": "Descricao detalhada da tarefa"},
                    "active_form": {"type": "string", "description": "Descricao no presente continuo (ex: 'Executando build')"}
                },
                "required": ["subject"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_get",
            "description": "Obtem o status e detalhes de uma tarefa pelo ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID da tarefa"}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_update",
            "description": "Atualiza o status ou metadados de uma tarefa",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID da tarefa"},
                    "status": {"type": "string", "description": "Novo status: pending, running, completed, failed, killed"},
                    "output": {"type": "string", "description": "Texto de saida/resultado da tarefa"}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_list",
            "description": "Lista todas as tarefas, opcionalmente filtradas por status",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filtrar por status: pending, running, completed, failed (opcional)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_stop",
            "description": "Para/interrompe uma tarefa em execucao",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID da tarefa a parar"}
                },
                "required": ["task_id"]
            }
        }
    },
    # â”€â”€ Web Search â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Busca informacoes na internet usando DuckDuckGo. Retorna titulos, URLs e snippets dos resultados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Termo de busca"}
                },
                "required": ["query"]
            }
        }
    },
    # â”€â”€ File Edit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    {
        "type": "function",
        "function": {
            "name": "file_edit",
            "description": "Edita um arquivo substituindo exatamente um trecho de texto por outro. A string antiga deve ser unica no arquivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho do arquivo"},
                    "old_string": {"type": "string", "description": "Texto exato a ser substituido (deve aparecer uma unica vez)"},
                    "new_string": {"type": "string", "description": "Novo texto"},
                    "root": {"type": "string", "description": "Diretorio raiz (opcional)"}
                },
                "required": ["path", "old_string", "new_string"]
            }
        }
    },
    # â”€â”€ Web Fetch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Busca o conteudo de uma URL e retorna como texto markdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL completa para buscar"},
                    "prompt": {"type": "string", "description": "Instrucao opcional para processar o resultado"}
                },
                "required": ["url"]
            }
        }
    },
    # ── Document Reader ──────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Le o conteudo de documentos: PDF, DOCX, XLSX, CSV, XML, TXT, PPTX e outros formatos. Retorna o texto extraido com metadados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho do arquivo (relativo ou absoluto)"},
                    "root": {"type": "string", "description": "Diretorio raiz do projeto (opcional)"}
                },
                "required": ["path"]
            }
        }
    },
    # ── Tool Search ─────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "tool_search",
            "description": "Busca ferramentas disponiveis pelo nome ou descricao. Use quando nao souber qual ferramenta usar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "O que voce quer fazer (ex: 'editar arquivo', 'buscar na web')"}
                },
                "required": ["query"]
            }
        }
    },
    # â”€â”€ Glob â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Busca arquivos por padrao glob (ex: **/*.py, src/**/*.tsx).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Padrao glob para buscar arquivos"},
                    "path": {"type": "string", "description": "Diretorio base (opcional)"}
                },
                "required": ["pattern"]
            }
        }
    },
    # â”€â”€ Agent Forking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    {
        "type": "function",
        "function": {
            "name": "fork_subagent",
            "description": "Cria um subagente para executar uma tarefa especifica em paralelo. O subagente tem acesso limitado a ferramentas e roda de forma independente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Descricao detalhada da tarefa para o subagente"},
                    "system_prompt": {"type": "string", "description": "Instrucoes adicionais para o subagente (opcional)"}
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_subagent_result",
            "description": "Obtem o resultado de um subagente apos sua execucao.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subagent_id": {"type": "string", "description": "ID do subagente"}
                },
                "required": ["subagent_id"]
            }
        }
    },
    # â”€â”€ Agent Teams â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    {
        "type": "function",
        "function": {
            "name": "team_create",
            "description": "Cria um time de agentes para coordenacao de tarefas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome do time"},
                    "members": {"type": "array", "items": {"type": "string"}, "description": "Lista de nomes dos membros (opcional)"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "team_delete",
            "description": "Deleta um time de agentes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "string", "description": "ID do time"}
                },
                "required": ["team_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Envia uma mensagem para outro agente do time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Nome do agente destinatario"},
                    "message": {"type": "string", "description": "Conteudo da mensagem"}
                },
                "required": ["recipient", "message"]
            }
        }
    },
    # â”€â”€ Cron â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    {
        "type": "function",
        "function": {
            "name": "cron_create",
            "description": "Agenda uma tarefa para execucao recorrente usando expressao cron.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Expressao cron de 5 campos (minuto hora dia mes dia-da-semana). Ex: '0 9 * * *' = todo dia as 9h"},
                    "task": {"type": "string", "description": "Descricao da tarefa a executar"}
                },
                "required": ["expression", "task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cron_delete",
            "description": "Remove um job cron agendado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "ID do job cron"}
                },
                "required": ["job_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cron_list",
            "description": "Lista todos os jobs cron ativos.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    # â”€â”€ Memory Tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    {
        "type": "function",
        "function": {
            "name": "memory_write",
            "description": "Salva informacao na memoria de longo prazo do agente (namespace + chave + conteudo).",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Namespace: conversations, project_knowledge, reflections, preferences"},
                    "key": {"type": "string", "description": "Chave unica para recuperacao"},
                    "content": {"type": "string", "description": "Conteudo a ser armazenado"}
                },
                "required": ["namespace", "key", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_read",
            "description": "Le informacao da memoria de longo prazo pelo namespace + chave.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Namespace: conversations, project_knowledge, reflections, preferences"},
                    "key": {"type": "string", "description": "Chave unica para leitura"}
                },
                "required": ["namespace", "key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_list",
            "description": "Lista todas as chaves salvas em um namespace de memoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Namespace: conversations, project_knowledge, reflections, preferences"}
                },
                "required": ["namespace"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_delete",
            "description": "Apaga uma entrada especifica da memoria de longo prazo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Namespace: conversations, project_knowledge, reflections, preferences"},
                    "key": {"type": "string", "description": "Chave a ser removida"}
                },
                "required": ["namespace", "key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "monitor_dashboard",
            "description": "Coleta dados de CPU, RAM e ultimas linhas de log do servidor para o dashboard de monitoramento.",
            "parameters": {
                "type": "object",
                "properties": {
                    "linhas_log": {"type": "integer", "description": "Quantidade de linhas de log para retornar (padrao 20)"}
                },
                "required": []
            }
        }
    },
    # ── Charon Tools (mesmas ferramentas do voice assistant) ──
    {
        "type": "function",
        "function": {
            "name": "youtube_video",
            "description": "Controla YouTube: reproduzir videos, resumir, obter info ou mostrar trending. Use quando o usuario pedir para abrir YouTube, tocar musica, ver video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "play | summarize | get_info | trending"},
                    "query": {"type": "string", "description": "Busca para play (ex: 'James Blunt Goodbye My Lover')"},
                    "save": {"type": "boolean", "description": "Salvar resumo no Notepad"},
                    "region": {"type": "string", "description": "Codigo do pais para trending (ex: BR, US)"},
                    "url": {"type": "string", "description": "URL do video para get_info"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_control",
            "description": "Controla navegadores web: abrir sites, buscar, clicar, preencher, scroll, screenshot, navegacao.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "go_to | search | click | type | scroll | screenshot | back | forward | reload | close"},
                    "browser": {"type": "string", "description": "chrome | edge | firefox | opera | brave"},
                    "url": {"type": "string", "description": "URL para go_to"},
                    "query": {"type": "string", "description": "Busca para search"},
                    "selector": {"type": "string", "description": "CSS selector para click/type"},
                    "text": {"type": "string", "description": "Texto para digitar ou clicar"},
                    "direction": {"type": "string", "description": "up | down para scroll"},
                    "amount": {"type": "integer", "description": "Quantidade de scroll (default: 500)"},
                    "key": {"type": "string", "description": "Tecla para press (ex: Enter, F5)"},
                    "path": {"type": "string", "description": "Caminho para salvar screenshot"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "computer_settings",
            "description": "Controla o computador: volume, brilho, atalhos de teclado, fechar apps, fullscreen, WiFi, reiniciar, desligar, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Acao a executar"},
                    "description": {"type": "string", "description": "Descricao em linguagem natural"},
                    "value": {"type": "string", "description": "Valor opcional: nivel de volume, texto, etc."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "computer_control",
            "description": "Controle direto do computador: digitar, clicar, atalhos, scroll, mover mouse, screenshots, encontrar elementos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | focus_window | screen_find | screen_click"},
                    "text": {"type": "string", "description": "Texto para digitar ou colar"},
                    "x": {"type": "integer", "description": "Coordenada X"},
                    "y": {"type": "integer", "description": "Coordenada Y"},
                    "keys": {"type": "string", "description": "Combinacao de teclas (ex: ctrl+c)"},
                    "key": {"type": "string", "description": "Tecla unica (ex: enter)"},
                    "direction": {"type": "string", "description": "up | down | left | right"},
                    "amount": {"type": "integer", "description": "Quantidade de scroll (default: 3)"},
                    "seconds": {"type": "number", "description": "Segundos para wait"},
                    "title": {"type": "string", "description": "Titulo da janela para focus_window"},
                    "description": {"type": "string", "description": "Descricao do elemento para screen_find/screen_click"},
                    "path": {"type": "string", "description": "Caminho para salvar screenshot"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_control",
            "description": "Controla a area de trabalho: papel de parede, organizar, limpar, listar, estatisticas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                    "path": {"type": "string", "description": "Caminho da imagem para wallpaper"},
                    "url": {"type": "string", "description": "URL da imagem para wallpaper_url"},
                    "mode": {"type": "string", "description": "by_type ou by_date para organize"},
                    "task": {"type": "string", "description": "Tarefa da area de trabalho em linguagem natural"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_helper",
            "description": "Escreve, edita, explica, executa ou compila arquivos de codigo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "write | edit | explain | run | build | auto"},
                    "description": {"type": "string", "description": "O que o codigo deve fazer ou que mudanca fazer"},
                    "language": {"type": "string", "description": "Linguagem de programacao (default: python)"},
                    "output_path": {"type": "string", "description": "Onde salvar o arquivo"},
                    "file_path": {"type": "string", "description": "Caminho de arquivo existente"},
                    "code": {"type": "string", "description": "Codigo bruto para explain"},
                    "args": {"type": "string", "description": "Argumentos CLI para run/build"},
                    "timeout": {"type": "integer", "description": "Timeout em segundos (default: 30)"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dev_agent",
            "description": "Cria projetos completos multi-arquivo do zero: planeja, escreve arquivos, instala deps, executa e corrige erros.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "O que o projeto deve fazer"},
                    "language": {"type": "string", "description": "Linguagem (default: python)"},
                    "project_name": {"type": "string", "description": "Nome da pasta do projeto"},
                    "timeout": {"type": "integer", "description": "Timeout de execucao em segundos (default: 30)"}
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "game_updater",
            "description": "Ferramenta para Steam/Epic Games: instalar, baixar, atualizar, listar jogos, status de download.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status"},
                    "platform": {"type": "string", "description": "steam | epic | both (default: both)"},
                    "game_name": {"type": "string", "description": "Nome do jogo"},
                    "app_id": {"type": "string", "description": "Steam AppID para install"},
                    "hour": {"type": "integer", "description": "Hora para update agendado 0-23 (default: 3)"},
                    "minute": {"type": "integer", "description": "Minuto para update agendado 0-59 (default: 0)"},
                    "shutdown_when_done": {"type": "boolean", "description": "Desligar PC quando download finalizar"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "flight_finder",
            "description": "Busca passagens de aviao no Google Flights. Use quando o usuario quiser comprar voos, buscar passagens, ver precos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Cidade ou aeroporto de origem (ex: Sao Paulo, GRU)"},
                    "destination": {"type": "string", "description": "Cidade ou aeroporto de destino (ex: Paris, CDG)"},
                    "date": {"type": "string", "description": "Data de saida (ex: 2026-09-15)"},
                    "return_date": {"type": "string", "description": "Data de volta para ida e volta (opcional)"},
                    "passengers": {"type": "integer", "description": "Numero de passageiros (default: 1)"},
                    "cabin": {"type": "string", "description": "Classe: economy | premium | business | first"},
                    "save": {"type": "boolean", "description": "Salvar resultado no Notepad"}
                },
                "required": ["origin", "destination", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "screen_process",
            "description": "Captura a tela ou webcam e analisa. Use quando o usuario perguntar o que esta na tela ou quiser que voce veja algo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "angle": {"type": "string", "description": "screen para capturar display, camera para webcam"},
                    "text": {"type": "string", "description": "Pergunta ou instrucao sobre a imagem"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "weather_report",
            "description": "Retorna o relatorio do tempo para uma cidade.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Nome da cidade"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reminder",
            "description": "Agenda um lembrete para data e hora especificas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
                    "time": {"type": "string", "description": "Hora no formato HH:MM (24h)"},
                    "message": {"type": "string", "description": "Texto do lembrete"}
                },
                "required": ["date", "time", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_status",
            "description": "Retorna metricas do sistema em tempo real: uso de CPU, RAM, GPU, temperatura, uptime e numero de processos.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_monitor",
            "description": "Adiciona, remove ou lista topicos de monitoramento em background.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "add | remove | list"},
                    "topic": {"type": "string", "description": "Topico para monitorar ou parar de monitorar"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "whatsapp_send",
            "description": "Envia uma mensagem de texto via WhatsApp ou Telegram.",
            "parameters": {
                "type": "object",
                "properties": {
                    "receiver": {"type": "string", "description": "Nome do destinatario"},
                    "message_text": {"type": "string", "description": "Texto da mensagem"},
                    "platform": {"type": "string", "description": "Plataforma: WhatsApp, Telegram"}
                },
                "required": ["receiver", "message_text", "platform"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_processor",
            "description": "Processa arquivos: imagens, PDFs, Word, CSV, JSON, codigo, audio, video, archives.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Caminho completo do arquivo"},
                    "action": {"type": "string", "description": "describe | ocr | summarize | extract_text | analyze | explain | review | fix | run | transcribe | info"},
                    "instruction": {"type": "string", "description": "Instrucao livre adicional"},
                    "format": {"type": "string", "description": "Formato de destino para conversao"},
                    "save": {"type": "boolean", "description": "Salvar resultado em arquivo"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calorie_counter",
            "description": "Analisa comida pela WEBCAM e reporta calorias e valores nutricionais (carboidratos, acucar, fibra, proteina, gordura). Use quando o usuario perguntar sobre calorias de comida que esta segurando ou mostrando.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Pedido exato do usuario, verbatim, no idioma dele"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pushup_counter",
            "description": "Conta flexoes ao vivo pela WEBCAM. Use quando o usuario quiser fazer flexoes e quiser que sejam contadas. A sessao pode durar alguns minutos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Pedido exato do usuario, verbatim, no idioma dele"},
                    "target": {"type": "number", "description": "Meta de repeticoes se o usuario informou uma (ex: 20)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "upload_video",
            "description": "Faz upload de um video da Area de Trabalho para o TikTok com automacao completa do navegador. Use quando o usuario pedir para postar/enviar video no TikTok.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Ideia de legenda/caption do usuario, verbatim, no idioma dele"}
                },
                "required": ["description"]
            }
        }
    },
]

# â”€â”€ Toolset Integration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_tools_by_toolset(toolset_names: list[str] | None = None) -> list[dict]:
    """Filter TOOLS by one or more toolset names.

    Args:
        toolset_names: List of toolset names (e.g. ``["developer"]``).
                       If None or empty, returns ALL tools.

    Returns:
        Filtered list of OpenAI function definitions.
    """
    if not toolset_names:
        return list(TOOLS)

    allowed = resolve_multiple_toolsets(toolset_names)
    return filter_function_defs(TOOLS, allowed)


def get_tools_by_name(tool_names: list[str]) -> list[dict]:
    """Filter TOOLS to only include specific named tools.

    Args:
        tool_names: List of exact tool function names.

    Returns:
        Filtered list matching only the requested tools.
    """
    allowed = set(tool_names)
    return [fd for fd in TOOLS if fd.get("function", {}).get("name") in allowed]


def get_all_tool_names() -> list[str]:
    """Return the name of every registered tool."""
    return [fd["function"]["name"] for fd in TOOLS if "function" in fd]


def build_tool_index() -> dict[str, str]:
    """Build a nameâ†’description index for tool_search."""
    return {
        fd["function"]["name"]: fd["function"]["description"]
        for fd in TOOLS
        if "function" in fd and "name" in fd["function"]
    }
