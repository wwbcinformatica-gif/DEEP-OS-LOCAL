"""Admin/diagnostics for browser module."""
import json, os, platform, subprocess, sys, time
from pathlib import Path

from . import ipc as ipc
from . import paths


def daemon_alive(name=None):
    return ipc.ping(name or "default", timeout=1.0)


def ensure_daemon(wait=60.0, name=None, env=None):
    """Idempotent daemon startup with self-healing."""
    if daemon_alive(name):
        try:
            s, token = ipc.connect(name or "default", timeout=3.0)
            resp = ipc.request(s, token, {"method": "Target.getTargets", "params": {}})
            if "result" in resp:
                return
        except Exception:
            pass
        restart_daemon(name)
    import sys
    for _ in range(3):
        e = {**os.environ, **({"BU_NAME": name} if name else {}), **(env or {})}
        try:
            stderr_sink = open(ipc.log_path(name or "default"), "ab")
        except OSError:
            stderr_sink = subprocess.DEVNULL
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        p = subprocess.Popen(
            [sys.executable, "-m", "backend.browser.daemon"],
            env=e, cwd=project_root,
            stdout=subprocess.DEVNULL, stderr=stderr_sink, **ipc.spawn_kwargs(),
        )
        if stderr_sink is not subprocess.DEVNULL:
            stderr_sink.close()
        deadline = time.time() + wait
        while time.time() < deadline:
            if daemon_alive(name):
                return
            if p.poll() is not None:
                break
            time.sleep(0.2)
        raise RuntimeError(f"daemon {name or 'default'} didn't come up")


def restart_daemon(name=None):
    import signal
    name = name or "default"
    pid_path = str(ipc.pid_path(name))
    daemon_pid = ipc.identify(name, timeout=5.0)
    if daemon_pid is not None:
        try:
            c, token = ipc.connect(name, timeout=5.0)
            ipc.request(c, token, {"meta": "shutdown"})
            c.close()
        except Exception:
            pass
        for _ in range(30):
            try:
                os.kill(daemon_pid, 0)
                time.sleep(0.2)
            except (ProcessLookupError, OSError):
                break
        else:
            try:
                os.kill(daemon_pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
    ipc.cleanup_endpoint(name)
    try:
        os.unlink(pid_path)
    except FileNotFoundError:
        pass


def run_doctor():
    """Read-only diagnostics."""
    chrome = _chrome_running()
    daemon = daemon_alive()
    print("browser-harness doctor")
    print(f"  platform    {platform.system()} {platform.release()}")
    print(f"  python      {sys.version.split()[0]}")
    print(f"  chrome      {'ok' if chrome else 'FAIL - start chrome/edge'}")
    print(f"  daemon      {'ok' if daemon else 'FAIL'}")
    return 0 if (chrome and daemon) else 1


def _chrome_running():
    system = platform.system()
    try:
        if system == "Windows":
            out = subprocess.check_output(["tasklist"], text=True, errors="replace", timeout=5)
            names = ("chrome.exe", "msedge.exe", "chromium.exe", "brave.exe")
        else:
            out = subprocess.check_output(["ps", "-A", "-o", "comm="], text=True, errors="replace", timeout=5)
            names = ("Google Chrome", "chrome", "chromium", "Microsoft Edge", "msedge")
        return any(n.lower() in out.lower() for n in names)
    except Exception:
        return False
