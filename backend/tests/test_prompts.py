from core.prompts import (
    MOOD_INSTRUCTIONS,
    TOOL_SYSTEM_PROMPT,
    build_compact_tool_prompt,
)


def test_mood_instructions_have_all_keys():
    expected = {"descontraido", "serio", "bravo", "jarvis", "opencode"}
    assert expected.issubset(MOOD_INSTRUCTIONS.keys())


def test_tool_system_prompt_format():
    result = TOOL_SYSTEM_PROMPT.format(
        root_info="C:\\projeto",
        personality="Voce e um assistente.",
    )
    assert "C:\\projeto" in result
    assert "assistente" in result


def test_build_compact_tool_prompt():
    result = build_compact_tool_prompt(root="C:\\projeto", path="src")
    assert "C:\\projeto" in result
    assert "read" in result
    assert "write" in result
    assert "bash" in result
