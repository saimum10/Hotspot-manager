#!/usr/bin/env python3
# Tiny CLI entry point — used by cron (root crontab) for scheduled
# on / off / idle-check actions. Works even when the GUI app is closed.
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backend  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("Usage: cli.py [start|stop|idle-check]")
        sys.exit(1)
    action = sys.argv[1]
    if action == "start":
        backend.start_hotspot()
    elif action == "stop":
        backend.stop_hotspot()
    elif action == "idle-check":
        backend.idle_check()
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
