import json
from pathlib import Path

from core.llm_native import build_messages, complete_chat
from generator.planner import ProjectPlan

FILE_GENERATOR_PROMPT = """
You are a Senior Software Engineer. Generate the COMPLETE content for a single file based on:
- Project plan: {plan_summary}
- File path: {file_path}
- Description: {file_description}

RULES:
1. Output ONLY the file content, no explanations
2. Include all imports, types, and implementations
3. Make it production-ready with error handling
4. Follow best practices for {language}
5. If HTML, include full doctype and structure
6. If CSS, make it responsive and modern
7. If JS/TS, use modern syntax (ES2020+)
8. Include comprehensive error handling
9. Add input validation where relevant
10. Maximum 500 lines per file
"""

class ProjectScaffolder:
    def __init__(self, output_dir: str, provider: str = "ollama", model: str = "qwen2.5-coder:14b", api_key: str = ""):
        self.output_dir = Path(output_dir)
        self.provider = provider
        self.model = model
        self.api_key = api_key

    async def scaffold(self, plan: ProjectPlan) -> dict:
        result = {"project_dir": str(self.output_dir / plan.project_name), "files": [], "errors": []}
        project_root = self.output_dir / plan.project_name

        for phase in plan.phases:
            phase_result = await self._generate_phase(plan, phase, project_root)
            result["files"].extend(phase_result["files"])
            result["errors"].extend(phase_result["errors"])

        await self._write_metadata(plan, project_root)
        result["total_files"] = len(result["files"])
        result["has_errors"] = len(result["errors"]) > 0
        return result

    async def _generate_phase(self, plan: ProjectPlan, phase: dict, project_root: Path) -> dict:
        result = {"files": [], "errors": []}
        phase_dir = project_root
        phase_dir.mkdir(parents=True, exist_ok=True)

        for file_spec in phase.get("files", []):
            file_path = file_spec.get("path", "")
            description = file_spec.get("description", "")
            if not file_path:
                continue
            target = project_root / file_path
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.exists():
                result["files"].append({"path": file_path, "status": "skipped", "reason": "already exists"})
                continue

            try:
                extension = file_path.split(".")[-1] if "." in file_path else ""
                content = await self._generate_file_content(plan, file_path, description)
                target.write_text(content, encoding="utf-8")
                result["files"].append({"path": file_path, "status": "created", "size": len(content)})
            except Exception as e:
                error_msg = f"Failed to generate {file_path}: {str(e)}"
                result["errors"].append(error_msg)
                target.write_text(f"// TODO: {description}\n// Error: {error_msg}\n", encoding="utf-8")
                result["files"].append({"path": file_path, "status": "placeholder", "error": error_msg})

        return result

    async def _generate_file_content(self, plan: ProjectPlan, file_path: str, description: str) -> str:
        plan_summary = f"{plan.project_name}: {plan.description} ({plan.language})"
        prompt = FILE_GENERATOR_PROMPT.format(
            plan_summary=plan_summary,
            file_path=file_path,
            file_description=description,
            language=plan.language,
        )
        messages = build_messages(prompt, f"Generate content for {file_path}")
        response = await complete_chat(self.provider, self.model, messages, temperature=0.3, api_key=self.api_key)
        return self._clean_content(response)

    def _clean_content(self, content: str) -> str:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
        return content.strip()

    async def _write_metadata(self, plan: ProjectPlan, project_root: Path):
        meta = {
            "project": plan.project_name,
            "description": plan.description,
            "language": plan.language,
            "generated_at": plan.created_at,
            "plan_id": plan.plan_id,
            "dependencies": plan.dependencies,
            "commands": {
                "run": plan.run_command,
                "test": plan.test_command,
                "build": plan.build_command,
            },
        }
        (project_root / "project.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
