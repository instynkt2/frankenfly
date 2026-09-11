"""The frontend deployment must preserve custom files and recover from I/O errors."""
import hashlib
import importlib.util
import io
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("frontend_update", Path(__file__).parents[1] / "update.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    root = tmp_path / "app"
    old = {"dist/index.html": b"original html", "dist/assets/app.js": b"original javascript"}
    new = {name: data + b" with relative URLs" for name, data in old.items()}
    hashes = {name: tuple(hashlib.sha256(value).hexdigest() for value in (data, new[name])) for name, data in old.items()}
    monkeypatch.setattr(updater, "HASHES", hashes)
    for name, data in old.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (root / "unrelated.txt").write_text("preserve me")
    def download(url, timeout):
        name = next(name for name in new if url.endswith("/" + name))
        return io.BytesIO(new[name])
    monkeypatch.setattr(updater.urllib.request, "urlopen", download)
    return root, old, new


def test_update_preserves_other_files_and_keeps_originals(deployment):
    root, old, new = deployment
    updater.apply_update(root, "a" * 40)
    assert all((root / name).read_bytes() == data for name, data in new.items())
    backup, = root.parent.glob("frontend-backup-*")
    assert all((backup / Path(name).name).read_bytes() == data for name, data in old.items())
    assert (root / "unrelated.txt").read_text() == "preserve me"
    updater.apply_update(root, "a" * 40)
    assert len(list(root.parent.glob("frontend-backup-*"))) == 1


def test_custom_file_blocks_all_writes(deployment):
    root, old, _ = deployment
    target = root / "dist/index.html"
    target.write_text("custom content")
    with pytest.raises(RuntimeError, match="custom changes"):
        updater.apply_update(root, "a" * 40)
    assert target.read_text() == "custom content"
    assert (root / "dist/assets/app.js").read_bytes() == old["dist/assets/app.js"]
    assert not list(root.parent.glob("frontend-backup-*"))


def test_second_write_failure_restores_first_file(deployment, monkeypatch):
    root, old, _ = deployment
    replace = Path.replace
    def fail_second(source, target):
        if source.name == "new-app.js":
            raise OSError("simulated disk failure")
        return replace(source, target)
    monkeypatch.setattr(Path, "replace", fail_second)
    with pytest.raises(OSError, match="simulated disk failure"):
        updater.apply_update(root, "a" * 40)
    assert all((root / name).read_bytes() == data for name, data in old.items())
    assert (root / "unrelated.txt").read_text() == "preserve me"
