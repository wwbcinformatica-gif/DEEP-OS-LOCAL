import json

from fastapi import APIRouter, HTTPException

from core.config import faq_path
from core.models import KnowledgePayload
from core.rag import rebuild_vectorstore

router = APIRouter()

def get_next_id(docs):
    ids = [d.get("id", 0) for d in docs]
    return max(ids) + 1 if ids else 1

@router.post("/knowledge")
async def add_knowledge(payload: KnowledgePayload):
    try:
        with open(faq_path, encoding="utf-8") as f:
            docs = json.load(f)
        docs.append({"id": get_next_id(docs), "texto": payload.texto})
        with open(faq_path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        rebuild_vectorstore(faq_path)
        return {"status": "success", "message": "Conhecimento absorvido com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/knowledge")
async def list_knowledge():
    try:
        with open(faq_path, encoding="utf-8") as f:
            docs = json.load(f)
        return {"items": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/knowledge/{item_id}")
async def update_knowledge(item_id: int, payload: KnowledgePayload):
    try:
        with open(faq_path, encoding="utf-8") as f:
            docs = json.load(f)
        for doc in docs:
            if doc.get("id") == item_id:
                doc["texto"] = payload.texto
                break
        else:
            raise HTTPException(status_code=404, detail="Item não encontrado")
        with open(faq_path, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        rebuild_vectorstore(faq_path)
        return {"status": "success", "message": "Atualizado!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/knowledge/{item_id}")
async def delete_knowledge(item_id: int):
    try:
        with open(faq_path, encoding="utf-8") as f:
            docs = json.load(f)
        new_docs = [d for d in docs if d.get("id") != item_id]
        if len(new_docs) == len(docs):
            raise HTTPException(status_code=404, detail="Item não encontrado")
        with open(faq_path, "w", encoding="utf-8") as f:
            json.dump(new_docs, f, ensure_ascii=False, indent=2)
        rebuild_vectorstore(faq_path)
        return {"status": "success", "message": "Removido!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
