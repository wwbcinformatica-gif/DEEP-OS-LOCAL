import asyncio
import json
import re
import shutil
import tempfile
from pathlib import Path

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07')

def strip_ansi(text: str) -> str:
    return ANSI_RE.sub('', text)


class CodeSandbox:
    def __init__(self, work_dir: str = ""):
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="wbc_sandbox_"))

    async def execute(self, command: str, cwd: str = "", timeout: int = 30) -> dict:
        workdir = Path(cwd) if cwd else self.work_dir
        if not workdir.exists():
            return {"stdout": "", "stderr": "Directory not found", "returncode": -1}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workdir),
                shell=True,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return {
                    "stdout": strip_ansi((stdout or b"").decode("utf-8", errors="replace")[-10000:]),
                    "stderr": strip_ansi((stderr or b"").decode("utf-8", errors="replace")[-5000:]),
                    "returncode": proc.returncode or 0,
                }
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {"stdout": "", "stderr": f"Timeout: command exceeded {timeout}s", "returncode": 124}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "returncode": -1}

    async def install_dependencies(self, project_dir: str, language: str, dependencies: list) -> dict:
        if not dependencies:
            return {"stdout": "No dependencies to install", "stderr": "", "returncode": 0}

        if language == "python":
            req_file = Path(project_dir) / "requirements.txt"
            req_file.write_text("\n".join(dependencies), encoding="utf-8")
            return await self.execute("pip install -r requirements.txt 2>&1", cwd=project_dir, timeout=120)
        elif language in ("node", "typescript"):
            pkg = {"name": "temp-project", "version": "1.0.0", "dependencies": {}}
            for dep in dependencies:
                if ":" in dep:
                    name, ver = dep.split(":", 1)
                    pkg["dependencies"][name.strip()] = ver.strip()
                else:
                    pkg["dependencies"][dep] = "*"
            pkg_file = Path(project_dir) / "package.json"
            pkg_file.write_text(json.dumps(pkg, indent=2), encoding="utf-8")
            return await self.execute("npm install 2>&1", cwd=project_dir, timeout=120)
        return {"stdout": f"Unknown language: {language}", "stderr": "", "returncode": 0}

    async def run_command(self, cmd: str, project_dir: str, timeout: int = 60) -> dict:
        return await self.execute(cmd, cwd=project_dir, timeout=timeout)

    async def cleanup(self):
        if self.work_dir and self.work_dir.exists():
            shutil.rmtree(str(self.work_dir), ignore_errors=True)
