"""Uninstall the Job Radar macOS LaunchAgent installed by install_launch_agent.py."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

LABEL = "com.swetrack.jobradar.sync"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def main() -> None:
    if platform.system() != "Darwin":
        raise SystemExit("LaunchAgents are macOS-only.")

    path = plist_path()
    if not path.exists():
        print(f"No LaunchAgent installed at {path}.")
        return

    subprocess.run(["launchctl", "unload", str(path)], capture_output=True)
    path.unlink()
    print(f"Uninstalled {path}.")


if __name__ == "__main__":
    main()
