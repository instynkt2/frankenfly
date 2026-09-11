#!/usr/bin/env python3
"""Console-friendly entry point for the reviewed, pinned native installer."""
from pathlib import Path
import hashlib
import os
import sys
import urllib.request

REVISION = "d4cbf5195927702d1543dc1d1d8e5fbced9f4617"
SHA256 = "51aa036b8b4cc1001fa1c35fd4c4f311c75d226a1576cc353f8fac5ab9280cd0"
URL = f"https://raw.githubusercontent.com/instynkt2/frankenfly/{REVISION}/scripts/install_native.py"


def prepare_installer(directory):
    target = directory / f"frankenfly-native-{REVISION[:8]}.py"
    if target.is_symlink():
        raise RuntimeError(f"Existing symbolic link, left untouched: {target}")
    if target.exists():
        data = target.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read(128 * 1024)
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise RuntimeError("Installer checksum mismatch; nothing executed.")
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError(f"Different existing file, left untouched: {target}")
    return target


if __name__ == "__main__":
    try:
        installer = prepare_installer(Path(__file__).resolve().parent)
        os.execv(sys.executable, [sys.executable, str(installer), *sys.argv[1:]])
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"STOP: {error}")
