"""Protection of unrelated files during first-time native deployment."""
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location(
    "install_native", Path(__file__).parents[1] / "scripts/install_native.py"
)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def test_existing_installation_is_rejected_and_preserved(tmp_path, monkeypatch):
    base = tmp_path / "frankenfly"
    base.mkdir()
    original = base / "existing-project.txt"
    original.write_text("keep this project")
    monkeypatch.setattr(native, "BASE", base)
    with pytest.raises(RuntimeError, match="Already exists"):
        native.check_existing_resources()
    assert original.read_text() == "keep this project"
    assert list(base.iterdir()) == [original]


def test_exclusive_write_preserves_existing_unit(tmp_path):
    target = tmp_path / "existing.service"
    target.write_text("an unrelated service")
    with pytest.raises(FileExistsError):
        native.exclusive_write(target, "replacement")
    assert target.read_text() == "an unrelated service"


@pytest.mark.parametrize("malicious_name,is_link", [("../outside.txt", False), ("link", True)])
def test_archive_rejects_escape_before_writing_files(tmp_path, malicious_name, is_link):
    archive_path = tmp_path / "source.tar.gz"
    prefix = f"frankenfly-{native.REVISION}"
    with tarfile.open(archive_path, "w:gz") as archive:
        good = tarfile.TarInfo(f"{prefix}/first.txt")
        good.size = 4
        archive.addfile(good, io.BytesIO(b"safe"))
        bad = tarfile.TarInfo(f"{prefix}/{malicious_name}")
        if is_link:
            bad.type = tarfile.SYMTYPE
            bad.linkname = "/etc"
        archive.addfile(bad)
    destination = tmp_path / "app"
    with pytest.raises(RuntimeError, match="Unexpected path"):
        native.extract_source(archive_path, destination)
    assert not destination.exists()
    assert not (tmp_path / "outside.txt").exists()
