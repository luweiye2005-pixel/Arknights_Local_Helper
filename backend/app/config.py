"""应用配置。"""
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """应用配置。"""

    GAMEDATA_DIR: str = "../data/gamedata"
    WIKI_DIR: str = "../data/wiki"
    RELIC_PATCH_FILE: str = "../data/patches/relic_modifiers.json"
    RELIC_CONDITIONS_FILE: str = "../data/patches/relic_conditions.json"
    OUTER_BUFFS_FILE: str = "../data/patches/outer_buffs.json"
    ICONS_DIR: str = "../data/icons"
    DATA_BACKEND: str = "mysql"
    OFFLINE_DATA_DIR: str = "../release_data"

    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "arknights"
    MYSQL_PASSWORD: str = "your_password"
    MYSQL_DATABASE: str = "arknights_helper"

    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": (REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }

    def resolve_path(self, relative: str) -> Path:
        p = Path(relative)
        if p.is_absolute():
            return p
        return (BACKEND_DIR / p).resolve()

    @property
    def gamedata_path(self) -> Path:
        return self.resolve_path(self.GAMEDATA_DIR)

    @property
    def wiki_path(self) -> Path:
        return self.resolve_path(self.WIKI_DIR)

    @property
    def relic_patch_path(self) -> Path:
        return self.resolve_path(self.RELIC_PATCH_FILE)

    @property
    def relic_conditions_path(self) -> Path:
        return self.resolve_path(self.RELIC_CONDITIONS_FILE)

    @property
    def outer_buffs_path(self) -> Path:
        return self.resolve_path(self.OUTER_BUFFS_FILE)

    @property
    def icons_path(self) -> Path:
        return self.resolve_path(self.ICONS_DIR)

    @property
    def offline_data_path(self) -> Path:
        return self.resolve_path(self.OFFLINE_DATA_DIR)

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )


settings = Settings()
