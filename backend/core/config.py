import os
from pathlib import Path

# ─── Projeto raiz (padrão — sobrescrito pelo WorkspaceManager) ─────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_DIR = PROJECT_ROOT
EXPLORER_ROOT = PROJECT_ROOT

# ─── Diretórios de dados (sempre relativos ao PROJECT_ROOT) ────────────
DATA_DIR = PROJECT_ROOT / "data"
BRAIN_DIR = DATA_DIR / "brain"
MEMORY_DIR = DATA_DIR / "memory"
faq_path = DATA_DIR / "faq.json"
DB_PATH = DATA_DIR / "interactions.db"
OPENCLAUDE_DIR = PROJECT_ROOT / "openclaude"

BRAIN_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
(MEMORY_DIR / "conversations").mkdir(exist_ok=True)
(MEMORY_DIR / "project_knowledge").mkdir(exist_ok=True)
(MEMORY_DIR / "reflections").mkdir(exist_ok=True)
(MEMORY_DIR / "preferences").mkdir(exist_ok=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENCODE_API_KEY = os.environ.get("OPENCODE_API_KEY", "")
OPENCLAUDE_API_KEY = os.environ.get("OPENCLAUDE_API_KEY", "")
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
OPENCLAUDE_BASE_URL = os.environ.get("OPENCLAUDE_BASE_URL", "http://localhost:4000/api/v1")


# ─── WorkspaceManager dinâmico ─────────────────────────────────────────
# Usar get_base_dir() quando precisar do workspace ativo (pode mudar em
# runtime). Usar BASE_DIR (constante) só para paths do projeto.

def get_base_dir() -> Path:
    """Retorna o workspace ativo. Consulta o WorkspaceManager."""
    from core.workspace_manager import WorkspaceManager
    return WorkspaceManager.get_instance().get_workspace()

def get_explorer_root() -> Path:
    """Alias para get_base_dir() — workspace ativo para o explorador."""
    return get_base_dir()

TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".py", ".ts", ".tsx", ".js", ".jsx",
    ".html", ".css", ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".csv", ".xml", ".sql", ".sh", ".bat", ".env", ".gitignore",
    ".log", ".dockerfile", ".editorconfig", ".pyi", ".rasi", ".conf",
    ".rs", ".go", ".java", ".cpp", ".hpp", ".c", ".h", ".rb",
    ".php", ".swift", ".kt", ".scala", ".ex", ".exs", ".vue",
    ".svelte", ".astro", ".mjs", ".cjs"
}

ALLOWED_BASH = {
    "ls", "dir", "cat", "type", "echo", "pwd", "whoami", "date",
    "time", "python", "py", "node", "npm", "git", "ollama", "curl",
    "ver", "systeminfo", "cd", "mkdir", "copy", "move", "del",
    "ren", "find", "code", "start", "pip", "npx", "cargo", "go",
    "rustc", "clang", "gcc", "make", "cmake", "tree", "grep", "rg"
}

MODEL_ROUTING = {
    "personality": {"provider": "groq", "model": "openai/gpt-oss-20b"},
    "coding": {"provider": "groq", "model": "openai/gpt-oss-120b"},
    "reasoning": {"provider": "groq", "model": "openai/gpt-oss-120b"},
    "premium": {"provider": "openai", "model": "gpt-4o"},
    "analysis": {"provider": "gemini", "model": "gemini-1.5-pro"},
}
