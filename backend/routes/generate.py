import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.config import get_base_dir
from generator.autofix import AutoFixLoop
from generator.planner import ProjectPlanner
from generator.sandbox import CodeSandbox
from generator.scaffolder import ProjectScaffolder
from generator.tester import ProjectTester

router = APIRouter()

def _get_generated_dir():
    d = get_base_dir() / "generated"
    d.mkdir(exist_ok=True)
    return d

class GenerateRequest(BaseModel):
    prompt: str
    provider: str = "ollama"
    model: str = "qwen2.5-coder:14b"
    api_key: str = ""

@router.post("/generate/plan")
async def generate_plan(req: GenerateRequest):
    try:
        planner = ProjectPlanner(req.provider, req.model, req.api_key)
        plan = await planner.plan(req.prompt)
        return {"status": "ok", "plan": plan.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate")
async def generate_project(req: GenerateRequest):
    try:
        planner = ProjectPlanner(req.provider, req.model, req.api_key)
        plan = await planner.plan(req.prompt)

        gen_dir = _get_generated_dir()
        scaffolder = ProjectScaffolder(str(gen_dir), req.provider, req.model, req.api_key)
        scaffold_result = await scaffolder.scaffold(plan)

        return {
            "status": "ok",
            "plan": plan.model_dump(),
            "scaffold": scaffold_result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    async def event_stream():
        try:
            yield json.dumps({"type": "status", "message": "Planning project..."}) + "\n"
            planner = ProjectPlanner(req.provider, req.model, req.api_key)
            plan = await planner.plan(req.prompt)
            yield json.dumps({"type": "plan", "data": plan.model_dump()}) + "\n"

            gen_dir = _get_generated_dir()
            project_dir = gen_dir / plan.project_name

            yield json.dumps({"type": "status", "message": f"Generating project: {plan.project_name}..."}) + "\n"
            scaffolder = ProjectScaffolder(str(gen_dir), req.provider, req.model, req.api_key)
            scaffold_result = await scaffolder.scaffold(plan)

            for f in scaffold_result.get("files", []):
                yield json.dumps({"type": "file", "data": f}) + "\n"

            if scaffold_result.get("has_errors"):
                yield json.dumps({"type": "status", "message": "Fixing errors..."}) + "\n"
                autofix = AutoFixLoop(req.provider, req.model, req.api_key)
                files_to_fix = []
                for f in scaffold_result.get("files", []):
                    if f.get("status") == "placeholder" and f.get("error"):
                        files_to_fix.append({
                            "path": str(project_dir / f["path"]),
                            "content": (project_dir / f["path"]).read_text() if (project_dir / f["path"]).exists() else "",
                            "error": f.get("error", ""),
                            "status": "error",
                        })
                if files_to_fix:
                    fixed = await autofix.fix_project(files_to_fix, plan.language)
                    for fix in fixed:
                        if fix.get("fix_status") == "fixed":
                            fp = Path(fix["path"])
                            fp.parent.mkdir(parents=True, exist_ok=True)
                            fp.write_text(fix["content"], encoding="utf-8")
                            yield json.dumps({"type": "fix", "data": {"path": str(fp), "status": "fixed"}}) + "\n"

            yield json.dumps({"type": "status", "message": "Installing dependencies..."}) + "\n"
            sandbox = CodeSandbox()
            dep_result = await sandbox.install_dependencies(str(project_dir), plan.language, plan.dependencies)
            yield json.dumps({"type": "dependencies", "data": dep_result}) + "\n"

            yield json.dumps({"type": "status", "message": "Generating tests..."}) + "\n"
            tester = ProjectTester(req.provider, req.model, req.api_key)
            test_files = await tester.generate_tests(
                plan.project_name, plan.description, plan.language,
                scaffold_result.get("files", [])
            )
            for tf in test_files:
                if tf.get("content"):
                    tfp = project_dir / tf["path"]
                    tfp.parent.mkdir(parents=True, exist_ok=True)
                    tfp.write_text(tf["content"], encoding="utf-8")
                    yield json.dumps({"type": "test_file", "data": {"path": tf["path"], "status": "created"}}) + "\n"

            if plan.test_command:
                yield json.dumps({"type": "status", "message": "Running tests..."}) + "\n"
                test_result = await tester.run_tests(str(project_dir), plan.test_command)
                yield json.dumps({"type": "test_result", "data": test_result}) + "\n"

                if not test_result.get("passed"):
                    yield json.dumps({"type": "status", "message": "Tests failed, attempting auto-fix..."}) + "\n"
                    autofix = AutoFixLoop(req.provider, req.model, req.api_key)
                    for f in scaffold_result.get("files", []):
                        fp = project_dir / f["path"]
                        if fp.exists():
                            content = fp.read_text(encoding="utf-8")
                            fix_result = await autofix.fix_file(
                                f["path"], content,
                                test_result.get("stdout", "") + "\n" + test_result.get("stderr", ""),
                                plan.language
                            )
                            if fix_result["status"] == "fixed":
                                fp.write_text(fix_result["content"], encoding="utf-8")
                                yield json.dumps({"type": "fix", "data": {"path": f["path"], "status": "fixed"}}) + "\n"

                    retest = await tester.run_tests(str(project_dir), plan.test_command)
                    yield json.dumps({"type": "retest_result", "data": retest}) + "\n"

            yield json.dumps({"type": "status", "message": "Project generation complete!"}) + "\n"

            project_files = []
            for f in scaffold_result.get("files", []):
                fp = project_dir / f["path"]
                if fp.exists():
                    project_files.append({"path": f["path"], "size": len(fp.read_text(encoding="utf-8"))})

            yield json.dumps({
                "type": "complete",
                "data": {
                    "project_name": plan.project_name,
                    "project_dir": str(project_dir),
                    "total_files": len(project_files),
                    "files": project_files,
                    "run_command": plan.run_command,
                    "test_command": plan.test_command,
                }
            }) + "\n"

        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")

@router.get("/generate/projects")
async def list_projects():
    gen_dir = _get_generated_dir()
    if not gen_dir.exists():
        return {"projects": []}
    projects = []
    for d in sorted(gen_dir.iterdir()):
        if d.is_dir():
            meta_file = d / "project.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                    projects.append(meta)
                except:
                    projects.append({"project": d.name})
    return {"projects": projects}

@router.get("/generate/projects/{name}")
async def get_project(name: str):
    project_dir = _get_generated_dir() / name
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    files = []
    for f in sorted(project_dir.rglob("*")):
        if f.is_file() and f.name != "project.json":
            files.append({
                "path": str(f.relative_to(project_dir)),
                "content": f.read_text("utf-8", errors="replace"),
            })
    meta = {}
    meta_file = project_dir / "project.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
    return {"project": name, "meta": meta, "files": files}
