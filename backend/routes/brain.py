import json
from datetime import datetime

from fastapi import APIRouter, HTTPException

from core.config import BRAIN_DIR
from core.llm import get_llm
from core.models import AgentTask, BrainArtifact

router = APIRouter()

try:
    from langchain_core.prompts import PromptTemplate
except ImportError:
    PromptTemplate = None

@router.post("/brain/artifacts")
async def create_artifact(payload: BrainArtifact):
    try:
        artifact_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        artifact = {
            "id": artifact_id,
            "title": payload.title,
            "description": payload.description,
            "plan": payload.plan,
            "status": payload.status,
            "files": payload.files,
            "result": payload.result,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        path = BRAIN_DIR / f"{artifact_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)
        return {"status": "created", "id": artifact_id, "path": str(path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/brain/artifacts")
async def list_artifacts():
    try:
        artifacts = []
        for f in sorted(BRAIN_DIR.glob("*.json"), reverse=True):
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
                artifacts.append({
                    "id": data.get("id"),
                    "title": data.get("title"),
                    "status": data.get("status"),
                    "created_at": data.get("created_at"),
                })
        return {"artifacts": artifacts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/brain/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str):
    path = BRAIN_DIR / f"{artifact_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact não encontrado")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@router.delete("/brain/artifacts/{artifact_id}")
async def delete_artifact(artifact_id: str):
    path = BRAIN_DIR / f"{artifact_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact não encontrado")
    path.unlink()
    return {"status": "deleted"}

@router.post("/brain/artifacts/{artifact_id}/plan")
async def generate_plan(artifact_id: str, task: AgentTask):
    path = BRAIN_DIR / f"{artifact_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact não encontrado")
    with open(path, encoding="utf-8") as f:
        artifact = json.load(f)
    plan_prompt = PromptTemplate.from_template(
        "Você é um arquiteto de software. Crie um plano de implementação detalhado "
        "para a seguinte tarefa:\n\n"
        "Título: {title}\nDescrição: {description}\n\n"
        "Gere uma lista de passos numerados (máximo 8 passos). "
        "Cada passo deve ser específico e acionável.\n"
        "Formato: 1. [ação concreta]\n2. [ação concreta]\n...\n\n"
        "Plano:"
    )
    llm = get_llm(task.provider, task.model, task.temperature)
    chain = plan_prompt | llm
    result = chain.invoke({
        "title": artifact["title"],
        "description": artifact["description"],
    })
    lines = [l.strip() for l in result.content.strip().split("\n") if l.strip()]
    plan = [l for l in lines if l[0].isdigit()]
    artifact["plan"] = plan
    artifact["status"] = "planned"
    artifact["updated_at"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)
    return {"status": "planned", "plan": plan}
