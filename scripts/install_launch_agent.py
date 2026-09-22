"""Install a macOS LaunchAgent that runs jobs_sync_and_notify.py periodically.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 13. Writes a plist to
~/Library/LaunchAgents (a per-user agent, not a system-wide LaunchDaemon --
no root required) and loads it with `launchctl`. macOS only.

    python scripts/install_launch_agent.py                       # every 15 minutes
    python scripts/install_launch_agent.py --interval-minutes 30
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

from swetrack.infrastructure.paths import find_repo_root

LABEL = "com.swetrack.jobradar.sync"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def plist_contents(*, python_executable: str, script_path: Path, interval_seconds: int) -> str:
    log_dir = Path.home() / "Library" / "Logs"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_executable}</string>
        <string>{script_path}</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{log_dir / "swetrack-jobradar.log"}</string>
    <key>StandardErrorPath</key>
    <string>{log_dir / "swetrack-jobradar.error.log"}</string>
</dict>
</plist>
"""


def install(*, interval_minutes: int) -> None:
    if platform.system() != "Darwin":
        raise SystemExit("LaunchAgents are macOS-only.")

    script_path = find_repo_root() / "scripts" / "jobs_sync_and_notify.py"
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    (Path.home() / "Library" / "Logs").mkdir(parents=True, exist_ok=True)
    path.write_text(plist_contents(python_executable=sys.executable, script_path=script_path, interval_seconds=interval_minutes * 60))

    subprocess.run(["launchctl", "unload", str(path)], capture_output=True)  # ignore: fine if not already loaded
    subprocess.run(["launchctl", "load", str(path)], check=True)
    print(f"Installed and loaded {path} -- runs every {interval_minutes} minute(s) while the Mac is awake.")
    print(f"Logs: {Path.home() / 'Library' / 'Logs' / 'swetrack-jobradar.log'}")
    print("Uninstall with: python scripts/uninstall_launch_agent.py")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interval-minutes", type=int, default=15)
    args = parser.parse_args()
    install(interval_minutes=args.interval_minutes)


if __name__ == "__main__":
    main()
