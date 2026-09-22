"""macOS local notification delivery via `osascript`. No external dependency, $0.

SWETrack_Job_Radar_Claude_Code_Handoff.md Section 13. Best-effort: on any
non-macOS platform, or if `osascript` fails/is missing, this is a no-op that
returns False rather than raising -- a notification failing to display must
never break a sync.
"""

from __future__ import annotations

import platform
import subprocess

_TIMEOUT_SECONDS = 5.0


def send_macos_notification(*, title: str, subtitle: str, message: str) -> bool:
    """Fire a native macOS notification banner. Returns True only if it was actually sent."""
    if platform.system() != "Darwin":
        return False

    script = (
        f"display notification {_applescript_string(message)} "
        f"with title {_applescript_string(title)} "
        f"subtitle {_applescript_string(subtitle)}"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=_TIMEOUT_SECONDS,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _applescript_string(value: str) -> str:
    """Quote a string for safe embedding in an AppleScript `-e` argument."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
