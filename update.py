#!/usr/bin/env python3
"""Update only the two known Frankenfly frontend files for prefix hosting.

No package installs, model changes, service restarts or Nginx edits.
By default checks existing files. --apply downloads and atomically updates them.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import tempfile
import urllib.request

ROOT = Path("/opt/frankenfly/app")
HASHES = {
    "dist/index.html": (
        "d29e03d01b7b8e8cd5722e8c0068e9842943fe905e37e93e9a76ff70a7f66696",
        "193cbc07822c3b1bb7bcf98ef86ea801efd985b674323c65eebee0d24ea0bd21",
    ),
    "dist/assets/app.js": (
        "80acb5a29f7563adeb51e86a1aa057eaa82dc76218a4395eb1dfc798067b7a2b",
        "66dd98c8c176a0ca8e28caa79de32321134c3fca5e62d890a53e0ff8a0533f9e",
    ),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def current_files(root):
    originals = {}
    for name, hashes in HASHES.items():
        target = root / name
        if target.resolve() != target or not target.is_file():
            raise RuntimeError(f"Unexpected path, left untouched: {target}")
        data = target.read_bytes()
        if digest(data) not in hashes:
            raise RuntimeError(f"File has custom changes, left untouched: {target}")
        originals[name] = data
    return originals


def apply_update(root, revision):
    originals = current_files(root)
    if all(digest(data) == HASHES[name][1] for name, data in originals.items()):
        print("Frontend already supports /frankenfly/. No changes needed.")
        return
    payloads = {}
    for name, (_, expected) in HASHES.items():
        url = f"https://raw.githubusercontent.com/instynkt2/frankenfly/{revision}/{name}"
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(128 * 1024)
        if digest(data) != expected:
            raise RuntimeError(f"Downloaded file checksum mismatch: {name}")
        payloads[name] = data
    backup = Path(tempfile.mkdtemp(prefix="frontend-backup-", dir=root.parent))
    changed = []
    try:
        for name, data in payloads.items():
            target = root / name
            if target.read_bytes() != originals[name]:
                raise RuntimeError(f"Concurrent edit detected: {target}")
            original = backup / target.name
            original.write_bytes(originals[name])
            original.chmod(0o600)
            staged = backup / ("new-" + target.name)
            staged.write_bytes(data)
            staged.chmod(0o644)
            staged.replace(target)
            changed.append(name)
    except Exception:
        for name in reversed(changed):
            target = root / name
            if digest(target.read_bytes()) == HASHES[name][1]:
                restored = backup / ("restore-" + target.name)
                restored.write_bytes(originals[name])
                restored.chmod(0o644)
                restored.replace(target)
        raise
    print(f"Updated only index.html and app.js. Original files saved under {backup}.")
    print("No services restarted. Model, state, operator key and other projects unchanged.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise RuntimeError("Use a complete, pinned Git commit SHA.")
    if os.geteuid() != 0:
        raise RuntimeError("Run on the target server as root.")
    if args.apply:
        apply_update(ROOT, args.revision)
    else:
        current_files(ROOT)
        print("Known frontend files verified. No changes made.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"STOP: {error}")
