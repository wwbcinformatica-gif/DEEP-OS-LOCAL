"""
DEEP-AUREA — WebSocket de voz com Gemini Live API.
"""
import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("voicews")

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import is_headless

router = APIRouter()

LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

# Tempo de espera, apos o turn_complete, para os ultimos chunks de audio do
# Gemini chegarem antes de fechar o turno. Curto demais corta a ultima
# palavra; longo demais atrasa o retorno ao estado "ouvindo".
TURN_TAIL_GRACE_S = 0.9

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

GEMINI_VOICES = {
    "charon": "Charon", "puck": "Puck", "kore": "Kore",
    "fenrir": "Fenrir", "leda": "Leda", "orus": "Orus",
    "aoede": "Aoede", "zephyr": "Zephyr",
}


def _resolve_voice(voice: str) -> str:
    """Resolve nome da voz (case-insensitive)."""
    return GEMINI_VOICES.get(voice.lower(), voice)


def _get_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if key and key != "cole_sua_chave_aqui":
        return key
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if cfg_path.exists():
            k = json.loads(cfg_path.read_text(encoding="utf-8")).get("gemini_api_key", "")
            if k:
                return k
    except Exception:
        pass
    try:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                    v = line.split("=", 1)[1].strip()
                    if v:
                        os.environ["GEMINI_API_KEY"] = v
                        return v
    except Exception:
        pass
    return ""


# ── Imports das Actions ───────────────────────────────────────────────────────
_ACTIONS_OK = False
try:
    from actions.open_app import open_app
    from actions.web_search import web_search as web_search_action
    from actions.weather_report import weather_action
    from actions.send_message import send_message
    from actions.reminder import reminder
    from actions.youtube_video import youtube_video
    from actions.screen_processor import _capture_camera, _capture_screen
    from actions.computer_settings import computer_settings
    from actions.browser_control import browser_control
    from actions.file_controller import file_controller
    from actions.desktop import desktop_control
    from actions.code_helper import code_helper
    from actions.download_image import download_image
    from actions.dev_agent import dev_agent
    from actions.computer_control import computer_control
    from actions.game_updater import game_updater
    from actions.flight_finder import flight_finder
    from actions.file_processor import file_processor
    from actions.system_monitor import get_system_status
    from actions.background_monitor import add_monitor, remove_monitor, list_monitors
    _ACTIONS_OK = True
    logger.info("Todas as 20 actions importadas com sucesso")
except ImportError as e:
    logger.warning(f"nem todas as actions foram importadas: {e}")

# ── Imports das Tools do DEEP-AUREA ──────────────────────────────────────────
_TOOLS_OK = False
try:
    from tools.system_tools import tool_read, tool_write
    from tools.file_edit import tool_file_edit
    from tools.web_fetch import tool_web_fetch
    from tools.explorer import resolve_path
    _TOOLS_OK = True
    print("[VoiceWS] Tools do DEEP-AUREA importadas com sucesso")
except ImportError as e:
    print(f"[VoiceWS] Aviso: tools do DEEP-AUREA nao importadas: {e}")

try:
    from memory.config_manager import get_brief_enabled
    _BRIEF_OK = True
except ImportError:
    _BRIEF_OK = False


# ── TOOL DECLARATIONS (3 niveis) ──────────────────────────────────────────────

# BASIC: 18 tools - Estabilidade minima
BASIC_TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Abre qualquer aplicativo no computador. Use quando o usuario pedir para abrir, iniciar ou lancar qualquer app, site ou programa.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {"type": "STRING", "description": "Nome do aplicativo (ex: 'WhatsApp', 'Chrome', 'Spotify')"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Busca na web. Use para qualquer pergunta sobre fatos atuais, eventos, precos ou topicos. Modos: search (padrao), news (noticias), research (profundo), price (preco), compare (comparacao).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Consulta de busca"},
                "mode":   {"type": "STRING", "description": "search | news | research | price | compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Itens para comparar (modo compare)"},
                "aspect": {"type": "STRING", "description": "Aspecto da comparacao: price | specs | reviews | features"},
            },
            "required": ["query"]
        }
    },
    {
        "name": "system_status",
        "description": "Retorna metricas do sistema em tempo real: uso de CPU, RAM, GPU, temperatura, uptime e numero de processos.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "weather_report",
        "description": "Retorna o relatorio do tempo para uma cidade.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "Nome da cidade"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Envia uma mensagem de texto via WhatsApp, Telegram ou outra plataforma.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Nome do destinatario"},
                "message_text": {"type": "STRING", "description": "Texto da mensagem"},
                "platform":     {"type": "STRING", "description": "Plataforma: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text"]
        }
    },
    {
        "name": "reminder",
        "description": "Cria lembretes. Use para agendar tarefas, alarmes ou avisos futuros.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text":    {"type": "STRING", "description": "Texto do lembrete"},
                "time":    {"type": "STRING", "description": "Hora para o lembrete (ex: '14:30', 'em 2 horas')"},
                "date":    {"type": "STRING", "description": "Data (ex: 'amanha', '2026-08-28')"},
                "repeat":  {"type": "STRING", "description": "Repetir: daily, weekly, monthly"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "list_reminders",
        "description": (
            "Lista os lembretes do usuario e pode gerar um documento para download. "
            "Use quando o usuario perguntar quais lembretes tem, ou pedir um resumo/lista deles."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "document": {
                    "type": "STRING",
                    "description": (
                        "Use 'sim' para gerar um documento com o resumo e entregar o link de download. "
                        "Use 'nao' (ou omita) para apenas falar o resumo em voz."
                    )
                },
                "include_fired": {
                    "type": "STRING",
                    "description": "Use 'sim' para incluir tambem os lembretes ja disparados ou cancelados."
                }
            }
        }
    },
    {
        "name": "youtube_video",
        "description": "Busca e abre videos do YouTube. Use quando o usuario quiser assistir, pesquisar ou ouvir musicas no YouTube.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Busca no YouTube"},
                "action": {"type": "STRING", "description": "search (padrao) ou open (abrir video especifico)"},
                "video_id": {"type": "STRING", "description": "ID do video para open"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "screen_process",
        "description": "Captura e processa tela ou camera. Use para ver o que esta na tela, tirar screenshot, ou analisar camera.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source": {"type": "STRING", "description": "screen (tela) ou camera"},
                "action": {"type": "STRING", "description": "capture (captura), analyze (analisa), record (grava)"}
            },
            "required": ["source"]
        }
    },
    {
        "name": "computer_settings",
        "description": "Configuracoes do sistema: volume, brilho, wifi, bluetooth, bateria, modo aviao, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "Acao a executar"},
                "description": {"type": "STRING", "description": "Descricao em linguagem natural"},
                "value":       {"type": "STRING", "description": "Valor opcional: nivel de volume, texto, etc."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "browser_control",
        "description": "Controla navegadores web: abrir sites, buscar, clicar, preencher, scroll, screenshot, navegacao.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | screenshot | back | forward | reload | close"},
                "browser":   {"type": "STRING", "description": "chrome | edge | firefox | opera | brave"},
                "url":       {"type": "STRING", "description": "URL para go_to"},
                "query":     {"type": "STRING", "description": "Busca para search"},
                "selector":  {"type": "STRING", "description": "CSS selector para click/type"},
                "text":      {"type": "STRING", "description": "Texto para digitar ou clicar"},
                "direction": {"type": "STRING", "description": "up | down para scroll"},
                "amount":    {"type": "INTEGER", "description": "Quantidade de scroll (default: 500)"},
                "key":       {"type": "STRING", "description": "Tecla para press (ex: Enter, F5)"},
                "path":      {"type": "STRING", "description": "Caminho para salvar screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Gerencia arquivos e pastas: listar, criar, deletar, mover, copiar, renomear, ler, escrever, buscar, abrir arquivos (imagens, documentos, pdf, html, txt, xml, doc, etc) com o aplicativo padrao, espaco em disco.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | info | open"},
                "path":        {"type": "STRING", "description": "Caminho do arquivo/pasta ou atalho: desktop, downloads, documents, home. Para abrir use o caminho completo ou atalho + name"},
                "destination": {"type": "STRING", "description": "Destino para move/copy"},
                "new_name":    {"type": "STRING", "description": "Novo nome para rename"},
                "content":     {"type": "STRING", "description": "Conteudo para create_file/write"},
                "name":        {"type": "STRING", "description": "Nome do arquivo para buscar ou abrir"},
                "extension":   {"type": "STRING", "description": "Extensao para buscar (ex: .pdf)"},
                "count":       {"type": "INTEGER", "description": "Numero de resultados para largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controla a area de trabalho: papel de parede, organizar, limpar, listar, estatisticas.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Caminho da imagem para wallpaper"},
                "url":    {"type": "STRING", "description": "URL da imagem para wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type ou by_date para organize"},
                "task":   {"type": "STRING", "description": "Tarefa da area de trabalho em linguagem natural"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Escreve, edita, explica, executa ou compila arquivos de codigo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto"},
                "description": {"type": "STRING", "description": "O que o codigo deve fazer ou que mudanca fazer"},
                "language":    {"type": "STRING", "description": "Linguagem de programacao (default: python)"},
                "output_path": {"type": "STRING", "description": "Onde salvar o arquivo"},
                "file_path":   {"type": "STRING", "description": "Caminho de arquivo existente"},
                "code":        {"type": "STRING", "description": "Codigo bruto para explain"},
                "args":        {"type": "STRING", "description": "Argumentos CLI para run/build"},
                "timeout":     {"type": "INTEGER", "description": "Timeout em segundos (default: 30)"},
            },
            "required": ["action", "description"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Cria projetos completos multi-arquivo do zero: planeja, escreve arquivos, instala deps, executa e corrige erros.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "O que o projeto deve fazer"},
                "language":     {"type": "STRING", "description": "Linguagem (default: python)"},
                "project_name": {"type": "STRING", "description": "Nome da pasta do projeto"},
                "timeout":      {"type": "INTEGER", "description": "Timeout de execucao em segundos (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "computer_control",
        "description": "Controle direto do computador: digitar, clicar, atalhos, scroll, mover mouse, screenshots, encontrar elementos.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | focus_window | screen_find | screen_click"},
                "text":        {"type": "STRING", "description": "Texto para digitar ou colar"},
                "x":           {"type": "INTEGER", "description": "Coordenada X"},
                "y":           {"type": "INTEGER", "description": "Coordenada Y"},
                "keys":        {"type": "STRING", "description": "Combinacao de teclas (ex: ctrl+c)"},
                "key":         {"type": "STRING", "description": "Tecla unica (ex: enter)"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Quantidade de scroll (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Segundos para wait"},
                "title":       {"type": "STRING",  "description": "Titulo da janela para focus_window"},
                "description": {"type": "STRING",  "description": "Descricao do elemento para screen_find/screen_click"},
                "path":        {"type": "STRING",  "description": "Caminho para salvar screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_processor",
        "description": "Processa arquivos: imagens, PDFs, Word, CSV, JSON, codigo, audio, video, archives. Use quando o usuario quiser processar um arquivo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path":   {"type": "STRING", "description": "Caminho completo do arquivo"},
                "action":      {"type": "STRING", "description": "Acao: describe | ocr | summarize | extract_text | analyze | explain | review | fix | run | transcribe | info"},
                "instruction": {"type": "STRING", "description": "Instrucao livre adicional"},
                "format":      {"type": "STRING", "description": "Formato de destino para conversao"},
                "save":        {"type": "BOOLEAN", "description": "Salvar resultado em arquivo"},
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "bash",
        "description": "Executa comandos no terminal. Use para rodar qualquer comando do sistema.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "Comando para executar"},
                "workdir": {"type": "STRING", "description": "Diretorio de trabalho (opcional)"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "read_file",
        "description": "Le o conteudo de um arquivo ou lista uma pasta.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "Caminho do arquivo ou pasta"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "download_image",
        "description": "Baixa uma imagem de uma URL e salva localmente. Retorna o caminho do arquivo. Use quando o usuario quiser baixar, salvar ou copiar uma imagem da internet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url":      {"type": "STRING", "description": "URL da imagem para baixar"},
                "save_path":{"type": "STRING", "description": "Caminho para salvar (pasta ou arquivo). Vazio = pasta padrao downloads"},
                "filename": {"type": "STRING", "description": "Nome do arquivo (sem extensao). Vazio = nome automatico"}
            },
            "required": ["url"]
        }
    },
]

# MEDIUM: 18 tools - Equilibrio (recomendado)
MEDIUM_TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Abre qualquer aplicativo no computador. Use quando o usuario pedir para abrir, iniciar ou lancar qualquer app, site ou programa.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {"type": "STRING", "description": "Nome do aplicativo (ex: 'WhatsApp', 'Chrome', 'Spotify')"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Busca na web. Use para qualquer pergunta sobre fatos atuais, eventos, precos ou topicos. Modos: search (padrao), news (noticias), research (profundo), price (preco), compare (comparacao).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Consulta de busca"},
                "mode":   {"type": "STRING", "description": "search | news | research | price | compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Itens para comparar (modo compare)"},
                "aspect": {"type": "STRING", "description": "Aspecto da comparacao: price | specs | reviews | features"},
            },
            "required": ["query"]
        }
    },
    {
        "name": "system_status",
        "description": "Retorna metricas do sistema em tempo real: uso de CPU, RAM, GPU, temperatura, uptime e numero de processos.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "weather_report",
        "description": "Retorna o relatorio do tempo para uma cidade.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "Nome da cidade"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Envia uma mensagem de texto via WhatsApp, Telegram ou outra plataforma.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Nome do destinatario"},
                "message_text": {"type": "STRING", "description": "Texto da mensagem"},
                "platform":     {"type": "STRING", "description": "Plataforma: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text"]
        }
    },
    {
        "name": "reminder",
        "description": "Cria lembretes. Use para agendar tarefas, alarmes ou avisos futuros.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text":    {"type": "STRING", "description": "Texto do lembrete"},
                "time":    {"type": "STRING", "description": "Hora para o lembrete (ex: '14:30', 'em 2 horas')"},
                "date":    {"type": "STRING", "description": "Data (ex: 'amanha', '2026-08-28')"},
                "repeat":  {"type": "STRING", "description": "Repetir: daily, weekly, monthly"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "list_reminders",
        "description": (
            "Lista os lembretes do usuario e pode gerar um documento para download. "
            "Use quando o usuario perguntar quais lembretes tem, ou pedir um resumo/lista deles."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "document": {
                    "type": "STRING",
                    "description": (
                        "Use 'sim' para gerar um documento com o resumo e entregar o link de download. "
                        "Use 'nao' (ou omita) para apenas falar o resumo em voz."
                    )
                },
                "include_fired": {
                    "type": "STRING",
                    "description": "Use 'sim' para incluir tambem os lembretes ja disparados ou cancelados."
                }
            }
        }
    },
    {
        "name": "youtube_video",
        "description": "Busca e abre videos do YouTube. Use quando o usuario quiser assistir, pesquisar ou ouvir musicas no YouTube.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Busca no YouTube"},
                "action": {"type": "STRING", "description": "search (padrao) ou open (abrir video especifico)"},
                "video_id": {"type": "STRING", "description": "ID do video para open"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "screen_process",
        "description": "Captura e processa tela ou camera. Use para ver o que esta na tela, tirar screenshot, ou analisar camera.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source": {"type": "STRING", "description": "screen (tela) ou camera"},
                "action": {"type": "STRING", "description": "capture (captura), analyze (analisa), record (grava)"}
            },
            "required": ["source"]
        }
    },
    {
        "name": "computer_settings",
        "description": "Configuracoes do sistema: volume, brilho, wifi, bluetooth, bateria, modo aviao, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "Acao a executar"},
                "description": {"type": "STRING", "description": "Descricao em linguagem natural"},
                "value":       {"type": "STRING", "description": "Valor opcional: nivel de volume, texto, etc."}
            },
            "required": ["action"]
        }
    },
    {
        "name": "browser_control",
        "description": "Controla navegadores web: abrir sites, buscar, clicar, preencher, scroll, screenshot, navegacao.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | screenshot | back | forward | reload | close"},
                "browser":   {"type": "STRING", "description": "chrome | edge | firefox | opera | brave"},
                "url":       {"type": "STRING", "description": "URL para go_to"},
                "query":     {"type": "STRING", "description": "Busca para search"},
                "selector":  {"type": "STRING", "description": "CSS selector para click/type"},
                "text":      {"type": "STRING", "description": "Texto para digitar ou clicar"},
                "direction": {"type": "STRING", "description": "up | down para scroll"},
                "amount":    {"type": "INTEGER", "description": "Quantidade de scroll (default: 500)"},
                "key":       {"type": "STRING", "description": "Tecla para press (ex: Enter, F5)"},
                "path":      {"type": "STRING", "description": "Caminho para salvar screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Gerencia arquivos e pastas: listar, criar, deletar, mover, copiar, renomear, ler, escrever, buscar, abrir arquivos (imagens, documentos, pdf, html, txt, xml, doc, etc) com o aplicativo padrao, espaco em disco.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | info | open"},
                "path":        {"type": "STRING", "description": "Caminho do arquivo/pasta ou atalho: desktop, downloads, documents, home. Para abrir use o caminho completo ou atalho + name"},
                "destination": {"type": "STRING", "description": "Destino para move/copy"},
                "new_name":    {"type": "STRING", "description": "Novo nome para rename"},
                "content":     {"type": "STRING", "description": "Conteudo para create_file/write"},
                "name":        {"type": "STRING", "description": "Nome do arquivo para buscar ou abrir"},
                "extension":   {"type": "STRING", "description": "Extensao para buscar (ex: .pdf)"},
                "count":       {"type": "INTEGER", "description": "Numero de resultados para largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controla a area de trabalho: papel de parede, organizar, limpar, listar, estatisticas.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Caminho da imagem para wallpaper"},
                "url":    {"type": "STRING", "description": "URL da imagem para wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type ou by_date para organize"},
                "task":   {"type": "STRING", "description": "Tarefa da area de trabalho em linguagem natural"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Escreve, edita, explica, executa ou compila arquivos de codigo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto"},
                "description": {"type": "STRING", "description": "O que o codigo deve fazer ou que mudanca fazer"},
                "language":    {"type": "STRING", "description": "Linguagem de programacao (default: python)"},
                "output_path": {"type": "STRING", "description": "Onde salvar o arquivo"},
                "file_path":   {"type": "STRING", "description": "Caminho de arquivo existente"},
                "code":        {"type": "STRING", "description": "Codigo bruto para explain"},
                "args":        {"type": "STRING", "description": "Argumentos CLI para run/build"},
                "timeout":     {"type": "INTEGER", "description": "Timeout em segundos (default: 30)"},
            },
            "required": ["action", "description"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Cria projetos completos multi-arquivo do zero: planeja, escreve arquivos, instala deps, executa e corrige erros.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "O que o projeto deve fazer"},
                "language":     {"type": "STRING", "description": "Linguagem (default: python)"},
                "project_name": {"type": "STRING", "description": "Nome da pasta do projeto"},
                "timeout":      {"type": "INTEGER", "description": "Timeout de execucao em segundos (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "computer_control",
        "description": "Controle direto do computador: digitar, clicar, atalhos, scroll, mover mouse, screenshots, encontrar elementos.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | focus_window | screen_find | screen_click"},
                "text":        {"type": "STRING", "description": "Texto para digitar ou colar"},
                "x":           {"type": "INTEGER", "description": "Coordenada X"},
                "y":           {"type": "INTEGER", "description": "Coordenada Y"},
                "keys":        {"type": "STRING", "description": "Combinacao de teclas (ex: ctrl+c)"},
                "key":         {"type": "STRING", "description": "Tecla unica (ex: enter)"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Quantidade de scroll (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Segundos para wait"},
                "title":       {"type": "STRING",  "description": "Titulo da janela para focus_window"},
                "description": {"type": "STRING",  "description": "Descricao do elemento para screen_find/screen_click"},
                "path":        {"type": "STRING",  "description": "Caminho para salvar screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_processor",
        "description": "Processa arquivos: imagens, PDFs, Word, CSV, JSON, codigo, audio, video, archives. Use quando o usuario quiser processar um arquivo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path":   {"type": "STRING", "description": "Caminho completo do arquivo"},
                "action":      {"type": "STRING", "description": "Acao: describe | ocr | summarize | extract_text | analyze | explain | review | fix | run | transcribe | info"},
                "instruction": {"type": "STRING", "description": "Instrucao livre adicional"},
                "format":      {"type": "STRING", "description": "Formato de destino para conversao"},
                "save":        {"type": "BOOLEAN", "description": "Salvar resultado em arquivo"},
            },
             "required": ["file_path"]
        }
    },
    {
        "name": "bash",
        "description": "Executa comandos no terminal. Use para rodar qualquer comando do sistema.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "Comando para executar"},
                "workdir": {"type": "STRING", "description": "Diretorio de trabalho (opcional)"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "read_file",
        "description": "Le o conteudo de um arquivo ou lista uma pasta.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "Caminho do arquivo ou pasta"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "download_image",
        "description": "Baixa uma imagem de uma URL e salva localmente. Retorna o caminho do arquivo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url":      {"type": "STRING", "description": "URL da imagem para baixar"},
                "save_path":{"type": "STRING", "description": "Caminho para salvar"},
                "filename": {"type": "STRING", "description": "Nome do arquivo"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "write_file",
        "description": "Cria um arquivo e gera um link de download para o aparelho do usuario.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "Caminho do arquivo"},
                "content": {"type": "STRING", "description": "Conteudo para escrever"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "file_edit",
        "description": "Edita um arquivo fazendo find-and-replace.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "Caminho do arquivo"},
                "old_string": {"type": "STRING", "description": "Texto para encontrar"},
                "new_string": {"type": "STRING", "description": "Texto novo"}
            },
            "required": ["path", "old_string", "new_string"]
        }
    },
    {
        "name": "web_fetch",
        "description": "Busca o conteudo de uma URL como texto.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "URL para buscar"}
            },
            "required": ["url"]
        }
    },
]

# FULL: 25 tools - Completo (todas as anteriores + extras)
# ── TOOLS EXTRAS (ativas quando charon_toolset: full) ────────────────────────
EXTRA_TOOL_DECLARATIONS = [
    {
        "name": "save_document",
        "description": "Salva um documento e gera um link de download. O arquivo fica disponivel no menu Downloads. Formatos: md, txt, html, json.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Titulo do documento"},
                "content": {"type": "STRING", "description": "Conteudo do documento"},
                "path": {"type": "STRING", "description": "Caminho completo (opcional)"},
                "category": {"type": "STRING", "description": "Categoria: relatorios, notas, codigos"},
                "format": {"type": "STRING", "description": "Formato: md, txt, html, json"}
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "memory_save",
        "description": "Salva informacao na memoria de longo prazo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "namespace": {"type": "STRING", "description": "Categoria: preferences, projects, notes"},
                "key": {"type": "STRING", "description": "Chave unica"},
                "content": {"type": "STRING", "description": "Conteudo para salvar"}
            },
            "required": ["namespace", "key", "content"]
        }
    },
    {
        "name": "memory_recall",
        "description": "Le informacao da memoria de longo prazo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "namespace": {"type": "STRING", "description": "Categoria"},
                "key": {"type": "STRING", "description": "Chave do dado"}
            },
            "required": ["namespace", "key"]
        }
    },
]

_toolset_cache = {"value": None, "mtime": 0.0}


def _get_charon_toolset() -> str:
    """Le config de toolset do config.yaml (com cache)."""
    try:
        cfg_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
        if cfg_path.exists():
            mtime = cfg_path.stat().st_mtime
            if mtime == _toolset_cache["mtime"] and _toolset_cache["value"]:
                return _toolset_cache["value"]
            import yaml
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            value = cfg.get("voice", {}).get("charon_toolset", "basic")
            _toolset_cache["value"] = value
            _toolset_cache["mtime"] = mtime
            return value
    except Exception:
        pass
    return _toolset_cache["value"] or "basic"


# Tools que dependem de interface grafica (mouse/teclado/tela/janela).
# Num VPS headless elas falham ao ser usadas — pyautogui levanta
# `KeyError: 'DISPLAY'` (nao ImportError), e mss nao tem tela para capturar.
# Removidas da lista enviada ao Gemini, para o Charon nao oferecer ao usuario
# algo que so vai dar erro.
_HEADLESS_EXCLUDED = {
    "open_app",            # abre app na area de trabalho
    "browser_control",     # controla o navegador na tela
    "desktop_control",     # controla a area de trabalho
    "computer_control",    # mouse/teclado
    "computer_settings",   # ajustes do SO (volume, janelas)
    "screen_process",      # captura de tela/camera
    "game_updater",        # mexe em instalador grafico
    "send_message",        # pyautogui para colar em apps de mensagem
}


def _filter_headless(tools: list) -> list:
    if not is_headless():
        return tools
    filtered = [t for t in tools if t.get("name") not in _HEADLESS_EXCLUDED]
    removidas = [t.get("name") for t in tools if t.get("name") in _HEADLESS_EXCLUDED and t.get("name")]
    print(f"[VoiceWS] Headless mode: {len(tools)} -> {len(filtered)} tools (removidas: {', '.join(removidas)})")
    return filtered


AVAILABLE_TOOLS_LIST = """
Ferramentas disponiveis:
- web_search: busca na web
- youtube_video: buscar videos no YouTube (retorna link clicavel)
- weather_report: relatorio do tempo
- system_status: status do sistema
- reminder: criar lembretes
- list_reminders: listar lembretes / gerar documento de resumo
- file_controller: gerenciar arquivos
- file_processor: processar PDFs/imagens
- download_image: baixar imagens
- code_helper: ajuda de codigo
- dev_agent: criar projetos
- bash: executar comandos
- read_file: ler arquivos
- background_monitor: monitoramento
"""


def _get_active_tools() -> list:
    """Retorna tools ativas baseado na configuracao."""
    toolset = _get_charon_toolset()
    if toolset == "full":
        tools = MEDIUM_TOOL_DECLARATIONS + EXTRA_TOOL_DECLARATIONS
    elif toolset == "medium":
        tools = MEDIUM_TOOL_DECLARATIONS
    else:
        tools = BASIC_TOOL_DECLARATIONS
    tools = _filter_headless(tools)
    print(f"[VoiceWS] Toolset: {toolset.upper()} ({len(tools)} tools ativas)")
    return tools


# ── System Instruction ────────────────────────────────────────────────────────
_PROJECT_CONTEXT_CACHE: dict = {"mtime": 0.0, "text": ""}


def _load_project_context() -> str:
    """Carrega o CHARON_CONTEXT.md (conhecimento do projeto + desenvolvedor)."""
    try:
        ctx_path = Path(__file__).resolve().parent.parent.parent / "CHARON_CONTEXT.md"
        mtime = ctx_path.stat().st_mtime if ctx_path.exists() else 0.0
        if mtime != _PROJECT_CONTEXT_CACHE["mtime"]:
            _PROJECT_CONTEXT_CACHE["mtime"] = mtime
            _PROJECT_CONTEXT_CACHE["text"] = ctx_path.read_text(encoding="utf-8")
        return _PROJECT_CONTEXT_CACHE["text"]
    except Exception:
        return ""


_identity_cache = {}
_identity_cache_time = 0

# O tenant da conexao fica em core.tenant_identity (ContextVar central),
# compartilhado com as actions do Charon e com as rotas HTTP.


def _tenant_from_token(token: str | None) -> str | None:
    """Extrai o tenant_id (sub) de um JWT, sem levantar excecao."""
    if not token:
        return None
    try:
        from core.auth import AuthManager
        return AuthManager.decode_token(token).get("sub")
    except Exception:
        return None


def _load_identity() -> dict:
    """
    Carrega identity.

    Se houver tenant no contexto da conexao, le do banco (isolado por
    assinante). Caso contrario usa o config.yaml global (com cache de 5s).
    """
    global _identity_cache, _identity_cache_time

    try:
        from core.tenant_identity import get_current_tenant, get_identity
        tenant_id = get_current_tenant()
        if tenant_id:
            return get_identity(tenant_id)
    except Exception:
        pass  # cai para o global abaixo

    import time
    now = time.time()
    if _identity_cache and (now - _identity_cache_time) < 5:
        return _identity_cache
    try:
        import yaml
        config_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        result = data.get("identity", {})
        _identity_cache = result
        _identity_cache_time = now
        return result
    except Exception:
        return {}


def _build_system_instruction(voice_name: str = "Charon", user_tz: str = "America/Sao_Paulo", user_locale: str = "pt-BR", extra_prompt: str = "") -> str:
    project_ctx = _load_project_context()
    context_block = f"\n\n--- CONTEXTO ---\n{project_ctx}" if project_ctx else ""
    toolset = _get_charon_toolset()
    tools = _get_active_tools()
    tool_count = len(tools)
    tool_names = [t.get("name", "") for t in tools]
    
    identity = _load_identity()
    assistant_name = identity.get("assistant_name", "") or voice_name
    user_name = identity.get("user_name", "") or ""
    
    print(f"[VoiceWS] Identity: assistant={assistant_name}, user={user_name or '(vazio)'}, tools={tool_count}")

    headless_mode = is_headless()
    
    from datetime import datetime as _dt, timezone as _tz
    from zoneinfo import ZoneInfo
    try:
        tz = ZoneInfo(user_tz)
        agora = _dt.now(tz)
        hora_local = agora.strftime("%d/%m/%Y %H:%M:%S")
        offset = agora.strftime("%z")
        offset_fmt = f"UTC{offset[:3]}:{offset[3:]}" if offset else ""
        dias = ["segunda-feira", "terca-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sabado", "domingo"]
        dia_semana = dias[agora.weekday()]
        hora_info = f"HORA ATUAL DO USUARIO: {hora_local} ({dia_semana}). Fuso: {user_tz} ({offset_fmt}). "
    except Exception:
        agora = _dt.now()
        hora_local = agora.strftime("%d/%m/%Y %H:%M:%S")
        hora_info = f"HORA APROXIMADA: {hora_local}. "
    
    idioma = "portugues brasileiro"
    if user_locale.startswith("en"):
        idioma = "ingles"
    elif user_locale.startswith("es"):
        idioma = "espanhol"
    
    base = (
        f"IMPORTANTE: Voce se chama {assistant_name}. O usuario se chama {user_name}. "
        f"Detecte o idioma do usuario e responda NELE. "
        f"Se o usuario falar em portugues, responda em portugues. "
        f"Se falar em ingles, responda em ingles. Se falar em espanhol, responda em espanhol. "
        f"Adapte-se ao idioma do usuario. "
        f"{hora_info}"
        f"Esta é a hora LOCAL do usuario. Use SEMPRE esta hora. NUNCA use o comando bash 'date' para hora. "
        f"O servidor esta em UTC mas o usuario esta em {user_tz}. "
        f"Respostas direto e util. Quando o usuario pedir para ler ou explicar um texto longo, leia COMPLETO sem pular nada, mas divida em partes de ate 3 paragrafos cada vez. Quando terminar uma parte, diga 'Continuar?' e espere o usuario confirmar antes de ler a proxima parte. "
        f"SEMPRE termine sua frase completa antes de parar. NUNCA pare no meio de uma palavra ou frase. "
        f"Use tools sempre ({tool_count} tools, {toolset}). "
        f"IMPORTANTE: Para salvar documentos, SEMPRE use a tool save_document. NUNCA diga o caminho do arquivo. "
        f"A tool save_document gera um link de download automatico para o usuario. "
        f"Ao criar documentos, use markdown bem estruturado: headers (#, ##, ###), listas (- ou 1.), **negrito**, *italico*, `codigo`, paragrafos separados por linha vazia. "
        f"Se tool falhar, diga erro. Nao reinicie conversa. Mantenha contexto."
    )
    
    if headless_mode:
        base += (
            "\n\nMODO SERVIDOR (headless): Voce esta rodando em um servidor sem interface grafica. "
            "Nao e possivel abrir aplicativos, navegadores ou controlar desktop. "
            "Se o usuario pedir algo que voce nao pode fazer, explique educadamente "
            "e liste as ferramentas que voce tem disponivel: "
            f"{', '.join(tool_names)}. "
            "Para YouTube, retorne o link clicavel em vez de tentar abrir navegador. "
            "IMPORTANTE: como o usuario nao tem uma tela para voce mostrar coisas, entregue "
            "LISTAS e RESUMOS como documento: use save_document (ou list_reminders com "
            "document='sim') e SEMPRE inclua o link de download na sua resposta, "
            "dizendo 'clique no link para baixar'. NUNCA leia uma URL longa em voz alta — "
            "apenas diga que o link foi enviado."
        )

    if toolset == "full":
        base += " Docs: save_document. Cod: bash/read/write/edit."

    if extra_prompt:
        base += f"\n\n--- INSTRUCOES PERSONALIZADAS ---\n{extra_prompt}"

    return base + context_block


# ── VoiceSession ──────────────────────────────────────────────────────────────
class VoiceSession:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.client = None
        self.session = None
        self._cm = None
        self._running = False
        self._voice = "Charon"
        self._turn_done_event = asyncio.Event()
        self._briefing_sent = False
        self._receive_task: asyncio.Task | None = None
        self._keepalive_task: asyncio.Task | None = None
        self._last_response_time = asyncio.get_event_loop().time()
        self._last_audio_sent_time = 0
        self._reconnecting = False
        self._interrupted = False
        self._audio_buffer: list[bytes] = []
        self._audio_flush_task: asyncio.Task | None = None

        # Contadores de log agregado (ver _handle_response).
        #
        # Motivo: logar CADA chunk de audio enchia o /var/log/syslog do VPS —
        # ~400 mil linhas/dia, chegando a 27 GB e estourando o disco (o deploy
        # falhou com "No space left on device"). Agora so registramos o que e
        # anormal (delay alto, sessao longa), com resumo por turno.
        self._chunks_recebidos = 0
        self._turno_inicio = 0.0
        self._chunks_no_turno = 0
        self._maior_delay_ms = 0.0
        self._ultimo_aviso_delay = 0.0

    async def start(self, voice: str = "Charon", user_tz: str = "America/Sao_Paulo", user_locale: str = "pt-BR", extra_prompt: str = ""):
        if self._running:
            return False

        t_start = asyncio.get_event_loop().time()
        api_key = _get_gemini_key()
        if not api_key or api_key == "cole_sua_chave_aqui":
            await self.ws.send_json({"type": "error", "message": "GEMINI_API_KEY nao configurada"})
            return False

        self._voice = _resolve_voice(voice)
        await self.ws.send_json({"type": "status", "message": "Conectando ao Gemini..."})

        sys_instr = _build_system_instruction(self._voice, user_tz=user_tz, user_locale=user_locale, extra_prompt=extra_prompt)
        t_sys = (asyncio.get_event_loop().time() - t_start) * 1000
        print(f"[VoiceWS] System instruction pronta em {t_sys:.0f}ms ({len(sys_instr)} chars)")

        try:
            self.client = genai.Client(api_key=api_key)
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                output_audio_transcription={},
                input_audio_transcription={},
                system_instruction=sys_instr,
                tools=[types.Tool(function_declarations=_get_active_tools())],
                speech_config=types.SpeechConfig(
                    language_code="pt-BR",
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self._voice)
                    )
                ),
            )
            active_tools = _get_active_tools()
            print(f"[VoiceWS] Conectando ao Gemini Live com {len(active_tools)} ferramentas...")
            self._cm = self.client.aio.live.connect(model=LIVE_MODEL, config=config)
            self.session = await asyncio.wait_for(self._cm.__aenter__(), timeout=15)
            t_conn = (asyncio.get_event_loop().time() - t_start) * 1000
            self._running = True
            self._last_response_time = asyncio.get_event_loop().time()
            print(f"[VoiceWS] Conectado em {t_conn:.0f}ms! Voz: {self._voice} | Actions OK: {_ACTIONS_OK}")

            self._receive_task = asyncio.create_task(self._receive_loop())
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            # Envia greeting apos 1s
            if not self._briefing_sent:
                self._briefing_sent = True
                asyncio.create_task(self._send_startup_briefing())

            await self.ws.send_json({
                "type": "connected",
                "voice": self._voice,
                "preset": voice,
                "tools": len(active_tools),
            })
            return True
        except asyncio.TimeoutError:
            print(f"[VoiceWS] TIMEOUT ao conectar ao Gemini (15s)")
            await self.ws.send_json({"type": "error", "message": "Timeout: Gemini nao respondeu em 15s. Verifique a API key."})
            return False
        except Exception as e:
            print(f"[VoiceWS] ERRO ao conectar: {e}")
            traceback.print_exc()
            await self.ws.send_json({"type": "error", "message": str(e)})
            return False

    async def send_text_chunked(self, text: str):
        MAX_CHUNK = 2000
        if len(text) <= MAX_CHUNK:
            await self.session.send_client_content(
                turns={"parts": [{"text": text}]}, turn_complete=True
            )
            return
        paragraphs = text.split("\n\n")
        chunks = []
        current = ''
        for para in paragraphs:
            if len(current) + len(para) + 2 > MAX_CHUNK:
                if current:
                    chunks.append(current)
                current = para
            else:
                current = current + "\n\n" + para if current else para
        if current:
            chunks.append(current)
        for i, chunk in enumerate(chunks):
            if not self._running:
                break
            await self.session.send_client_content(
                turns={"parts": [{"text": chunk}]},
                turn_complete=(i == len(chunks) - 1)
            )
            if i < len(chunks) - 1:
                await asyncio.sleep(0.2)

    async def send_audio(self, audio_data: bytes):
        if not self.session or not self._running:
            print("[VoiceWS] send_audio: sessao nao esta pronta")
            return
        try:
            t0 = asyncio.get_event_loop().time()
            await self.session.send_realtime_input(
                media={"data": audio_data, "mime_type": "audio/pcm;rate=16000"}
            )
            elapsed = (asyncio.get_event_loop().time() - t0) * 1000
            if elapsed > 200:
                print(f"[VoiceWS] send_audio lento: {elapsed:.0f}ms ({len(audio_data)} bytes)")
            self._last_audio_sent_time = asyncio.get_event_loop().time()
            self._interrupted = False
        except Exception as e:
            print(f"[VoiceWS] Erro ao enviar audio: {e}")
            if "closed" in str(e).lower() or "disconnect" in str(e).lower():
                print("[VoiceWS] Sessao Gemini parece morta. Tentando reconexao...")
                try:
                    await self.ws.send_json({"type": "error", "message": "Sessao Gemini encerrada. Reconectando..."})
                except Exception:
                    pass
                asyncio.create_task(self._reconnect())

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})
        t0 = asyncio.get_event_loop().time()
        print(f"[VoiceWS] Tool call: {name} {args}")

        # Notifica frontend que esta processando
        try:
            await self.ws.send_json({"type": "transcript", "speaker": "Charon", "text": f"Processando {name}..."})
        except Exception:
            pass

        loop = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=None))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=None))
                result = r or "Done."

            elif name == "system_status":
                r = await loop.run_in_executor(None, get_system_status)
                result = str(r)

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=None))
                result = r or "Weather delivered."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=None, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=None))
                result = r or "Reminder set."

            elif name == "list_reminders":
                # Lista os lembretes do tenant. Com document='sim', gera um
                # documento em downloads/ e devolve o link (mesmo caminho dos
                # resumos que ja funcionam na interface sem pagina propria).
                def _list_reminders_sync():
                    try:
                        from core.reminder_doc import build_spoken_summary, save_summary_document
                        from core.reminders import list_reminders as _list
                        from core.tenant_identity import get_current_tenant

                        incluir_disparados = str(args.get("include_fired", "")).strip().lower() in ("sim", "true", "1", "yes")
                        quer_doc = str(args.get("document", "")).strip().lower() in ("sim", "true", "1", "yes")

                        meus = _list(get_current_tenant(), include_fired=incluir_disparados)

                        if quer_doc:
                            doc = save_summary_document(meus, titulo="Meus Lembretes")
                            if doc:
                                return (
                                    f"{build_spoken_summary(meus)}\n\n"
                                    f"Documento gerado: {doc['filename']}\n\n"
                                    f"📥 **Baixar:** [Clique aqui para baixar {doc['filename']}]({doc['url']})"
                                )
                            return build_spoken_summary(meus) + "\n\n(Nao consegui gerar o documento, mas a lista acima esta completa.)"

                        return build_spoken_summary(meus)
                    except Exception as e:
                        return f"Nao consegui listar os lembretes: {e}"

                result = await loop.run_in_executor(None, _list_reminders_sync)

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=None))
                result = r or "Done."

            elif name == "screen_process":
                angle = args.get("angle", "screen").lower()
                if angle == "camera":
                    img_b, mime_t = await loop.run_in_executor(None, _capture_camera)
                    result = f"Camera captured: {len(img_b)} bytes. Image sent for analysis."
                else:
                    img_b, mime_t = await loop.run_in_executor(None, _capture_screen)
                    result = f"Screen captured: {len(img_b)} bytes. Image sent for analysis."

            elif name == "close_camera":
                result = "Camera closed."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=None))
                result = r or "Done."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=None))
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=None))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=None))
                result = r or "Done."

            elif name == "code_helper":
                # code_helper precisa de file_path ou code
                if not args.get("file_path") and not args.get("code"):
                    result = "Para usar code_helper, forneça: file_path (caminho do arquivo) OU code (codigo para executar). Exemplo: code_helper action='run' file_path='C:\\teste.py'"
                else:
                    r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=None, speak=None))
                    result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=None, speak=None))
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=None))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=None, speak=None))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=None))
                result = r or "Done."

            elif name == "manage_monitor":
                action = args.get("action", "").lower().strip()
                topic = args.get("topic", "").strip()
                if action == "add" and topic:
                    result = await asyncio.to_thread(add_monitor, topic)
                elif action == "remove" and topic:
                    result = await asyncio.to_thread(remove_monitor, topic)
                elif action == "list":
                    topics = await asyncio.to_thread(list_monitors)
                    result = ("Monitoring: " + ", ".join(topics)) if topics else "No topics monitored."
                else:
                    result = "Specify action (add/remove/list) and a topic."

            elif name == "file_processor":
                r = await loop.run_in_executor(None, lambda: file_processor(parameters=args, player=None, speak=None))
                result = r or "Done."

            elif name == "download_image":
                url = args.get("url", "")
                save_path = args.get("save_path", "")
                filename = args.get("filename", "")
                r = await loop.run_in_executor(None, lambda: download_image(url=url, save_path=save_path, filename=filename))
                result = r or "Done."

            # ── NOVAS FERRAMENTAS (DEEP-AUREA Tools) ─────────────────────────────
            elif name == "bash":
                import subprocess
                cmd = args.get("command", "")
                workdir = args.get("workdir", None)
                # Notifica frontend que esta processando
                try:
                    await self.ws.send_json({"type": "transcript", "speaker": "Charon", "text": "Executando comando..."})
                except Exception:
                    pass
                try:
                    r = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=30,
                        cwd=workdir
                    )
                    result = r.stdout[:2000] if r.returncode == 0 else f"Erro: {r.stderr[:2000]}"
                except subprocess.TimeoutExpired:
                    result = "Timeout: comando demorou mais de 30 segundos"
                except Exception as e:
                    result = f"Erro ao executar comando: {e}"

            elif name == "read_file":
                from tools.system_tools import tool_read as _tool_read
                path = args.get("path", "")
                r = await _tool_read(path)
                if "error" in r:
                    result = r["error"]
                elif r.get("type") == "directory":
                    items = [i["name"] for i in r.get("items", [])[:50]]
                    result = f"Pasta: {r.get('name', path)}\nItens: {len(items)}\n" + "\n".join(items)
                else:
                    result = r.get("content", str(r))

            elif name == "write_file":
                path = args.get("path", "")
                content = args.get("content", "")
                from urllib.parse import quote as _quote
                import re as _re
                # Limpa conteudo preservando estrutura
                clean_content = content.replace("\\n", "\n")
                # Remove markdown mas mantem listas e paragrafos
                clean_content = _re.sub(r'^#{1,6}\s+', '', clean_content, flags=_re.MULTILINE)
                clean_content = clean_content.replace("**", "").replace("__", "").replace("`", "")
                clean_content = _re.sub(r'^\s*[-*+]\s+', '• ', clean_content, flags=_re.MULTILINE)
                clean_content = _re.sub(r'\n{3,}', '\n\n', clean_content)
                clean_content = '\n'.join(line.rstrip() for line in clean_content.split('\n'))
                filename = Path(path).name if path else "arquivo.txt"
                # Diretorio do TENANT (isolado). Antes era hardcoded em
                # /root/DEEP-OS/downloads, o que quebrava se o projeto mudasse
                # de pasta e deixava todos os assinantes no mesmo diretorio.
                from core.reminder_doc import tenant_downloads_dir
                docs_dir = tenant_downloads_dir()
                docs_dir.mkdir(parents=True, exist_ok=True)
                filepath = docs_dir / filename
                filepath.write_text(clean_content.strip(), encoding="utf-8")
                download_url = f"/api/download?path={_quote(str(filepath))}"
                result = f"Arquivo salvo: {filename}\n\n📥 **Baixar:** [Clique aqui para baixar {filename}]({download_url})"

            elif name == "save_document":
                title = args.get("title", "documento")
                content = args.get("content", "")
                category = args.get("category", "notas")
                fmt = args.get("format", "md").lower().strip()
                from urllib.parse import quote as _quote
                import re as _re

                # ── Formatacao inteligente do conteudo ──────────────────────────────
                raw = content
                # Converte \\n literais em quebras de linha reais
                raw = raw.replace("\\n", "\n")

                def _md_to_html(text: str) -> str:
                    """Converte markdown simples para HTML bonito."""
                    lines = text.split("\n")
                    html_lines = []
                    in_list = False
                    in_num_list = False
                    for line in lines:
                        stripped = line.strip()
                        # Headers
                        hm = _re.match(r'^(#{1,6})\s+(.+)', stripped)
                        if hm:
                            level = len(hm.group(1))
                            html_lines.append(f"</ul>" if in_list else "")
                            html_lines.append(f"</ol>" if in_num_list else "")
                            in_list = False; in_num_list = False
                            html_lines.append(f"<h{level}>{hm.group(2)}</h{level}>")
                            continue
                        # Horizontal rule
                        if _re.match(r'^-{3,}$|^\*{3,}$|^_{3,}$', stripped):
                            html_lines.append("</ul>" if in_list else "")
                            html_lines.append("</ol>" if in_num_list else "")
                            in_list = False; in_num_list = False
                            html_lines.append("<hr>")
                            continue
                        # Unordered list
                        lm = _re.match(r'^[-*+]\s+(.+)', stripped)
                        if lm:
                            if not in_list:
                                html_lines.append("</ol>" if in_num_list else "")
                                in_num_list = False
                                html_lines.append("<ul>")
                                in_list = True
                            item = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', lm.group(1))
                            item = _re.sub(r'`(.+?)`', r'<code>\1</code>', item)
                            html_lines.append(f"  <li>{item}</li>")
                            continue
                        # Ordered list
                        olm = _re.match(r'^\d+[.)]\s+(.+)', stripped)
                        if olm:
                            if not in_num_list:
                                html_lines.append("</ul>" if in_list else "")
                                in_list = False
                                html_lines.append("<ol>")
                                in_num_list = True
                            item = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', olm.group(1))
                            item = _re.sub(r'`(.+?)`', r'<code>\1</code>', item)
                            html_lines.append(f"  <li>{item}</li>")
                            continue
                        # Close lists if line is not a list item
                        if in_list and stripped:
                            html_lines.append("</ul>"); in_list = False
                        if in_num_list and stripped:
                            html_lines.append("</ol>"); in_num_list = False
                        # Empty line = paragraph break
                        if not stripped:
                            html_lines.append("")
                            continue
                        # Regular paragraph with inline formatting
                        para = stripped
                        para = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para)
                        para = _re.sub(r'\*(.+?)\*', r'<em>\1</em>', para)
                        para = _re.sub(r'`(.+?)`', r'<code>\1</code>', para)
                        para = _re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', para)
                        html_lines.append(f"<p>{para}</p>")
                    if in_list: html_lines.append("</ul>")
                    if in_num_list: html_lines.append("</ol>")
                    return "\n".join(html_lines)

                def _md_to_txt(text: str) -> str:
                    """Converte markdown para texto limpo e organizado."""
                    lines = text.split("\n")
                    out = []
                    for line in lines:
                        stripped = line.strip()
                        # Headers -> uppercase com separador
                        hm = _re.match(r'^(#{1,6})\s+(.+)', stripped)
                        if hm:
                            title_text = hm.group(2).upper()
                            out.append("")
                            out.append(title_text)
                            out.append("=" * len(title_text))
                            out.append("")
                            continue
                        # Horizontal rule
                        if _re.match(r'^-{3,}$|^\*{3,}$|^_{3,}$', stripped):
                            out.append("-" * 40)
                            continue
                        # Lists
                        lm = _re.match(r'^[-*+]\s+(.+)', stripped)
                        if lm:
                            item = _re.sub(r'\*\*(.+?)\*\*', r'\1', lm.group(1))
                            item = _re.sub(r'`(.+?)`', r'\1', item)
                            out.append(f"  • {item}")
                            continue
                        olm = _re.match(r'^\d+[.)]\s+(.+)', stripped)
                        if olm:
                            item = _re.sub(r'\*\*(.+?)\*\*', r'\1', olm.group(1))
                            out.append(f"  {olm.group(0)}")
                            continue
                        # Empty line
                        if not stripped:
                            out.append("")
                            continue
                        # Regular text - clean inline markdown
                        clean = stripped
                        clean = _re.sub(r'\*\*(.+?)\*\*', r'\1', clean)
                        clean = _re.sub(r'\*(.+?)\*', r'\1', clean)
                        clean = _re.sub(r'`(.+?)`', r'\1', clean)
                        clean = _re.sub(r'\[(.+?)\]\((.+?)\)', r'\1 (\2)', clean)
                        out.append(clean)
                    # Remove empty lines excess
                    result = "\n".join(out)
                    result = _re.sub(r'\n{4,}', '\n\n\n', result)
                    return result.strip()

                def _clean_md(text: str) -> str:
                    """Limpa markdown mas mantem estrutura."""
                    text = _re.sub(r'^\s*#{1,6}\s+', '', text, flags=_re.MULTILINE)
                    text = _re.sub(r'^\s*[-*+]\s+', '• ', text, flags=_re.MULTILINE)
                    text = _re.sub(r'^\s*\d+[.)]\s+', '', text, flags=_re.MULTILINE)
                    text = _re.sub(r'^>{1,}\s*', '', text, flags=_re.MULTILINE)
                    text = _re.sub(r'^-{3,}$|^\*{3,}$|^_{3,}$', '', text, flags=_re.MULTILINE)
                    text = _re.sub(r'\n{4,}', '\n\n\n', text)
                    text = '\n'.join(line.rstrip() for line in text.split('\n'))
                    return text.strip()

                # Gera nome do arquivo
                from datetime import datetime as _dt
                today = _dt.now()
                safe_title = "".join(c if c.isalnum() or c in " _-" else "" for c in title)
                safe_title = safe_title.strip().replace(" ", "_")[:60]
                ext_map = {"md": ".md", "txt": ".txt", "doc": ".doc", "html": ".html", "json": ".json"}
                ext = ext_map.get(fmt, ".md")
                filename = f"{today.strftime('%Y%m%d')}_{safe_title}{ext}"
                # Diretorio do TENANT (isolado por assinante)
                from core.reminder_doc import tenant_downloads_dir
                docs_dir = tenant_downloads_dir()
                docs_dir.mkdir(parents=True, exist_ok=True)
                filepath = docs_dir / filename
                header = f"{title}\n{'='*len(title)}\nCategoria: {category.title()}\nCriado em: {today.strftime('%d/%m/%Y %H:%M')}\n\n"

                # Gera conteudo final por formato
                if fmt == "json":
                    import json as _json
                    doc_data = {"title": title, "category": category, "created": today.isoformat(), "content": _clean_md(raw)}
                    final_content = _json.dumps(doc_data, ensure_ascii=False, indent=2)
                elif fmt == "html":
                    body_html = _md_to_html(raw)
                    final_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>{title}</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.8; color: #333; background: #fafafa; }}
h1 {{ color: #1a1a2e; border-bottom: 3px solid #6c5ce7; padding-bottom: 12px; font-size: 1.8em; }}
h2 {{ color: #2d3436; margin-top: 28px; font-size: 1.4em; }}
h3 {{ color: #636e72; font-size: 1.2em; }}
p {{ margin: 12px 0; text-align: justify; }}
ul, ol {{ margin: 8px 0 16px 24px; }}
li {{ margin: 6px 0; }}
strong {{ color: #1a1a2e; }}
code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: 'Consolas', monospace; font-size: 0.9em; }}
a {{ color: #6c5ce7; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
hr {{ border: none; border-top: 2px solid #dfe6e9; margin: 24px 0; }}
.meta {{ color: #636e72; font-size: 0.9em; margin-bottom: 24px; padding: 12px; background: #f0f0f5; border-radius: 6px; }}
</style></head>
<body>
<h1>{title}</h1>
<div class="meta">📂 Categoria: {category.title()} | 📅 Criado: {today.strftime('%d/%m/%Y %H:%M')}</div>
<hr>
{body_html}
</body></html>"""
                elif fmt == "doc":
                    body_html = _md_to_html(raw)
                    final_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>{title}</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.8; color: #333; }}
h1 {{ color: #1a1a2e; border-bottom: 3px solid #6c5ce7; padding-bottom: 12px; }}
h2 {{ color: #2d3436; margin-top: 24px; }}
p {{ margin: 10px 0; text-align: justify; }}
ul, ol {{ margin: 8px 0 16px 24px; }}
li {{ margin: 4px 0; }}
code {{ background: #f0f0f0; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
strong {{ color: #1a1a2e; }}
hr {{ border: none; border-top: 1px solid #ddd; margin: 20px 0; }}
</style></head>
<body>
<h1>{title}</h1>
<p style="color:#666; font-size:0.9em;">Categoria: {category.title()} | Criado: {today.strftime('%d/%m/%Y %H:%M')}</p>
<hr>
{body_html}
</body></html>"""
                elif fmt == "txt":
                    final_content = header + _md_to_txt(raw)
                else:  # md
                    header_md = f"# {title}\n\n> 📂 Categoria: {category.title()}\n> 📅 Criado em: {today.strftime('%d/%m/%Y %H:%M')}\n\n---\n\n"
                    final_content = header_md + raw
                filepath.write_text(final_content, encoding="utf-8")
                download_url = f"/api/download?path={_quote(str(filepath))}"
                result = f"Documento salvo: {filename}\n\n📥 **Baixar:** [Clique aqui para baixar {filename}]({download_url})"
                print(f"[VoiceWS] Documento salvo para download ({fmt}): {filepath}")

            # ── Tools extras (full toolset) ──────────────────────────────────────
            elif name == "bash":
                import subprocess
                cmd = args.get("command", "")
                workdir = args.get("workdir", None)
                try:
                    await self.ws.send_json({"type": "transcript", "speaker": "Charon", "text": "Executando comando..."})
                except Exception:
                    pass
                try:
                    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=workdir)
                    result = r.stdout[:2000] if r.returncode == 0 else f"Erro: {r.stderr[:2000]}"
                except subprocess.TimeoutExpired:
                    result = "Timeout: comando demorou mais de 30 segundos"
                except Exception as e:
                    result = f"Erro: {e}"

            elif name == "file_edit":
                from tools.file_edit import tool_file_edit
                path = args.get("path", "")
                old = args.get("old_string", "")
                new = args.get("new_string", "")
                r = await tool_file_edit(path, old, new)
                result = r.get("message", str(r))

            elif name == "web_fetch":
                from tools.web_fetch import tool_web_fetch
                url = args.get("url", "")
                r = await tool_web_fetch(url)
                result = r.get("content", str(r))[:3000]

            elif name == "memory_save":
                from memory.memory_manager import load_memory, save_memory
                ns = args.get("namespace", "notes")
                key = args.get("key", "")
                content = args.get("content", "")
                mem = load_memory()
                if ns not in mem:
                    mem[ns] = {}
                mem[ns][key] = {"value": content, "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                save_memory(mem)
                result = f"Salvo em {ns}/{key}"

            elif name == "memory_recall":
                from memory.memory_manager import load_memory
                ns = args.get("namespace", "notes")
                key = args.get("key", "")
                mem = load_memory()
                entry = mem.get(ns, {}).get(key, {})
                result = entry.get("value", f"Nenhum dado em {ns}/{key}")

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()

        elapsed = (asyncio.get_event_loop().time() - t0) * 1000
        print(f"[VoiceWS] Tool result: {name} -> {str(result)[:100]} ({elapsed:.0f}ms)")

        # Envia o resultado da tool para o frontend exibir no chat
        try:
            await self.ws.send_json({
                "type": "tool_result",
                "tool": name,
                "result": str(result)[:2000],
            })
        except Exception:
            pass

        return types.FunctionResponse(id=fc.id, name=name, response={"result": result})

    async def _send_startup_briefing(self):
        await asyncio.sleep(1)
        if not self.session or not self._running:
            return

        identity = _load_identity()
        assistant_name = identity.get("assistant_name", "") or self._voice
        user_name = identity.get("user_name", "") or ""

        trigger = f"Se apresente para {user_name} agora. Diga seu nome, horario e como pode ajudar." if user_name else "Se apresente agora. Diga seu nome e horario."

        print(f"[VoiceWS] Enviando trigger: {trigger}")
        self._turn_done_event.clear()
        try:
            await self.session.send_client_content(
                turns={"parts": [{"text": trigger}]},
                turn_complete=True,
            )
        except Exception as e:
            print(f"[VoiceWS] Erro ao enviar briefing: {e}")

    async def _handle_response(self, response) -> None:
        if not self._running:
            return

        # Log AGREGADO — nao imprimir por chunk.
        #
        # Antes, cada resposta do Gemini gerava uma linha:
        #   [VoiceWS] Recebido: data=True, tool=False, ... (delay=0ms)
        # A 400 mil linhas/dia isso encheu /var/log/syslog com 27 GB e derrubou
        # o disco do VPS. Agora registramos apenas o ANORMAL:
        #   - delay entre chunks acima de 300 ms (gargalo real de rede/Gemini)
        #   - um resumo ao fechar cada turno
        if response.server_content:
            sc = response.server_content
            now = asyncio.get_event_loop().time()
            delay_ms = (now - self._last_response_time) * 1000
            self._chunks_recebidos += 1
            self._chunks_no_turno += 1
            if delay_ms > self._maior_delay_ms:
                self._maior_delay_ms = delay_ms

            # So avisa delay alto, no maximo a cada 30 s (evita rajada)
            if delay_ms > 300 and (now - self._ultimo_aviso_delay) > 30:
                self._ultimo_aviso_delay = now
                print(f"[VoiceWS] AVISO: delay alto entre chunks: {delay_ms:.0f}ms "
                      f"(pode indicar gargalo de rede ou do Gemini)")

            if sc.turn_complete:
                duracao = now - self._turno_inicio if self._turno_inicio else 0
                print(f"[VoiceWS] Turno concluido: {self._chunks_no_turno} chunks em "
                      f"{duracao:.1f}s | maior delay: {self._maior_delay_ms:.0f}ms | "
                      f"total na sessao: {self._chunks_recebidos}")
                # Reinicia as metricas do turno
                self._turno_inicio = now
                self._chunks_no_turno = 0
                self._maior_delay_ms = 0.0

        if response.data:
            if self._interrupted:
                pass  # discard old audio only
            else:
                try:
                    await self.ws.send_bytes(response.data)
                except Exception as e:
                    print(f"[VoiceWS] Erro ao enviar audio (ignorado): {e}")

        if response.server_content:
            sc = response.server_content

            # Skip OLD transcriptions (user already speaking new message)
            # but KEEP turn_complete to reset state and flush audio
            if self._interrupted:
                if sc.turn_complete:
                    # Flush remaining audio even when interrupted
                    if self._audio_buffer:
                        try:
                            merged = b''.join(self._audio_buffer)
                            self._audio_buffer = []
                            await self.ws.send_bytes(merged)
                        except Exception:
                            pass
                    self._interrupted = False
                    self._turn_done_event.set()
                    try:
                        await self.ws.send_json({"type": "turn_complete"})
                    except Exception:
                        pass
                else:
                    self._audio_buffer = []
                return

            if sc.input_transcription and sc.input_transcription.text:
                try:
                    await self.ws.send_json({
                        "type": "transcript",
                        "speaker": "user",
                        "text": sc.input_transcription.text,
                    })
                except Exception:
                    pass
            if sc.output_transcription and sc.output_transcription.text:
                try:
                    await self.ws.send_json({
                        "type": "transcript",
                        "speaker": "Charon",
                        "text": sc.output_transcription.text,
                    })
                except Exception:
                    pass
            if sc.turn_complete:
                # Espera os ultimos chunks do Gemini chegarem antes de fechar
                # o turno. Antes eram 500ms fixos, o que as vezes cortava a
                # cauda da ultima palavra (o ring do cliente ficava sem audio).
                await asyncio.sleep(TURN_TAIL_GRACE_S)
                # Flush buffer de audio restante
                if self._audio_buffer:
                    try:
                        merged = b''.join(self._audio_buffer)
                        self._audio_buffer = []
                        await self.ws.send_bytes(merged)
                    except Exception:
                        pass
                self._turn_done_event.set()
                try:
                    await self.ws.send_json({"type": "turn_complete"})
                except Exception:
                    pass

        if response.tool_call:
            fn_responses = []
            for fc in response.tool_call.function_calls:
                print(f"[VoiceWS] Executando tool: {fc.name}")
                try:
                    await self.ws.send_json({"type": "status", "message": f"Executando {fc.name}..."})
                except Exception:
                    pass
                try:
                    fr = await asyncio.wait_for(self._execute_tool(fc), timeout=20)
                except asyncio.TimeoutError:
                    print(f"[VoiceWS] Tool {fc.name} timeout (20s)")
                    fr = types.FunctionResponse(
                        id=fc.id, name=fc.name,
                        response={"result": f"Timeout: {fc.name} demorou mais de 20 segundos."}
                    )
                except Exception as e:
                    print(f"[VoiceWS] Tool {fc.name} erro: {e}")
                    fr = types.FunctionResponse(
                        id=fc.id, name=fc.name,
                        response={"result": f"Erro ao executar {fc.name}: {str(e)[:200]}"}
                    )
                fn_responses.append(fr)
            try:
                await self.session.send_tool_response(function_responses=fn_responses)
            except Exception as e:
                print(f"[VoiceWS] Erro ao enviar tool_response: {e}")

    async def _receive_loop(self):
        """Escuta respostas do Gemini continuamente."""
        while self._running:
            try:
                async for response in self.session.receive():
                    if not self._running:
                        return
                    self._last_response_time = asyncio.get_event_loop().time()
                    try:
                        await self._handle_response(response)
                    except Exception as e:
                        print(f"[VoiceWS] Erro no _handle_response: {e}")
                        traceback.print_exc()
            except asyncio.CancelledError:
                return
            except Exception as e:
                if not self._running:
                    return
                print(f"[VoiceWS] Receive erro: {e}")
                traceback.print_exc()
                if self._running:
                    asyncio.create_task(self._safe_reconnect())

    def _ensure_receive_loop(self):
        """Reinicia receive se parou (erro de conexao)."""
        if self._receive_task is None or self._receive_task.done():
            if self._running and self.session:
                self._receive_task = asyncio.create_task(self._receive_loop())

    async def _keepalive_loop(self):
        """Verifica se a sessao esta viva e reconecta automaticamente."""
        ping_count = 0
        while self._running:
            try:
                await asyncio.sleep(15)
                if not self._running or not self.session:
                    return

                # Verifica se a receive task ainda esta rodando
                if self._receive_task and self._receive_task.done():
                    print("[VoiceWS] Receive task morta! Tentando reconexao...")
                    await self._reconnect()
                    continue

                # Envia ping a cada 30 segundos para manter sessao ativa
                ping_count += 1
                if ping_count >= 2:  # 2 * 15s = 30s
                    ping_count = 0
                    try:
                        silence = b'\x00' * 480  # 15ms de silencio (16kHz 16bit mono)
                        await self.session.send_realtime_input(
                            media={"data": silence, "mime_type": "audio/pcm;rate=16000"}
                        )
                        self._last_response_time = asyncio.get_event_loop().time()
                    except Exception as e:
                        print(f"[VoiceWS] Ping falhou, reconectando... ({e})")
                        await self._reconnect()

                # Watchdog: se nao recebe nada por 5 minutos, forca reconexao
                now = asyncio.get_event_loop().time()
                silence_duration = now - self._last_response_time
                if silence_duration > 300:
                    print(f"[VoiceWS] Watchdog: {silence_duration:.0f}s sem resposta. Forcando reconexao...")
                    await self._reconnect()
                    continue

            except asyncio.CancelledError:
                return
            except Exception as e:
                if self._running:
                    print(f"[VoiceWS] Keepalive erro: {e}")

    async def _safe_reconnect(self):
        """Reconnect seguro — não bloqueia a receive_loop."""
        await asyncio.sleep(1)
        if self._reconnecting:
            return
        await self._reconnect()

    async def _reconnect(self):
        """Reconecta ao Gemini Live quando a sessao expira."""
        if not self._running or self._reconnecting:
            return
        self._reconnecting = True
        try:
            # Cancela tasks antigas
            if self._receive_task and not self._receive_task.done():
                self._receive_task.cancel()
            if self._keepalive_task and not self._keepalive_task.done():
                self._keepalive_task.cancel()

            # Fecha sessao antiga (com timeout para nao travar)
            if self.session:
                try:
                    await asyncio.wait_for(self.session.close(), timeout=5)
                except Exception:
                    pass
            if self._cm:
                try:
                    await asyncio.wait_for(self._cm.__aexit__(None, None, None), timeout=5)
                except Exception:
                    pass
                self._cm = None
            self.session = None

            await asyncio.sleep(2)  # Espera antes de reconectar

            # Client novo a cada reconexao — evita estado stale
            api_key = _get_gemini_key()
            if not api_key or api_key == "cole_sua_chave_aqui":
                print("[VoiceWS] API key nao configurada")
                return

            self.client = genai.Client(api_key=api_key)
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                output_audio_transcription={},
                input_audio_transcription={},
                system_instruction=_build_system_instruction(self._voice),
                tools=[types.Tool(function_declarations=_get_active_tools())],
                session_resumption=types.SessionResumptionConfig(),
                context_window_compression=types.ContextWindowCompressionConfig(
                    sliding_window=types.SlidingWindow(),
                ),
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self._voice)
                    )
                ),
            )
            self._cm = self.client.aio.live.connect(model=LIVE_MODEL, config=config)
            self.session = await self._cm.__aenter__()
            self._last_response_time = asyncio.get_event_loop().time()
            print(f"[VoiceWS] Reconectado! Voz: {self._voice}")

            # Reinicia tasks
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

            # Notifica frontend
            try:
                await self.ws.send_json({"type": "connected", "voice": self._voice, "tools": len(_get_active_tools())})
            except Exception:
                pass
            self._reconnecting = False

        except Exception as e:
            self._reconnecting = False
            print(f"[VoiceWS] Falha na reconexao: {e}")
            traceback.print_exc()
            self._running = False
            try:
                await self.ws.send_json({"type": "error", "message": f"Falha na reconexao: {str(e)[:200]}"})
                await self.ws.send_json({"type": "disconnected"})
            except Exception:
                pass

    async def stop(self):
        self._running = False
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
        if self.session:
            try:
                await self.session.close()
            except Exception:
                pass
        if self._cm:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:
                pass
            self._cm = None
        self.session = None
        try:
            await self.ws.send_json({"type": "disconnected"})
        except Exception:
            pass


_sessions: dict = {}


async def disconnect_all_voice_sessions():
    """Desconecta todas as sessoes de voz ativas (usado quando identity muda)."""
    for sid, session in list(_sessions.items()):
        if session._running:
            try:
                await session.stop()
            except Exception:
                pass
    _sessions.clear()


@router.post("/voice/disconnect-all")
async def api_disconnect_all_voice():
    """Endpoint para forçar desconexão de todas as sessoes Charon."""
    await disconnect_all_voice_sessions()
    return {"status": "disconnected"}


async def deliver_reminder(tenant_id: str | None, message: str, reminder: dict | None = None) -> bool:
    """
    Entrega um lembrete vencido ao assinante, pelo WebSocket do Charon.

    Alem de mandar o texto para a IA falar, envia um evento `transcript`
    para o frontend renderizar na conversa (mesmo formato das mensagens
    normais, que o CharonPage ja sabe exibir).

    `reminder` (opcional) traz a linha do banco, usada para formatar o horario
    na hora LOCAL do usuario — o banco guarda UTC.

    Retorna True se havia sessao ativa para receber.
    """
    alvo = None
    for session in list(_sessions.values()):
        if not getattr(session, "_running", False):
            continue
        # Se o lembrete tem tenant, entrega so na sessao daquele assinante.
        # Sessoes sem tenant registrado atendem lembretes globais.
        sess_tenant = getattr(session, "_tenant_id", None)
        if tenant_id:
            if sess_tenant == tenant_id:
                alvo = session
                break
        elif not sess_tenant:
            alvo = session
            break

    if alvo is None:
        return False

    # Formata o horario na hora local do usuario (o banco guarda UTC)
    quando = ""
    if reminder:
        try:
            from core.reminder_doc import _fmt_humano
            quando = _fmt_humano(reminder.get("fire_at", ""), reminder.get("tz"))
        except Exception:
            quando = ""

    texto = f"Lembrete: {message}" + (f" (agendado para {quando})" if quando else "")

    try:
        # 1. Frontend: aparece na conversa do Charon
        await alvo.ws.send_json({"type": "transcript", "speaker": "charon", "text": f"⏰ {message}"})
        await alvo.ws.send_json({"type": "reminder", "message": message, "when": quando})

        # 2. IA: fala o lembrete em voz
        if alvo.session:
            await alvo.session.send_client_content(
                turns={"parts": [{"text": f"Entregue este lembrete ao usuario agora, em voz, de forma natural: {message}"}]},
                turn_complete=True,
            )
        print(f"[VoiceWS] Lembrete entregue (tenant={tenant_id or 'global'}): {message[:60]}")
        return True
    except Exception as e:
        print(f"[VoiceWS] Erro ao entregar lembrete: {e}")
        return False


@router.websocket("/ws/voice")
async def voice_websocket(ws: WebSocket):
    await ws.accept()

    # Identifica o tenant desta conexao de voz (isolamento por assinante).
    # Aceita ?token=<JWT> (preferido) ou ?tenant_id=<id>.
    qp = ws.query_params
    _voice_tenant = _tenant_from_token(qp.get("token")) or qp.get("tenant_id")
    if _voice_tenant:
        try:
            from core.tenant_identity import set_current_tenant
            set_current_tenant(_voice_tenant)
        except Exception:
            pass
        print(f"[VoiceWS] Conexao do tenant: {_voice_tenant}")

    session = VoiceSession(ws)
    session._tenant_id = _voice_tenant
    sid = f"voice_{id(ws)}"
    _sessions[sid] = session
    _audio_buffer: list[bytes] = []

    try:
        while True:
            msg = await ws.receive()

            if "bytes" in msg and msg["bytes"]:
                if session._running and session.session:
                    session._interrupted = False
                    await session.send_audio(msg["bytes"])
                else:
                    _audio_buffer.append(msg["bytes"])
                    # Limita buffer a 3 segundos (48kHz/3 = 16kHz, 16bit = 32000 bytes/s)
                    if len(_audio_buffer) > 48:
                        _audio_buffer = _audio_buffer[-48:]
                continue

            if "text" in msg and msg["text"]:
                data = json.loads(msg["text"])
                msg_type = data.get("type", "")

                if msg_type == "start":
                    for old_sid, old_session in list(_sessions.items()):
                        if old_sid != sid and old_session._running:
                            await old_session.stop()
                            _sessions.pop(old_sid, None)
                    identity = _load_identity()
                    voice_from_config = identity.get("voice", "Charon") or "Charon"
                    user_tz = data.get("timezone", "America/Sao_Paulo")
                    user_locale = data.get("locale", "pt-BR")
                    inst_prompt = data.get("system_prompt", "")
                    inst_temp = data.get("temperature", 0.7)

                    # Registra o fuso do usuario no contexto. Sem isto, a action
                    # `reminder` calculava "agora" com o relogio do servidor
                    # (UTC) e um lembrete para as 14:30 em Brasilia parecia
                    # estar no passado.
                    try:
                        from core.tenant_identity import set_current_timezone
                        set_current_timezone(user_tz)
                        print(f"[VoiceWS] Fuso do usuario: {user_tz}")
                    except Exception:
                        pass

                    started = await session.start(voice=voice_from_config, user_tz=user_tz, user_locale=user_locale, extra_prompt=inst_prompt)
                    # Envia áudio acumulado no buffer
                    if started and _audio_buffer:
                        print(f"[VoiceWS] Enviando {len(_audio_buffer)} chunks do buffer")
                        for chunk in _audio_buffer:
                            if session._running and session.session:
                                await session.send_audio(chunk)
                        _audio_buffer.clear()

                elif msg_type == "text":
                    if data.get("text") and session.session:
                        try:
                            session._turn_done_event.clear()
                            session._interrupted = False
                            from core.skill_loader import get_charon_skills_context
                            user_text = data["text"]
                            skills_ctx = get_charon_skills_context(user_text)
                            if skills_ctx:
                                full_text = f"{skills_ctx}\n\nUsuario: {user_text}"
                            else:
                                full_text = user_text
                            await session.session.send_client_content(
                                turns={"parts": [{"text": full_text}]}, turn_complete=True
                            )
                        except Exception:
                            pass

                elif msg_type == "stop":
                    break

                elif msg_type == "interrupt":
                    session._interrupted = True
                    if session.session and session._running:
                        try:
                            await session.session.send_realtime_input(
                                audio={"data": b"", "mime_type": "audio/pcm;rate=16000"},
                                interrupt=True,
                            )
                        except Exception:
                            pass
                    session._turn_done_event.set()

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await session.stop()
        _sessions.pop(sid, None)


@router.get("/api/voice/status")
async def voice_status():
    key = _get_gemini_key()
    from core.skill_loader import get_skill_count
    toolset = _get_charon_toolset()
    return {
        "available": bool(key and key != "cole_sua_chave_aqui"),
        "default_voice": "charon",
        "toolset": toolset,
        "tools": len(_get_active_tools()),
        "actions_loaded": _ACTIONS_OK,
        "skills": get_skill_count(),
    }
