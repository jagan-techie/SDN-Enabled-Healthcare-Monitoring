#!/usr/bin/env python3
"""Single-click launcher for the SDN-Enabled-Healthcare-Monitoring project.

This script creates a local virtual environment if needed, installs the project
requirements, then starts the full system stack via scripts/run_all.py.

Double-click this file on Windows (or run `python run_project.py`) to start the
entire demo with one click.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"
RUNNER = ROOT / "scripts" / "run_all.py"


def print_step(message: str) -> None:
    print(f"\n[run_project] {message}")


def get_venv_python() -> Path:
    if sys.platform == "win32":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def ensure_virtualenv() -> Path:
    venv_python = get_venv_python()
    if venv_python.exists():
        print_step(f"Using existing environment: {venv_python}")
        return venv_python

    print_step("Creating project virtual environment...")
    venv.EnvBuilder(with_pip=True, clear=False, upgrade=False).create(ROOT / ".venv")
    if not venv_python.exists():
        raise FileNotFoundError(f"Virtual environment was not created at {venv_python}")
    print_step(f"Environment ready: {venv_python}")
    return venv_python


def ensure_requirements(python_exe: Path) -> None:
    if not REQUIREMENTS.exists():
        raise FileNotFoundError(f"Missing requirements file: {REQUIREMENTS}")

    print_step("Installing Python dependencies...")
    subprocess.run(
        [str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        cwd=str(ROOT),
        check=True,
    )
    subprocess.run(
        [str(python_exe), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        cwd=str(ROOT),
        check=True,
    )
    print_step("Dependencies installed successfully.")


def launch_stack(python_exe: Path) -> subprocess.Popen:
    print_step("Starting the SDN-enabled healthcare monitoring stack...")
    process = subprocess.Popen(
        [str(python_exe), "-u", str(RUNNER)],
        cwd=str(ROOT),
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    time.sleep(6)
    try:
        webbrowser.open("http://127.0.0.1:5000/login")
    except Exception:
        pass

    print("\n")
    print("=" * 72)
    print("Project is starting...")
    print("Dashboard: http://127.0.0.1:5000/login")
    print("Controller API: http://127.0.0.1:8080/api/v1/priority/status")
    print("Press Ctrl+C here to stop all services.")
    print("=" * 72)
    return process


def main() -> int:
    if not RUNNER.exists():
        raise FileNotFoundError(f"Missing launcher script: {RUNNER}")

    print("=" * 72)
    print("SDN-Enabled Healthcare Monitoring")
    print("Single-click launcher")
    print("=" * 72)

    python_exe = ensure_virtualenv()
    ensure_requirements(python_exe)
    process = launch_stack(python_exe)

    try:
        return process.wait()
    except KeyboardInterrupt:
        print_step("Stopping all services...")
        if sys.platform == "win32":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - top-level user UX path
        print(f"\n[run_project] ERROR: {exc}", file=sys.stderr)
        print("\nPlease ensure Python 3.10+ is installed and try again.", file=sys.stderr)
        raise SystemExit(1)
