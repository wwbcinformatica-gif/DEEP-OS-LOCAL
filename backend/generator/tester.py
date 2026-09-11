from core.llm_native import build_messages, complete_chat
from generator.sandbox import CodeSandbox

TEST_GENERATOR_PROMPT = """
You are a Senior QA Engineer. Generate test code for:
- Project: {project_name} ({project_description})
- Language: {language}
- File to test: {file_path}

RULES:
1. Generate COMPLETE, runnable test code
2. For Python: use pytest
3. For JS/TS: use jest or vitest
4. Test all public functions and edge cases
5. Include setup/teardown if needed
6. Output ONLY the test code, no explanations
"""

class ProjectTester:
    def __init__(self, provider: str = "ollama", model: str = "qwen2.5-coder:14b", api_key: str = ""):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.sandbox = CodeSandbox()

    async def generate_tests(self, project_name: str, description: str, language: str, files: list[dict]) -> list[dict]:
        test_files = []
        for file_info in files:
            if file_info.get("status") != "created":
                continue
            file_path = file_info.get("path", "")
            if self._is_test_file(file_path) or self._is_asset(file_path):
                continue

            try:
                messages = build_messages(
                    TEST_GENERATOR_PROMPT.format(
                        project_name=project_name,
                        project_description=description,
                        language=language,
                        file_path=file_path,
                    ),
                    f"Generate tests for {file_path}"
                )
                response = await complete_chat(self.provider, self.model, messages, temperature=0.3, api_key=self.api_key)
                test_content = self._clean_code(response)
                test_path = self._test_path(file_path, language)

                test_files.append({
                    "path": test_path,
                    "content": test_content,
                    "source_file": file_path,
                    "status": "generated",
                })
            except Exception as e:
                test_files.append({
                    "path": f"tests/test_{Path(file_path).name}",
                    "content": "",
                    "source_file": file_path,
                    "status": "error",
                    "error": str(e),
                })

        return test_files

    async def run_tests(self, project_dir: str, test_command: str) -> dict:
        if not test_command:
            return {"status": "skipped", "reason": "No test command specified"}
        try:
            result = await self.sandbox.run_command(test_command, project_dir, timeout=120)
            return {
                "status": "completed",
                "command": test_command,
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "returncode": result.get("returncode", -1),
                "passed": result.get("returncode") == 0,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _test_path(self, file_path: str, language: str) -> str:
        name = Path(file_path).name
        if language == "python":
            return f"tests/test_{name}"
        elif language in ("node", "typescript"):
            stem = Path(name).stem
            return f"tests/{stem}.test.{Path(name).suffix.lstrip('.')}"
        return f"tests/test_{name}"

    def _is_test_file(self, path: str) -> bool:
        return "test" in path.lower() or "spec" in path.lower()

    def _is_asset(self, path: str) -> bool:
        ext = path.split(".")[-1].lower() if "." in path else ""
        return ext in ("json", "md", "css", "html", "yaml", "yml", "toml", "env", "gitignore")

    def _clean_code(self, content: str) -> str:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = lines[1:] if lines[0].startswith("```") else lines
            lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
            content = "\n".join(lines)
        return content.strip()

from pathlib import Path
