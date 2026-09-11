#!/usr/bin/env python3
"""First installation on a shared Ubuntu 24.04 host; no host package changes.

Run as root to provision ONLY Frankenfly. --check performs a read-only preflight.
The setup worker and app run as an unprivileged systemd DynamicUser with limits.
An existing installation is never overwritten; this is not an update script.
"""
from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
from urllib.parse import urlparse
import venv

REVISION = "8ec05640a0ac231cb60b261be1747a1ce5c0845d"
BASE = Path("/opt/frankenfly")
STATE = Path("/var/lib/frankenfly")
UNITS = Path("/etc/systemd/system")
UNIT_NAMES = ("frankenfly.service", "frankenfly-setup.service")
PORT = 18080
PIP_VERSION = "25.0.1"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def exists(path):
    return os.path.lexists(path)


def check_existing_resources():
    protected = [BASE, STATE, Path("/var/lib/private/frankenfly")]
    protected += [UNITS / name for name in UNIT_NAMES]
    for directory in (UNITS, Path('/run/systemd/system'), Path('/usr/lib/systemd/system'), Path('/usr/local/lib/systemd/system')):
        protected += [directory / (name + '.d') for name in UNIT_NAMES]
    for path in protected:
        if exists(path):
            raise RuntimeError(f"Already exists, left untouched: {path}")
    for name in UNIT_NAMES:
        status = run("systemctl", "show", name, "--property=LoadState", "--value", capture_output=True, text=True)
        if status.stdout.strip() != "not-found":
            raise RuntimeError(f"Existing unit {name}, left untouched.")
    try:
        pwd.getpwnam("frankenfly")
    except KeyError:
        pass
    else:
        raise RuntimeError("Existing frankenfly account, left untouched.")
    try:
        grp.getgrnam("frankenfly")
    except KeyError:
        pass
    else:
        raise RuntimeError("Existing frankenfly group, left untouched.")


def preflight():
    if os.geteuid() != 0:
        raise RuntimeError("Run the installer as root.")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("This installer requires the existing Python 3.12.")
    if not Path("/run/systemd/system").is_dir():
        raise RuntimeError("A running systemd host is required.")
    controllers = Path("/sys/fs/cgroup/cgroup.controllers")
    if not controllers.exists() or not {"cpu", "memory"}.issubset(controllers.read_text().split()):
        raise RuntimeError("CPU and memory cgroup v2 limits must be available.")
    for command in ("systemctl", "systemd-analyze"):
        if not shutil.which(command):
            raise RuntimeError(f"Missing {command}; no packages will be installed automatically.")
    check_existing_resources()
    memory = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
    available_mib = memory['MemAvailable'] / 1024
    if available_mib < 2560:
        raise RuntimeError(f"Only {available_mib:.0f} MiB available; setup needs at least 2560 MiB headroom.")
    for directory in ("/opt", "/var/lib"):
        if shutil.disk_usage(directory).free < 10 * 1024 ** 3:
            raise RuntimeError(f"Less than 10 GiB free under {directory}; nothing changed.")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", PORT))
    print(f"Preflight OK: {available_mib:.0f} MiB available, localhost:{PORT} free.", flush=True)


def exclusive_write(path, text, mode=0o644):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w") as output:
        output.write(text)


def download(url, destination, max_bytes):
    request = urllib.request.Request(url, headers={"User-Agent": "Frankenfly-native/0.1"})
    temporary = destination.with_suffix(".partial")
    total = 0
    with urllib.request.urlopen(request, timeout=90) as source, temporary.open("wb") as target:
        while block := source.read(1024 * 1024):
            total += len(block)
            if total > max_bytes:
                raise RuntimeError("Download exceeded the expected size limit.")
            target.write(block)
    temporary.replace(destination)


def extract_source(archive_path, destination):
    """Only regular files/directories below the pinned archive's single root."""
    prefix = f"frankenfly-{REVISION}"
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if sum(m.size for m in members) > 25 * 1024 ** 2:
            raise RuntimeError("Unexpected source archive size.")
        for member in members:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != prefix or ".." in parts or not (member.isfile() or member.isdir()):
                raise RuntimeError("Unexpected path or link in source archive.")
        for member in members:
            relative = PurePosixPath(member.name).parts[1:]
            target = destination.joinpath(*relative)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o755)
            else:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                with archive.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o644)


def unit_files():
    common = f"""DynamicUser=yes
User=frankenfly
StateDirectory=frankenfly
StateDirectoryMode=0750
WorkingDirectory={BASE}/app
Environment=PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
Environment=OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
Environment=FRANKENFLY_DATA_DIR={STATE}/data FRANKENFLY_STATE_DIR={STATE}/state
CPUAccounting=yes
CPUQuota=50%
CPUWeight=10
IOAccounting=yes
IOWeight=10
Nice=10
IOSchedulingClass=idle
MemoryAccounting=yes
MemorySwapMax=0
TasksMax=64
OOMPolicy=kill
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictNamespaces=yes
RestrictRealtime=yes
LockPersonality=yes
CapabilityBoundingSet=
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LogRateLimitIntervalSec=30s
LogRateLimitBurst=100
"""
    setup = f"""[Unit]
Description=Prepare Frankenfly's isolated Python environment and fly connectome
Wants=network-online.target
After=network-online.target
OnSuccess=frankenfly.service

[Service]
Type=oneshot
{common}MemoryHigh=1280M
MemoryMax=1536M
TimeoutStartSec=2h
ExecStart=/usr/bin/python3 {BASE}/installer.py --setup-worker
"""
    app = f"""[Unit]
Description=Frankenfly shared fly-brain simulation
Wants=network-online.target
After=network-online.target
ConditionPathExists={STATE}/ready
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
{common}MemoryHigh=640M
MemoryMax=768M
Environment=FRANKENFLY_HZ=2
EnvironmentFile={STATE}/operator.env
ExecStart={STATE}/venv/bin/python -m uvicorn frankenfly.server:app --host 127.0.0.1 --port {PORT} --workers 1 --no-proxy-headers --no-access-log --limit-concurrency 32
ExecStartPost=/usr/bin/python3 {BASE}/installer.py --wait-ready
Restart=on-failure
RestartSec=15
TimeoutStartSec=120
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
"""
    return {"frankenfly.service": app, "frankenfly-setup.service": setup}


def install():
    preflight()
    os.umask(0o022)
    BASE.mkdir(mode=0o755)
    # No existing path is adopted, deleted or recursively re-owned.
    shutil.copyfile(Path(__file__), BASE / "installer.py")
    (BASE / "installer.py").chmod(0o644)
    archive = BASE / "source.tar.gz"
    download(f"https://codeload.github.com/instynkt2/frankenfly/tar.gz/{REVISION}", archive, 10 * 1024 ** 2)
    extract_source(archive, BASE / "app")
    staged = BASE / "units"
    staged.mkdir(mode=0o755)
    for name, content in unit_files().items():
        exclusive_write(staged / name, content)
    # The app interpreter is generated by setup. --man=no keeps this local.
    # Verify the setup unit now; both units were syntax-checked in development.
    run("systemd-analyze", "verify", "--man=no", str(staged / "frankenfly-setup.service"))
    for name, content in unit_files().items():
        exclusive_write(UNITS / name, content)
    run("systemctl", "daemon-reload")
    run("systemctl", "enable", "frankenfly.service")
    run("systemctl", "start", "--no-block", "frankenfly-setup.service")
    print("Frankenfly setup started in the background; it survives closing this console.")
    print("Read progress: journalctl -u frankenfly-setup -n 25 --no-pager")
    print(f"After setup: curl -fsS http://127.0.0.1:{PORT}/healthz")
    print("Listening on localhost only. Existing ports, proxy, firewall and projects are unchanged.")


def setup_worker():
    if os.geteuid() == 0:
        raise RuntimeError("The setup worker must run under its unprivileged systemd account.")
    (STATE / "ready").unlink(missing_ok=True)
    environment = STATE / "venv"
    venv.EnvBuilder(with_pip=False).create(environment)
    python = str(environment / "bin/python")
    metadata_url = f"https://pypi.org/pypi/pip/{PIP_VERSION}/json"
    with urllib.request.urlopen(metadata_url, timeout=30) as response:
        metadata = json.load(response)
    wheel_info = next(item for item in metadata["urls"] if item["packagetype"] == "bdist_wheel")
    if urlparse(wheel_info["url"]).hostname != "files.pythonhosted.org":
        raise RuntimeError("Unexpected pip wheel host.")
    wheel = STATE / Path(wheel_info["filename"]).name
    download(wheel_info["url"], wheel, 5 * 1024 ** 2)
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != wheel_info["digests"]["sha256"]:
        raise RuntimeError("pip bootstrap checksum mismatch.")
    # The wheel supplies bootstrap code; pip installs only into this empty venv.
    install_env = dict(os.environ, PIP_CONFIG_FILE="/dev/null")
    bootstrap_env = dict(install_env, PYTHONPATH=str(wheel))
    run(python, "-m", "pip", "--isolated", "install", "--no-input", "--no-cache-dir",
        "--disable-pip-version-check", "--no-index", str(wheel), env=bootstrap_env)
    run(python, "-m", "pip", "--isolated", "install", "--no-input", "--no-cache-dir",
        "--disable-pip-version-check", "--only-binary=:all:", "--index-url", "https://pypi.org/simple",
        "-r", str(BASE / "app/requirements.lock"), env=install_env)
    run(python, "-m", "pip", "--isolated", "check", env=install_env)
    run(python, "-m", "frankenfly.prepare", "--data-dir", str(STATE / "data"))
    operator = STATE / "operator.env"
    if not exists(operator):
        import secrets
        exclusive_write(operator, f"FRANKENFLY_CONTROL_TOKEN={secrets.token_urlsafe(36)}\n", 0o600)
    (STATE / "state").mkdir(exist_ok=True, mode=0o700)
    exclusive_write(STATE / "ready", REVISION + "\n", 0o600)
    print("Frankenfly setup complete. Starting the app on localhost:18080.", flush=True)


def wait_ready():
    for _ in range(90):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=1) as response:
                if json.load(response).get("ready") is True:
                    print("Frankenfly health check passed.", flush=True)
                    return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise RuntimeError("Frankenfly did not become healthy within 90 attempts.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--setup-worker", action="store_true", help=argparse.SUPPRESS)
    modes.add_argument("--wait-ready", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.check:
        preflight()
    elif args.setup_worker:
        setup_worker()
    elif args.wait_ready:
        wait_ready()
    else:
        install()


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"STOP: {error}\nNo other project has been stopped, removed or reconfigured.")
