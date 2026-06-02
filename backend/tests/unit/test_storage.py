import pytest

from app.services.storage import LocalStorage


def test_local_storage_roundtrip(tmp_path):
    store = LocalStorage(str(tmp_path))
    key = "hr/abc/file.txt"
    store.put(key, b"hello", "text/plain")
    assert store.get(key) == b"hello"
    store.delete(key)
    with pytest.raises(FileNotFoundError):
        store.get(key)


def test_local_storage_blocks_path_traversal(tmp_path):
    store = LocalStorage(str(tmp_path))
    with pytest.raises(ValueError):
        store.put("../../etc/passwd", b"x", "text/plain")


def test_delete_missing_is_noop(tmp_path):
    LocalStorage(str(tmp_path)).delete("nope/missing.txt")  # must not raise
