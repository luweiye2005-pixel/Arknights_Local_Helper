import gzip
import hashlib
import json

import pytest

from app.data import json_db


def write_bundle(path, payload, version=1, valid_hash=True):
    path.mkdir()
    raw = gzip.compress(json.dumps(payload).encode())
    (path / "data.json.gz").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest() if valid_hash else "bad"
    (path / "manifest.json").write_text(json.dumps({"schema_version": version, "data_sha256": digest}))


def test_offline_bundle_verifies_hash_and_schema(tmp_path, monkeypatch):
    payload = {"operators": {}, "enemies": {}, "relics": {}, "operator_briefs": [], "skills": {}, "themes": []}
    write_bundle(tmp_path / "ok", payload)
    monkeypatch.setattr(json_db.settings, "OFFLINE_DATA_DIR", str(tmp_path / "ok"))
    json_db._data.cache_clear()
    assert json_db.db_counts()["operators"] == 0


def test_offline_bundle_rejects_corruption(tmp_path, monkeypatch):
    write_bundle(tmp_path / "bad", {}, valid_hash=False)
    monkeypatch.setattr(json_db.settings, "OFFLINE_DATA_DIR", str(tmp_path / "bad"))
    json_db._data.cache_clear()
    with pytest.raises(json_db.OfflineDataError, match="校验失败"):
        json_db.init_schema()


def test_offline_bundle_rejects_unknown_schema(tmp_path, monkeypatch):
    write_bundle(tmp_path / "future", {}, version=99)
    monkeypatch.setattr(json_db.settings, "OFFLINE_DATA_DIR", str(tmp_path / "future"))
    json_db._data.cache_clear()
    with pytest.raises(json_db.OfflineDataError, match="不支持的数据版本"):
        json_db.init_schema()
