"""数据访问门面：开发环境 MySQL，桌面版只读 JSON。"""
from importlib import import_module

from app.config import settings

_backend_name = "app.data.json_db" if settings.DATA_BACKEND == "json" else "app.data.mysql_db"
_backend = import_module(_backend_name)

for _name in dir(_backend):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_backend, _name)
