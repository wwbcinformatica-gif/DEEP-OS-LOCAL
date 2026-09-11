"""Daemon IPC plumbing. AF_UNIX socket on POSIX, TCP loopback on Windows."""
import asyncio, json, os, re, secrets, socket, subprocess, sys
from pathlib import Path

from . import paths

IS_WINDOWS = sys.platform == "win32"
BH_RUNTIME_DIR = os.environ.get("DA_BROWSER_RUNTIME_DIR")
BH_TMP_DIR = os.environ.get("DA_BROWSER_TMP_DIR")
BH_RUNTIME_DIR_SHARED = os.environ.get("DA_BROWSER_RUNTIME_DIR_SHARED") == "1"
BH_TMP_DIR_SHARED = os.environ.get("DA_BROWSER_TMP_DIR_SHARED") == "1"
_TMP = paths.tmp_dir()
_RUNTIME = paths.ensure_private_dir(Path(BH_RUNTIME_DIR).expanduser().resolve()) if BH_RUNTIME_DIR else paths.runtime_dir()
_TMP.mkdir(parents=True, exist_ok=True)
_RUNTIME.mkdir(parents=True, exist_ok=True)
_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")

_server_token = None


def _check(name):
    if not _NAME_RE.match(name or ""):
        raise ValueError(f"invalid BU_NAME {name!r}: must match [A-Za-z0-9_-]{{1,64}}")
    return name


def _runtime_stem(name):
    _check(name)
    return "da-browser" if BH_RUNTIME_DIR and not BH_RUNTIME_DIR_SHARED else f"da-browser-{name}"


def _tmp_stem(name):
    _check(name)
    return "da-browser" if BH_TMP_DIR and not BH_TMP_DIR_SHARED else f"da-browser-{name}"


def log_path(name):   return _TMP / f"{_tmp_stem(name)}.log"
def pid_path(name):   return _RUNTIME / f"{_runtime_stem(name)}.pid"
def port_path(name):  return _RUNTIME / f"{_runtime_stem(name)}.port"
def _sock_path(name): return _RUNTIME / f"{_runtime_stem(name)}.sock"


def _read_port_file(name):
    try:
        d = json.loads(port_path(name).read_text(encoding="utf-8"))
        return int(d["port"]), d["token"]
    except (FileNotFoundError, ValueError, KeyError, TypeError, OSError):
        return None, None


def sock_addr(name):
    if not IS_WINDOWS:
        return str(_sock_path(name))
    port, _ = _read_port_file(name)
    return f"127.0.0.1:{port}" if port else f"tcp:{_runtime_stem(name)}"


def spawn_kwargs():
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def connect(name, timeout=1.0):
    if not IS_WINDOWS:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(_sock_path(name)))
        return s, None
    port, token = _read_port_file(name)
    if port is None:
        raise FileNotFoundError(str(port_path(name)))
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.settimeout(timeout)
    return s, token


def request(c, token, req):
    if token:
        req = {**req, "token": token}
    c.sendall((json.dumps(req) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = c.recv(1 << 16)
        if not chunk:
            break
        data += chunk
    return json.loads(data or b"{}")


def ping(name, timeout=1.0):
    try:
        c, token = connect(name, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
        return False
    try:
        resp = request(c, token, {"meta": "ping"})
        return isinstance(resp, dict) and resp.get("pong") is True
    except (OSError, ValueError, AttributeError):
        return False
    finally:
        try:
            c.close()
        except OSError:
            pass


def identify(name, timeout=1.0):
    try:
        c, token = connect(name, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
        return None
    try:
        resp = request(c, token, {"meta": "ping"})
        if not isinstance(resp, dict) or resp.get("pong") is not True:
            return None
        pid = resp.get("pid")
        return pid if type(pid) is int and 0 < pid < (1 << 31) else None
    except (OSError, ValueError, AttributeError):
        return None
    finally:
        try:
            c.close()
        except OSError:
            pass


async def serve(name, handler):
    global _server_token
    if not IS_WINDOWS:
        path = str(_sock_path(name))
        if os.path.exists(path):
            os.unlink(path)
        old_umask = os.umask(0o077)
        try:
            server = await asyncio.start_unix_server(handler, path=path)
        finally:
            os.umask(old_umask)
        _server_token = None
        async with server:
            await asyncio.Event().wait()
        return
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    _server_token = secrets.token_hex(32)
    pf = port_path(name)
    tmp = pf.with_name(pf.name + ".tmp")
    tmp.write_text(json.dumps({"port": port, "token": _server_token}), encoding="utf-8")
    os.replace(tmp, pf)
    try:
        async with server:
            await asyncio.Event().wait()
    finally:
        try:
            pf.unlink()
        except FileNotFoundError:
            pass


def expected_token():
    return _server_token


def cleanup_endpoint(name):
    p = _sock_path(name) if not IS_WINDOWS else port_path(name)
    try:
        p.unlink()
    except FileNotFoundError:
        pass
