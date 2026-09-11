from core.llm_native import build_messages, complete_chat

AUTOFIX_PROMPT = """
You are an Expert Debugger. You receive:
1. A file that has errors
2. The compilation/execution error output
3. The file content

Your task: Output the COMPLETE corrected file content.

RULES:
- Fix ALL errors in the file
- Do NOT change functionality, only fix bugs
- Output ONLY the corrected file content
- Preserve the original structure and style
- If the error is in a dependency, add a comment suggesting the fix
"""

class AutoFixLoop:
    def __init__(self, provider: str = "ollama", model: str = "qwen2.5-coder:14b", api_key: str = "", max_attempts: int = 3):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.max_attempts = max_attempts

    async def fix_file(self, file_path: str, content: str, error_output: str, language: str) -> dict:
        for attempt in range(1, self.max_attempts + 1):
            try:
                messages = build_messages(
                    AUTOFIX_PROMPT,
                    f"Language: {language}\n\nFile: {file_path}\n\nError Output:\n{error_output[-2000:]}\n\nCurrent Content:\n{content[:5000]}"
                )
                response = await complete_chat(self.provider, self.model, messages, temperature=0.2, api_key=self.api_key)
                fixed = self._extract_code(response)
                if not fixed:
                    continue

                validation = await self._validate_syntax(fixed, language)
                if validation.get("valid"):
                    return {
                        "status": "fixed",
                        "content": fixed,
                        "attempts": attempt,
                        "validation": validation,
                    }

                error_output = validation.get("error", "Syntax error persists")
                content = fixed

            except Exception:
                continue

        return {"status": "failed", "content": content, "attempts": self.max_attempts, "error": "Max fix attempts reached"}

    async def _validate_syntax(self, content: str, language: str) -> dict:
        if language == "python":
            try:
                compile(content, "<string>", "exec")
                return {"valid": True}
            except SyntaxError as e:
                return {"valid": False, "error": str(e)}
        return {"valid": True}

    def _extract_code(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return text

    async def fix_project(self, results: list[dict], language: str) -> list[dict]:
        fixed_results = []
        for result in results:
            if result.get("status") == "error":
                file_path = result.get("path", "")
                content = result.get("content", "")
                error = result.get("error", "")
                fix_result = await self.fix_file(file_path, content, error, language)
                fixed_results.append({
                    **result,
                    "fix_attempted": True,
                    "fix_status": fix_result["status"],
                    "content": fix_result["content"],
                })
            else:
                fixed_results.append(result)
        return fixed_results
