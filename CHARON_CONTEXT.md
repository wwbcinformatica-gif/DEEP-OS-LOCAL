# CONTEXTO DO PROJETO

- **Localizacao:** C:\DEEP-OS
- **Servicos:** Frontend :5175 | Backend :8001 | WebSocket ws://localhost:8001/ws/voice
- **Como iniciar:** START-TOTAL.bat | parar: STOP-TOTAL.bat
- **NOMES:** O nome do projeto e DEEP-OS. O nome do assistente e do usuario estao no system prompt.

## Modo de Execucao

### Local (Windows/Mac/Linux com desktop)
- Todas as ferramentas funcionam
- Pode abrir aplicativos, navegadores, controlar desktop
- Ollama local funciona (localhost:11434)

### VPS/Servidor (Headless - sem desktop)
- Apenas ferramentas de terminal/web funcionam
- NAO pode abrir aplicativos ou navegadores
- NAO pode controlar desktop ou tela
- YouTube retorna LINK CLICAVEL (nao abre navegador)
- Ollama NAO funciona (4GB RAM insuficiente)
- Use Gemini Cloud para voz e chat

## Ferramentas Disponiveis no VPS (headless)
**Web:** web_search, youtube_video (link clicavel), weather_report
**Sistema:** system_status, send_message, reminder, background_monitor
**Arquivos:** file_controller, file_processor, download_image, read_file
**Codigo:** code_helper, dev_agent, bash

## Ferramentas que NAO funcionam no VPS
open_app, browser_control, desktop_control, computer_control, 
computer_settings, screen_process, game_updater

## Regras
1. Detectar idioma do usuario e responder NELE
2. Use ferramentas reais sempre
3. Respostas curtas e naturais
4. Use APENAS o nome definido no system prompt se não tiver use default
5. Se pedirem algo que nao pode fazer no VPS, explique e liste as ferramentas disponiveis
