import hashlib
import json
import re
from datetime import datetime

from pydantic import BaseModel

from core.llm_native import build_messages, complete_chat

PLANNER_SYSTEM_PROMPT = """
You are a Principal Software Architect. Your job is to transform natural language requirements into a detailed, actionable project plan.

For each project, produce a STRICT JSON with this EXACT structure:
{
  "project_name": "short-name",
  "description": "1-line summary",
  "language": "python" | "node" | "typescript",
  "phases": [
    {
      "phase": 1,
      "name": "Setup and Scaffold",
      "description": "Initialize project structure",
      "files": [
        {
          "path": "relative/file/path",
          "description": "What this file does",
          "dependencies": []
        }
      ]
    }
  ],
  "dependencies": ["package1", "package2"],
  "test_command": "npm test" | "pytest" | etc,
  "build_command": "npm run build" | "",
  "run_command": "npm start" | "python main.py" | etc
}

RULES:
1. Break the project into 3-5 phases (scaffold → core → features → polish → test)
2. Each file must have a clear purpose
3. Dependencies between files must be explicit
4. Include test files in the final phase
5. Keep projects simple and functional
6. Respond ONLY with the JSON object, nothing else
"""

class ProjectFile(BaseModel):
    path: str
    content: str
    description: str = ""

class ProjectPhase(BaseModel):
    phase: int
    name: str
    description: str
    files: list[ProjectFile]

class ProjectPlan(BaseModel):
    project_name: str
    description: str
    language: str
    phases: list[dict]
    dependencies: list[str] = []
    test_command: str = ""
    build_command: str = ""
    run_command: str = ""
    plan_id: str = ""
    created_at: str = ""

class ProjectPlanner:
    def __init__(self, provider: str = "ollama", model: str = "qwen2.5-coder:14b", api_key: str = ""):
        self.provider = provider
        self.model = model
        self.api_key = api_key

    async def plan(self, prompt: str) -> ProjectPlan:
        messages = build_messages(PLANNER_SYSTEM_PROMPT, f"Requirements: {prompt}\n\nGenerate a complete project plan as JSON.")
        response = await complete_chat(self.provider, self.model, messages, temperature=0.2, api_key=self.api_key)
        plan_data = self._parse_response(response)
        plan_id = hashlib.md5(prompt.encode()).hexdigest()[:12]
        plan_data["plan_id"] = plan_id
        plan_data["created_at"] = datetime.now().isoformat()
        return ProjectPlan(**plan_data)

    def _parse_response(self, text: str) -> dict:
        json_match = re.search(r'\{.*\}', text.strip(), re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Failed to parse planner response: {text[:200]}")
