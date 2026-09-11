from core.agent_config import (
    AgentConfig,
    TerminalConfig,
    reset_config_cache,
)


def test_default_config():
    cfg = AgentConfig()
    assert cfg.model.default == "qwen2.5-coder:14b"
    assert cfg.model.provider == "custom"
    assert cfg.agent.max_turns == 15
    assert cfg.terminal.backend == "local"


def test_model_config_override():
    cfg = AgentConfig()
    cfg.model.default = "gpt-4"
    cfg.model.provider = "openai"
    assert cfg.model.default == "gpt-4"
    assert cfg.model.provider == "openai"


def test_agent_loop_config():
    cfg = AgentConfig()
    assert cfg.agent.max_tool_steps == 100
    assert cfg.agent.toolset == "agent"


def test_terminal_config_defaults():
    cfg = TerminalConfig()
    assert cfg.backend == "local"
    assert cfg.timeout == 600
    assert "ls" in cfg.allowed_commands


def test_reset_config_cache():
    reset_config_cache()
    cfg1 = AgentConfig()
    cfg2 = AgentConfig()
    assert cfg1 is not cfg2


def test_memory_config():
    cfg = AgentConfig()
    assert cfg.memory.enabled is True
    assert cfg.memory.max_namespaces == 10
