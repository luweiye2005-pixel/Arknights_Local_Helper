"""本地图标回退逻辑。"""
from pathlib import Path

from app.services import local_assets as la


def test_upgrade_base_relic_id():
    assert la.upgrade_base_relic_id("rogue_4_relic_legacy_9_c") == "rogue_4_relic_legacy_9"
    assert la.upgrade_base_relic_id("rogue_3_relic_legacy_16_a") == "rogue_3_relic_legacy_16"
    assert la.upgrade_base_relic_id("rogue_1_relic_r01") is None


def test_icon_candidates_order():
    assert la.icon_candidates("x_b") == ["x_b", "x"]
    assert la.icon_candidates("plain") == ["plain"]


def test_resolve_local_icon_falls_back_to_base(tmp_path, monkeypatch):
    root = tmp_path / "relics"
    root.mkdir()
    base = root / "rogue_4_relic_legacy_9.png"
    base.write_bytes(b"x" * 200)

    monkeypatch.setattr(la, "icons_root", lambda: root)
    path = la.resolve_local_icon("rogue_4_relic_legacy_9_c")
    assert path is not None
    assert path.name == "rogue_4_relic_legacy_9.png"


def test_resolve_local_icon_prefers_own_png(tmp_path, monkeypatch):
    root = tmp_path / "relics"
    root.mkdir()
    (root / "item_a.png").write_bytes(b"a" * 200)
    (root / "item.png").write_bytes(b"b" * 200)
    monkeypatch.setattr(la, "icons_root", lambda: root)
    path = la.resolve_local_icon("item_a")
    assert path.name == "item_a.png"


def test_has_real_icon_via_base(tmp_path, monkeypatch):
    root = tmp_path / "relics"
    root.mkdir()
    (root / "foo.png").write_bytes(b"z" * 200)
    monkeypatch.setattr(la, "icons_root", lambda: root)
    assert la.has_real_icon("foo_c") is True
    assert la.has_real_icon("missing_c") is False
