#!/usr/bin/env python3
"""
Kiro Bot Swarm — Run multiple concurrent bot instances without Docker.

Reads panels.json and spawns bot subprocesses. Each creates accounts
and adds them to ALL panels. No threading — pure subprocess management.

Usage:
    python swarm.py                    # 1 instance, all panels
    python swarm.py --instances 3      # 3 concurrent instances, all panels
    python swarm.py --dry-run          # Preview only
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BOT_SCRIPT = SCRIPT_DIR / "run_bot.py"
procs: dict[str, subprocess.Popen] = {}
running = True


def build_cmd(panels_json: Path) -> list[str]:
    return [
        sys.executable, str(BOT_SCRIPT),
        "--panels", str(panels_json),
        "--count", "99999",
        "--domain", "fake.legal",
        "--country", "us",
        "--headless",
        "--no-proxy",
        "--mail-provider", "fake_legal",
    ]


def shutdown(sig=None, frame=None):
    global running
    running = False
    print("\n[*] Stopping all instances...")
    for name, proc in procs.items():
        try:
            proc.terminate()
        except Exception:
            pass
    time.sleep(3)
    for name, proc in procs.items():
        try:
            proc.kill()
        except Exception:
            pass
    sys.exit(0)


def main():
    global running
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    instances = 1

    config_path = SCRIPT_DIR / "panels.json"
    for i, a in enumerate(args):
        if a == "--instances" and i + 1 < len(args):
            instances = int(args[i + 1])
        elif not a.startswith("-") and not a.isdigit():
            config_path = Path(a)

    if not config_path.exists():
        print(f"ERROR: {config_path} not found")
        sys.exit(1)

    with open(config_path) as f:
        panels = json.load(f)

    if not panels:
        print("ERROR: No panels"); sys.exit(1)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 60)
    print("  Kiro Bot Swarm")
    print("=" * 60)
    for p in panels:
        print(f"  Panel: {p['url']}")
    print(f"  Instances: {instances}")
    print(f"  Each account -> ALL panels")
    print()

    if dry_run:
        print("DRY RUN")
        print(f"  cmd: {' '.join(build_cmd(config_path))}")
        sys.exit(0)

    log_dir = SCRIPT_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    # Start all instances as subprocesses (no threading)
    for i in range(instances):
        name = f"kiro-{i+1}"
        log_file = log_dir / f"{name}.log"
        cmd = build_cmd(config_path)
        lf = open(log_file, "a", encoding="utf-8")
        proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=str(SCRIPT_DIR))
        procs[name] = proc
        print(f"  [{name}] Started (pid={proc.pid}, log={log_file})")

    print(f"\n  Running {len(procs)} instance(s). Ctrl+C to stop.\n")

    # Monitor loop — restart crashed instances
    while running:
        for name, proc in list(procs.items()):
            if proc.poll() is not None:
                exit_code = proc.returncode
                print(f"  [{name}] Stopped (exit {exit_code}). Restarting in 10s...")
                time.sleep(10)
                if not running:
                    break
                log_file = log_dir / f"{name}.log"
                lf = open(log_file, "a", encoding="utf-8")
                cmd = build_cmd(config_path)
                new_proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=str(SCRIPT_DIR))
                procs[name] = new_proc
                print(f"  [{name}] Restarted (pid={new_proc.pid})")
        time.sleep(5)


if __name__ == "__main__":
    main()
