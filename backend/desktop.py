"""Windows 离线桌面入口。"""
from __future__ import annotations

import os
import socket
import sys
import threading
from pathlib import Path


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


root = resource_root()
frozen = hasattr(sys, "_MEIPASS")
frontend_dir = root / "frontend" if frozen else root / "frontend" / "dist"
icons_dir = root / "resources" / "icons" if frozen else root / "data" / "icons"
fixed_runtime = root / "WebView2" if frozen else root / "vendor" / "WebView2"
os.environ["DATA_BACKEND"] = "json"
os.environ["OFFLINE_DATA_DIR"] = str(root / "release_data")
os.environ["ICONS_DIR"] = str(icons_dir)
if fixed_runtime.exists():
    os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = str(fixed_runtime)

import uvicorn  # noqa: E402
import webview  # noqa: E402
from app.desktop_main import SESSION_TOKEN, app, mount_frontend  # noqa: E402


def main() -> None:
    if "--smoke-test" in sys.argv or "--release-smoke-test" in sys.argv:
        from app.data import db
        db.init_schema()
        if not (frontend_dir / "index.html").is_file():
            raise RuntimeError("前端资源缺失")
        if "--release-smoke-test" in sys.argv and not (root / "WebView2" / "msedgewebview2.exe").is_file():
            raise RuntimeError("固定版 WebView2 Runtime 缺失")
        return
    mount_frontend(str(frontend_dir))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    webview.create_window("明日方舟离线面板", f"http://127.0.0.1:{port}/?token={SESSION_TOKEN}", width=1440, height=940, min_size=(1080, 720))
    webview.start(gui="edgechromium", private_mode=False)
    server.should_exit = True


if __name__ == "__main__": main()
