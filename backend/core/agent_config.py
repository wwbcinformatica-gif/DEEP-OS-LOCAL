"""
Agent Configuration Schema
==========================
Inspired by Hermes Agent's DEFAULT_CONFIG structure.
Centralizes all agent-related settings in one place.

Usage:
    from core.agent_config import AgentConfig, load_agent_config

    cfg = load_agent_config()
    model = cfg.model.default
    tools = resolve_toolset(cfg.agent.toolset)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger("wbc.agent_config")


# ---------------------------------------------------------------------------
# Config Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    """AI model and provider configuration."""

    default: str = "qwen2.5-coder:14b"
    provider: str = "custom"
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 300


@dataclass
class AgentLoopConfig:
    """Agent execution loop settings."""

    max_turns: int = 15
    max_tool_steps: int = 100
    toolset: str = "agent"  # default toolset name from toolsets.py
    image_input_mode: str = "text"  # "auto", "native", "text"
    system_prompt: str = ""
    personality: str = "opencode"
    max_iterations: int = 10  # safety limit for internal loops


@dataclass
class TerminalConfig:
    """Terminal execution backend settings."""

    backend: str = "local"  # "local", "docker", "ssh"
    timeout: int = 600
    cwd: str = "."
    allowed_commands: list[str] | None = None

    def __post_init__(self):
        if self.allowed_commands is None:
            self.allowed_commands = [
                "ls", "dir", "cat", "type", "echo", "pwd",
                "cd", "mkdir", "rmdir", "copy", "move", "del",
                "git", "npm", "node", "python", "pip", "uv",
                "curl", "wget", "find", "grep", "rg",
            ]


@dataclass
class MemoryConfig:
    """Memory and reflection system settings."""

    enabled: bool = True
    max_namespaces: int = 10
    reflection_enabled: bool = True
    vector_memory_enabled: bool = True


@dataclass
class SkillsConfig:
    """Skill loading and discovery settings."""

    enabled: bool = True
    external_dirs: list[str] = field(default_factory=list)
    guard_agent_created: bool = False


@dataclass
class DisplayConfig:
    """CLI and UI display settings."""

    compact: bool = False
    language: str = "pt-BR"
    show_tool_calls: bool = True
    show_reasoning: bool = True
    streaming: bool = True


@dataclass
class SecurityConfig:
    """Security and sandbox settings."""

    sandbox_enabled: bool = False
    redact_secrets: bool = True
    allowlist_commands: bool = False
    max_file_read_chars: int = 100000
    max_tool_output_bytes: int = 50000


@dataclass
class SpiralMemoryConfig:
    """DEEP-OS spiral memory settings."""

    enabled: bool = True
    interval: int = 4
    keeper_provider: str = ""
    keeper_model: str = ""


@dataclass
class AgentConfig:
    """Top-level agent configuration."""

    model: ModelConfig = field(default_factory=ModelConfig)
    agent: AgentLoopConfig = field(default_factory=AgentLoopConfig)
    terminal: TerminalConfig = field(default_factory=TerminalConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    spiral_memory: SpiralMemoryConfig = field(default_factory=SpiralMemoryConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

# Simple in-memory cache
_current_config: AgentConfig | None = None


def _resolve_proj_root() -> Path:
    """Resolve project root (3 levels up from backend/core/)."""
    return Path(__file__).resolve().parent.parent.parent


def _default_config_path() -> Path:
    return _resolve_proj_root() / "config.yaml"


def load_agent_config(path: str | None = None) -> AgentConfig:
    """Load agent configuration, merging defaults with YAML if it exists.

    Priority: defaults < config.yaml < environment variables.
    """
    global _current_config
    if _current_config is not None:
        return _current_config

    cfg = AgentConfig()

    config_path = Path(path) if path else _default_config_path()

    # Attempt to load and merge YAML over defaults
    if config_path.exists():
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            _merge_yaml(cfg, raw)
        except Exception as e:
            _log.warning("Erro ao carregar config.yaml: %s", e)

    # Environment variable overrides
    _apply_env_overrides(cfg)

    _current_config = cfg
    return cfg


def _merge_yaml(cfg: AgentConfig, raw: dict) -> None:
    """Deep-merge a parsed YAML dict into the AgentConfig."""
    if "model" in raw and isinstance(raw["model"], dict):
        m = raw["model"]
        if "default" in m:
            cfg.model.default = str(m["default"])
        if "provider" in m:
            cfg.model.provider = str(m["provider"])
        if "base_url" in m:
            cfg.model.base_url = str(m["base_url"])
        if "api_key" in m:
            cfg.model.api_key = str(m["api_key"])
        if "temperature" in m:
            cfg.model.temperature = float(m["temperature"])
        if "max_tokens" in m:
            cfg.model.max_tokens = int(m["max_tokens"])

    if "agent" in raw and isinstance(raw["agent"], dict):
        a = raw["agent"]
        if "max_turns" in a:
            cfg.agent.max_turns = int(a["max_turns"])
        if "max_tool_steps" in a:
            cfg.agent.max_tool_steps = int(a["max_tool_steps"])
        if "max_iterations" in a:
            cfg.agent.max_iterations = int(a["max_iterations"])
        if "toolset" in a:
            cfg.agent.toolset = str(a["toolset"])
        if "personality" in a:
            cfg.agent.personality = str(a["personality"])

    if "terminal" in raw and isinstance(raw["terminal"], dict):
        t = raw["terminal"]
        if "backend" in t:
            cfg.terminal.backend = str(t["backend"])
        if "timeout" in t:
            cfg.terminal.timeout = int(t["timeout"])

    if "memory" in raw and isinstance(raw["memory"], dict):
        mem = raw["memory"]
        if "enabled" in mem:
            cfg.memory.enabled = bool(mem["enabled"])
        if "reflection_enabled" in mem:
            cfg.memory.reflection_enabled = bool(mem["reflection_enabled"])
        if "vector_memory_enabled" in mem:
            cfg.memory.vector_memory_enabled = bool(mem["vector_memory_enabled"])

    if "skills" in raw and isinstance(raw["skills"], dict):
        sk = raw["skills"]
        if "enabled" in sk:
            cfg.skills.enabled = bool(sk["enabled"])
        if "external_dirs" in sk:
            cfg.skills.external_dirs = list(sk["external_dirs"])
        if "guard_agent_created" in sk:
            cfg.skills.guard_agent_created = bool(sk["guard_agent_created"])

    if "display" in raw and isinstance(raw["display"], dict):
        d = raw["display"]
        if "compact" in d:
            cfg.display.compact = bool(d["compact"])
        if "language" in d:
            cfg.display.language = str(d["language"])
        if "show_tool_calls" in d:
            cfg.display.show_tool_calls = bool(d["show_tool_calls"])
        if "streaming" in d:
            cfg.display.streaming = bool(d["streaming"])

    if "security" in raw and isinstance(raw["security"], dict):
        s = raw["security"]
        if "sandbox_enabled" in s:
            cfg.security.sandbox_enabled = bool(s["sandbox_enabled"])
        if "redact_secrets" in s:
            cfg.security.redact_secrets = bool(s["redact_secrets"])
        if "allowlist_commands" in s:
            cfg.security.allowlist_commands = bool(s["allowlist_commands"])

    if "spiral_memory" in raw and isinstance(raw["spiral_memory"], dict):
        sm = raw["spiral_memory"]
        if "enabled" in sm:
            cfg.spiral_memory.enabled = bool(sm["enabled"])
        if "interval" in sm:
            cfg.spiral_memory.interval = int(sm["interval"])
        if "keeper_provider" in sm:
            cfg.spiral_memory.keeper_provider = str(sm["keeper_provider"])
        if "keeper_model" in sm:
            cfg.spiral_memory.keeper_model = str(sm["keeper_model"])


def _apply_env_overrides(cfg: AgentConfig) -> None:
    """Apply environment variable overrides."""
    env = os.environ

    if "LLM_PROVIDER" in env:
        cfg.model.provider = env["LLM_PROVIDER"]
    if "LLM_API_BASE" in env:
        cfg.model.base_url = env["LLM_API_BASE"]
    if "LLM_API_KEY" in env:
        cfg.model.api_key = env["LLM_API_KEY"]
    if "LLM_MODEL" in env:
        cfg.model.default = env["LLM_MODEL"]
    if "LLM_TEMPERATURE" in env:
        cfg.model.temperature = float(env["LLM_TEMPERATURE"])

    if "AGENT_MAX_TURNS" in env:
        cfg.agent.max_turns = int(env["AGENT_MAX_TURNS"])
    if "AGENT_TOOLSET" in env:
        cfg.agent.toolset = env["AGENT_TOOLSET"]
    if "AGENT_PERSONALITY" in env:
        cfg.agent.personality = env["AGENT_PERSONALITY"]

    if "TERMINAL_BACKEND" in env:
        cfg.terminal.backend = env["TERMINAL_BACKEND"]
    if "TERMINAL_TIMEOUT" in env:
        cfg.terminal.timeout = int(env["TERMINAL_TIMEOUT"])


def reset_config_cache() -> None:
    """Clear cached config (e.g., after writing config.yaml)."""
    global _current_config
    _current_config = None
