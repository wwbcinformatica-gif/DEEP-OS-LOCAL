# CHARON TOOLS - Sistema de 3 Níveis

## Como Funciona
O Charon tem **3 níveis de tools** configuráveis:

| Nível | Quantidade | Descrição |
|-------|------------|-----------|
| **Estabilidade Mínima** | 19 tools | Básico, mais estável |
| **Equilíbrio** | 22 tools | Recomendado (BASIC + escrita/edição web) |
| **Completa** | 25 tools | Todas as ferramentas |

---

## Tools por Nível

### BASIC (19 tools) - Estabilidade Mínima

| # | Tool | Descrição |
|---|------|-----------|
| 1 | open_app | Abrir aplicativos |
| 2 | web_search | Busca na web |
| 3 | download_image | Baixar imagem de URL |
| 4 | system_status | Métricas CPU/RAM/GPU |
| 5 | weather_report | Relatório do tempo |
| 6 | send_message | Enviar msg WhatsApp/Telegram |
| 7 | reminder | Lembretes agendados |
| 8 | youtube_video | Buscar/abrir vídeos YouTube |
| 9 | screen_process | Capturar e processar tela |
| 10 | computer_settings | Configurações do sistema |
| 11 | browser_control | Controlar navegador |
| 12 | file_controller | Gerenciar arquivos |
| 13 | desktop_control | Área de trabalho |
| 14 | code_helper | Escrever/editar código |
| 15 | dev_agent | Criar projetos completos |
| 16 | computer_control | Digitar, clicar, atalhos |
| 17 | file_processor | Processar PDFs, imagens |
| 18 | bash | Executar comandos terminal |
| 19 | read_file | Ler conteúdo de arquivo |

### MEDIUM (22 tools) - Equilíbrio (Recomendado)

Todas as BASIC +:
| # | Tool | Descrição |
|---|------|-----------|
| 20 | write_file | Criar/sobrescrever arquivo |
| 21 | file_edit | Editar arquivo específico |
| 22 | web_fetch | Buscar conteúdo de URL |

### FULL (25 tools) - Completa

Todas as MEDIUM +:
| # | Tool | Descrição |
|---|------|-----------|
| 23 | save_document | Salvar documento organizado |
| 24 | memory_save | Salvar na memória |
| 25 | memory_recall | Ler da memória |

---

## Como Alterar

1. Acesse **Config > Agentes > Charon Tools**
2. Selecione o nível desejado
3. Clique em **Salvar configurações**
4. Reinicie o backend para aplicar

---

## Estabilidade Gemini Live

A sessão Gemini Live usa `context_window_compression` com `sliding_window` para sessões duradouras.

**Se o Charon parar de responder:**
1. Verifique se a API Key do Gemini está válida
2. Reinicie o backend
3. Aguarde reconexão automática (~15 segundos)
