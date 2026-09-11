"""
Plan Mode — Enter/Exit planning mode for structured task execution.
Mirrors OpenClaude's EnterPlanModeTool / ExitPlanModeTool.
"""
import json
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# ─── Plan State ───────────────────────────────────────────────────────────────
PLAN_STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "plan_state.json")

plan_state = {
    "active": False,
    "plan_content": "",
    "approved": False,
    "plan_summary": "",
    "entered_at": "",
    "exited_at": "",
}


def _persist():
    try:
        os.makedirs(os.path.dirname(PLAN_STATE_FILE), exist_ok=True)
        with open(PLAN_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(plan_state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load():
    global plan_state
    try:
        if os.path.exists(PLAN_STATE_FILE):
            with open(PLAN_STATE_FILE, encoding="utf-8") as f:
                loaded = json.load(f)
                plan_state.update(loaded)
    except Exception:
        pass


_load()


# ─── API ──────────────────────────────────────────────────────────────────────


class PlanEnterRequest(BaseModel):
    plan_content: str = ""


class PlanExitRequest(BaseModel):
    approved: bool = False
    plan_summary: str = ""


@router.get("/plan/state")
async def get_plan_state():
    return {
        "active": plan_state["active"],
        "plan_content": plan_state["plan_content"],
        "approved": plan_state["approved"],
        "plan_summary": plan_state["plan_summary"],
        "entered_at": plan_state["entered_at"],
        "exited_at": plan_state["exited_at"],
    }


@router.post("/plan/enter")
async def enter_plan_mode(req: PlanEnterRequest = PlanEnterRequest()):
    plan_state["active"] = True
    plan_state["plan_content"] = req.plan_content
    plan_state["approved"] = False
    plan_state["plan_summary"] = ""
    plan_state["entered_at"] = datetime.now().isoformat()
    plan_state["exited_at"] = ""
    _persist()
    return {"status": "plan_mode_entered", "active": True}


@router.post("/plan/exit")
async def exit_plan_mode(req: PlanExitRequest):
    if not plan_state["active"]:
        raise HTTPException(400, "Plan mode is not active")
    plan_state["active"] = False
    plan_state["approved"] = req.approved
    plan_state["plan_summary"] = req.plan_summary
    plan_state["exited_at"] = datetime.now().isoformat()
    _persist()
    return {
        "status": "plan_mode_exited",
        "approved": req.approved,
        "plan_summary": req.plan_summary,
    }
