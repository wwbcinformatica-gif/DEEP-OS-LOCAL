# DEEP-OS-LOCAL

Sistema Operacional de Agentes de IA - Versao Local

## Configuracao Local

Este projeto e uma copia do DEEP-OS configurada para execucao local (127.0.0.1).

## Inicio Rapido

### Opcao 1: Usar o script batch
```bash
INICIAR-LOCAL.bat
```

### Opcao 2: Inicio manual

#### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Enderecos Locais

- Backend: http://127.0.0.1:8000
- Frontend: http://127.0.0.1:5175
- API Docs: http://127.0.0.1:8000/docs

## Configuracao

Edite `config.yaml` para configurar:
- Modelos de IA (Ollama local)
- Memoria espiral
- Porta do servidor

## Variavel de Ambiente

Copie `backend/.env.example` para `backend/.env` e configure suas chaves de API.

## Estrutura

```
DEEP-OS-LOCAL/
├── backend/          # FastAPI + Python
├── frontend/         # React + Vite
├── config.yaml       # Configuracao principal
├── INICIAR-LOCAL.bat # Script de inicio
└── README.md         # Este arquivo
```
