from pathlib import Path

root = Path(SPECPATH)
datas = [
    (str(root / "frontend" / "dist"), "frontend"),
    (str(root / "release_data"), "release_data"),
    (str(root / "data" / "icons"), "resources/icons"),
]
runtime = root / "vendor" / "WebView2"
if runtime.exists():
    datas.append((str(runtime), "WebView2"))

a = Analysis([str(root / "backend" / "desktop.py")], pathex=[str(root / "backend")], binaries=[], datas=datas,
             hiddenimports=["app.data.json_db", "webview.platforms.edgechromium", "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto"],
             hookspath=[], runtime_hooks=[], excludes=["tkinter", "sqlalchemy", "pymysql", "app.data.mysql_db"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ArknightsOfflinePanel", console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="ArknightsOfflinePanel")
