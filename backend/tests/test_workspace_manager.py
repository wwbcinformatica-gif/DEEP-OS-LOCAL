from pathlib import Path

from core.workspace_manager import WorkspaceEntry, WorkspaceManager


def test_workspace_entry_to_dict():
    entry = WorkspaceEntry("test", "/tmp/test")
    d = entry.to_dict()
    assert d["name"] == "test"
    assert d["path"] == "/tmp/test"


def test_workspace_entry_from_dict():
    entry = WorkspaceEntry.from_dict({"name": "x", "path": "/x", "last_opened": "2024-01-01"})
    assert entry.name == "x"
    assert entry.path == "/x"
    assert entry.last_opened == "2024-01-01"


def test_validate_workspace(tmp_path: Path):
    wm = WorkspaceManager()
    result = wm.validate_workspace(str(tmp_path))
    assert result["valid"] is True
    assert result["resolved"] == str(tmp_path.resolve())


def test_validate_workspace_nonexistent():
    wm = WorkspaceManager()
    result = wm.validate_workspace(r"C:\NaoExiste12345")
    assert result["valid"] is False


def test_validate_workspace_file(tmp_path: Path):
    f = tmp_path / "arquivo.txt"
    f.write_text("conteudo")
    wm = WorkspaceManager()
    result = wm.validate_workspace(str(f))
    assert result["valid"] is False


def test_set_workspace(tmp_path: Path):
    wm = WorkspaceManager()
    wm._config_loaded = True
    result = wm.set_workspace(str(tmp_path))
    assert result["success"] is True
    assert result["workspace"] == str(tmp_path.resolve())


def test_set_workspace_invalid():
    wm = WorkspaceManager()
    wm._config_loaded = True
    result = wm.set_workspace(r"C:\NaoExiste12345")
    assert result["success"] is False


def test_get_workspace_default():
    wm = WorkspaceManager()
    ws = wm.get_workspace()
    assert ws is not None
    assert ws.exists()


def test_get_workspace_name(tmp_path: Path):
    wm = WorkspaceManager()
    wm._config_loaded = True
    wm.set_workspace(str(tmp_path))
    assert wm.get_workspace_name() == tmp_path.name
