from pathlib import Path

import pytest
from fastapi import HTTPException


def test_resolve_path_within_root(tmp_path: Path):
    from tools.explorer import resolve_path
    sub = tmp_path / "sub"
    sub.mkdir()
    result = resolve_path("sub", root=str(tmp_path))
    assert result == sub.resolve()


def test_resolve_path_outside_root(tmp_path: Path):
    from tools.explorer import resolve_path
    with pytest.raises(HTTPException) as exc:
        resolve_path("..", root=str(tmp_path))
    assert exc.value.status_code == 403


def test_resolve_path_absolute_breaking(tmp_path: Path):
    from tools.explorer import resolve_path
    with pytest.raises(HTTPException):
        resolve_path("C:\\Windows", root=str(tmp_path))
