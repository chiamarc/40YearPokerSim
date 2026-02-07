#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time

try:
    from watchfiles import watch
except ImportError:  # pragma: no cover
    print("Missing dependency: watchfiles. Run: pip install -r requirements-dev.txt")
    sys.exit(1)


WATCH_PATHS = [
    os.path.join(os.getcwd(), "app.py"),
    os.path.join(os.getcwd(), "engine.py"),
    os.path.join(os.getcwd(), "sim.py"),
    os.path.join(os.getcwd(), "index.html"),
    os.path.join(os.getcwd(), "static"),
]


class Runner:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.restart_event = threading.Event()
        self.stop_event = threading.Event()

    def start(self) -> None:
        self.process = subprocess.Popen([sys.executable, "app.py"])

    def stop(self) -> None:
        if not self.process:
            return
        if self.process.poll() is not None:
            return
        self.process.send_signal(signal.SIGTERM)
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)

    def restart(self) -> None:
        self.stop()
        self.start()

    def run(self) -> None:
        self.start()
        while not self.stop_event.is_set():
            if self.restart_event.wait(timeout=0.2):
                self.restart_event.clear()
                self.restart()


def _watch_files(runner: Runner) -> None:
    for _ in watch(*WATCH_PATHS):
        runner.restart_event.set()


def _watch_keys(runner: Runner) -> None:
    while not runner.stop_event.is_set():
        ch = sys.stdin.read(1)
        if not ch:
            time.sleep(0.05)
            continue
        if ch.lower() == "r":
            runner.restart_event.set()
        elif ch.lower() == "q":
            runner.stop_event.set()
            runner.restart_event.set()


def main() -> None:
    runner = Runner()
    file_thread = threading.Thread(target=_watch_files, args=(runner,), daemon=True)
    key_thread = threading.Thread(target=_watch_keys, args=(runner,), daemon=True)
    file_thread.start()
    key_thread.start()

    try:
        runner.run()
    except KeyboardInterrupt:
        runner.stop_event.set()
    finally:
        runner.stop()


if __name__ == "__main__":
    main()
