#!/usr/bin/env python3
"""
Minimal launcher — spawns N worker subprocesses, restarts dead ones.
No threads, no complexity. Just subprocess management.
"""
import subprocess, sys, time, signal

WORKERS = 40
BOT = "run_bot.py"
ARGS = ["--panels", "panels.json", "--count", "99999", "--headless",
        "--mail-provider", "fake_legal", "--domain", "fake.legal", "--country", "us"]

procs = {}
running = True

def shutdown(sig=None, frame=None):
    global running
    running = False
    for p in procs.values():
        try: p.terminate()
        except: pass
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

print(f"[*] Spawning {WORKERS} workers...")
for i in range(WORKERS):
    cmd = [sys.executable, BOT] + ARGS
    procs[i] = subprocess.Popen(cmd)
    print(f"  [{i+1}/{WORKERS}] PID {procs[i].pid}")
    time.sleep(0.3)

print(f"\n[+] All {WORKERS} workers running. Ctrl+C to stop.\n")

while running:
    time.sleep(10)
    for i in list(procs.keys()):
        if procs[i].poll() is not None:
            print(f"  [!] Worker {i} died (exit {procs[i].returncode}). Restarting...")
            cmd = [sys.executable, BOT] + ARGS
            procs[i] = subprocess.Popen(cmd)
            print(f"  [+] Worker {i} restarted (PID {procs[i].pid})")
