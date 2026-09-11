"""Session recording: one screenshot + one trace line per action."""
import base64, json, os, re, time
from pathlib import Path

from . import paths

ACTIONS = {
    "goto_url", "click_at_xy", "type_text", "fill_input", "press_key",
    "scroll", "dispatch_key", "upload_file", "new_tab", "switch_tab",
    "close_tab", "ensure_real_tab",
    "wait", "wait_for_load", "wait_for_element", "wait_for_network_idle",
}

_TEXT_LIMIT = 500
_SETTLE_SECONDS = 0.15

_URL_SECRETS = re.compile(
    r"([?&#](?:code|access_token|id_token|refresh_token|token|assertion"
    r"|client_secret|client_info|session_state|api_?key|sig|signature"
    r"|auth|authorization|password|secret)=)[^&#]+",
    re.IGNORECASE,
)


def _scrub_url(url):
    return _URL_SECRETS.sub(r"\1REDACTED", str(url))


_CTX_JS = (
    "(()=>{const o={url:location.href,title:document.title,"
    "w:innerWidth,h:innerHeight,sx:scrollX,sy:scrollY,dpr:devicePixelRatio};"
    "const e=document.activeElement;"
    "if(e&&e!==document.body&&e!==document.documentElement){"
    "const r=e.getBoundingClientRect();"
    "if(r.width||r.height)o.box={x:r.x,y:r.y,w:r.width,h:r.height};"
    "o.input=String(e.type||e.tagName||'').toLowerCase();}"
    "return o})()"
)


def _recordings_root():
    return paths.workspace_dir() / "recordings"


def _config_path():
    return paths.config_dir() / "recording.json"


def _load_config():
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _env_override():
    raw = os.environ.get("BH_RECORD")
    if raw is None:
        return None
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _marker():
    return _recordings_root() / f".active-{os.environ.get('BU_NAME', 'default')}"


def start_recording(name=None, title=None):
    if _env_override() is False:
        raise RuntimeError("recording disabled by BH_RECORD=0")
    name = name or time.strftime("rec-%Y%m%d-%H%M%S")
    d = _recordings_root() / name
    d.mkdir(parents=True, exist_ok=True)
    meta = {"name": name, "title": title, "started": round(time.time(), 3)}
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    _marker().write_text(str(d), encoding="utf-8")
    print(f"recording to {d}")
    return str(d)


def stop_recording():
    d = recording_dir()
    if d is None:
        print("no active recording")
        return None
    _marker().unlink(missing_ok=True)
    frames = sum(1 for _ in Path(d).glob("*.jpg"))
    print(f"recording saved: {d} ({frames} frames)")
    return d


def recording_dir():
    m = _marker()
    if not m.exists():
        return None
    d = m.read_text(encoding="utf-8").strip()
    return d if Path(d).is_dir() else None


def recordings():
    root = _recordings_root()
    if not root.exists():
        return []
    def modified(path):
        evidence = path / "events.jsonl"
        return evidence.stat().st_mtime if evidence.exists() else path.stat().st_mtime
    found = [p for p in root.iterdir()
             if p.is_dir() and ((p / "meta.json").exists() or (p / "events.jsonl").exists())]
    return [str(p) for p in sorted(found, key=modified, reverse=True)]


def latest_recording():
    found = recordings()
    return found[0] if found else None


def auto_recording_setting():
    override = _env_override()
    if override is not None:
        return override, "BH_RECORD"
    config = _load_config()
    if isinstance(config.get("enabled"), bool):
        return config["enabled"], "config"
    return False, "default"


def set_auto_recording(enabled):
    path = _config_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"enabled": bool(enabled)}) + "\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    if not enabled:
        d = recording_dir()
        if d is not None:
            _marker().unlink(missing_ok=True)


def observe(name, args, kwargs, duration=None):
    """Called after each traced helper succeeds. Never raises."""
    if name not in ACTIONS:
        return
    try:
        if _env_override() is False:
            return
        d = recording_dir()
        if d is None:
            return
        time.sleep(_SETTLE_SECONDS)
        _capture(Path(d), name, args, kwargs, duration)
    except Exception:
        pass


def _capture(d, helper, args=(), kwargs=None, duration=None):
    from . import helpers
    event = {"ts": round(time.time(), 3), "helper": helper}
    if duration is not None:
        event["duration"] = duration
    try:
        event.update(helpers.js(_CTX_JS) or {})
    except Exception:
        pass
    try:
        shot = helpers.cdp("Page.captureScreenshot", format="jpeg", quality=80)
        number = sum(1 for _ in d.glob("*.jpg")) + 1
        data = base64.b64decode(shot["data"])
        while True:
            frame = f"{number:04d}.jpg"
            try:
                with (d / frame).open("xb") as output:
                    output.write(data)
                break
            except FileExistsError:
                number += 1
        event["frame"] = frame
    except Exception:
        pass
    with (d / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
