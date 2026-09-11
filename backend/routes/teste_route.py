"""Rota de teste — cria e remove arquivo teste.txt na raiz do projeto."""
import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

# Raiz do projeto: sobe 2 níveis a partir de backend/routes/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_FILE = PROJECT_ROOT / "teste.txt"


@router.get("/teste")
async def teste_root():
    """Endpoint de teste que retorna o status do arquivo teste.txt."""
    exists = TEST_FILE.exists()
    size = TEST_FILE.stat().st_size if exists else 0
    return {
        "status": "ok",
        "endpoint": "/teste",
        "arquivo": str(TEST_FILE),
        "existe": exists,
        "tamanho_bytes": size,
    }


@router.post("/teste/criar")
async def criar_arquivo():
    """Cria o arquivo teste.txt na raiz do projeto."""
    TEST_FILE.write_text("Arquivo de teste criado pela rota /teste/criar\n", encoding="utf-8")
    return {
        "status": "criado",
        "arquivo": str(TEST_FILE),
        "tamanho_bytes": TEST_FILE.stat().st_size,
    }


@router.delete("/teste/apagar")
async def apagar_arquivo():
    """Apaga o arquivo teste.txt da raiz do projeto."""
    if TEST_FILE.exists():
        TEST_FILE.unlink()
        return {"status": "apagado", "arquivo": str(TEST_FILE)}
    return {"status": "nao_encontrado", "arquivo": str(TEST_FILE)}