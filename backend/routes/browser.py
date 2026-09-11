"""Browser automation API routes for DEEP-OS."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import os

router = APIRouter(prefix="/browser", tags=["browser"])


class NavigateRequest(BaseModel):
    url: str


class ClickRequest(BaseModel):
    x: float
    y: float
    button: str = "left"
    clicks: int = 1


class TypeRequest(BaseModel):
    text: str


class FillRequest(BaseModel):
    selector: str
    text: str
    clear_first: bool = True
    timeout: float = 0.0


class KeyRequest(BaseModel):
    key: str
    modifiers: int = 0


class ScrollRequest(BaseModel):
    x: float = 400
    y: float = 300
    dy: int = -300
    dx: int = 0


class JsRequest(BaseModel):
    expression: str
    target_id: Optional[str] = None


class TabRequest(BaseModel):
    target_id: Optional[str] = None
    activate: bool = False


class NewTabRequest(BaseModel):
    url: str = "about:blank"


class UploadRequest(BaseModel):
    selector: str
    path: str


class ScreenshotRequest(BaseModel):
    full: bool = False
    max_dim: Optional[int] = None


@router.get("/status")
async def browser_status():
    """Check browser daemon status."""
    from browser.admin import daemon_alive
    alive = daemon_alive()
    return {"status": "connected" if alive else "disconnected", "daemon": alive}


@router.post("/navigate")
async def browser_navigate(req: NavigateRequest):
    """Navigate to URL."""
    from backend.browser.helpers import goto_url
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    result = goto_url(req.url)
    return {"result": result}


@router.get("/page-info")
async def browser_page_info():
    """Get current page info (url, title, dimensions)."""
    from backend.browser.helpers import page_info
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    return page_info()


@router.post("/click")
async def browser_click(req: ClickRequest):
    """Click at coordinates."""
    from backend.browser.helpers import click_at_xy
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    click_at_xy(req.x, req.y, req.button, req.clicks)
    return {"status": "clicked", "x": req.x, "y": req.y}


@router.post("/type")
async def browser_type(req: TypeRequest):
    """Type text."""
    from backend.browser.helpers import type_text
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    type_text(req.text)
    return {"status": "typed"}


@router.post("/fill")
async def browser_fill(req: FillRequest):
    """Fill input field (framework-compatible)."""
    from backend.browser.helpers import fill_input
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    fill_input(req.selector, req.text, req.clear_first, req.timeout)
    return {"status": "filled"}


@router.post("/key")
async def browser_key(req: KeyRequest):
    """Press key."""
    from backend.browser.helpers import press_key
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    press_key(req.key, req.modifiers)
    return {"status": "pressed", "key": req.key}


@router.post("/scroll")
async def browser_scroll(req: ScrollRequest):
    """Scroll."""
    from backend.browser.helpers import scroll
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    scroll(req.x, req.y, req.dy, req.dx)
    return {"status": "scrolled"}


@router.post("/js")
async def browser_js(req: JsRequest):
    """Execute JavaScript."""
    from backend.browser.helpers import js
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    result = js(req.expression, req.target_id)
    return {"result": result}


@router.get("/screenshot")
async def browser_screenshot(full: bool = False, max_dim: Optional[int] = None):
    """Capture screenshot."""
    from backend.browser.helpers import capture_screenshot
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    path = capture_screenshot(full=full, max_dim=max_dim)
    return FileResponse(path, media_type="image/png")


@router.get("/tabs")
async def browser_tabs():
    """List open tabs."""
    from backend.browser.helpers import list_tabs
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    return {"tabs": list_tabs()}


@router.get("/tab/current")
async def browser_current_tab():
    """Get current tab."""
    from backend.browser.helpers import current_tab
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    return current_tab()


@router.post("/tab/new")
async def browser_new_tab(req: NewTabRequest):
    """Open new tab."""
    from backend.browser.helpers import new_tab
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    target_id = new_tab(req.url)
    return {"target_id": target_id}


@router.post("/tab/switch")
async def browser_switch_tab(req: TabRequest):
    """Switch tab."""
    from backend.browser.helpers import switch_tab
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    if not req.target_id:
        raise HTTPException(status_code=400, detail="target_id required")
    session_id = switch_tab(req.target_id, req.activate)
    return {"session_id": session_id}


@router.post("/tab/close")
async def browser_close_tab(req: TabRequest):
    """Close tab."""
    from backend.browser.helpers import close_tab
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    close_tab(req.target_id)
    return {"status": "closed"}


@router.post("/upload")
async def browser_upload(req: UploadRequest):
    """Upload file to input."""
    from backend.browser.helpers import upload_file
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    upload_file(req.selector, req.path)
    return {"status": "uploaded"}


@router.post("/recording/start")
async def browser_recording_start(name: Optional[str] = None, title: Optional[str] = None):
    """Start session recording."""
    from backend.browser.recorder import start_recording
    path = start_recording(name, title)
    return {"path": path}


@router.post("/recording/stop")
async def browser_recording_stop():
    """Stop session recording."""
    from backend.browser.recorder import stop_recording
    path = stop_recording()
    return {"path": path}


@router.get("/recording/status")
async def browser_recording_status():
    """Get recording status."""
    from backend.browser.recorder import recording_dir, auto_recording_setting
    active = recording_dir()
    enabled, source = auto_recording_setting()
    return {"active": active, "auto_enabled": enabled, "source": source}


@router.get("/doctor")
async def browser_doctor(ensure: bool = False):
    """Run diagnostics."""
    from backend.browser.admin import run_doctor, _chrome_running, daemon_alive, ensure_daemon
    if ensure:
        try:
            ensure_daemon(wait=30)
        except Exception:
            pass
    chrome = _chrome_running()
    daemon = daemon_alive()
    return {
        "chrome": chrome,
        "daemon": daemon,
        "status": "healthy" if (chrome and daemon) else "unhealthy",
    }


# ── Novas rotas do browser-harness ──────────────────────────────────────────────

@router.get("/network-requests")
async def browser_network_requests():
    """Get network requests history."""
    from backend.browser.helpers import cdp
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    result = cdp("Network.getResponseBody", requestId="")
    return {"requests": result}


@router.post("/print-pdf")
async def browser_print_pdf(url: str = "", path: str = ""):
    """Print page as PDF."""
    from backend.browser.helpers import cdp, goto_url
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    if url:
        goto_url(url)
    result = cdp("Page.printToPDF")
    if path and "data" in result:
        import base64
        with open(path, "wb") as f:
            f.write(base64.b64decode(result["data"]))
        return {"path": path, "status": "saved"}
    return {"status": "printed"}


@router.post("/handle-dialog")
async def browser_handle_dialog(accept: bool = True, prompt_text: str = ""):
    """Handle JavaScript dialog (alert, confirm, prompt)."""
    from backend.browser.helpers import cdp
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    if accept:
        cdp("Page.handleJavaScriptDialog", promptText=prompt_text)
    else:
        cdp("Page.handleJavaScriptDialog")
    return {"status": "handled", "accepted": accept}


@router.get("/cookies")
async def browser_get_cookies(domain: str = ""):
    """Get cookies for domain."""
    from backend.browser.helpers import cdp
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    result = cdp("Network.getCookies", urls=[f"https://{domain}"] if domain else [])
    return {"cookies": result.get("cookies", [])}


@router.post("/cookies")
async def browser_set_cookie(name: str, value: str, domain: str, path: str = "/"):
    """Set a cookie."""
    from backend.browser.helpers import cdp
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    cdp("Network.setCookie", name=name, value=value, domain=domain, path=path)
    return {"status": "set"}


@router.post("/drag")
async def browser_drag(x: float, y: float, target_x: float, target_y: float):
    """Drag element from (x,y) to (target_x, target_y)."""
    from backend.browser.helpers import cdp
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
    cdp("Input.dispatchMouseEvent", type="mouseMoved", x=target_x, y=target_y, button="left")
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=target_x, y=target_y, button="left", clickCount=1)
    return {"status": "dragged", "from": [x, y], "to": [target_x, target_y]}


@router.post("/viewport")
async def browser_set_viewport(width: int = 1920, height: int = 1080):
    """Set viewport size."""
    from backend.browser.helpers import cdp
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    cdp("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
    return {"status": "viewport_set", "width": width, "height": height}


@router.get("/download/status")
async def browser_download_status():
    """Check download status."""
    from backend.browser.helpers import cdp
    from backend.browser.admin import ensure_daemon
    ensure_daemon()
    result = cdp("Browser.downloadWillBegin")
    return {"download": result}
