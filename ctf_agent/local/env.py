from __future__ import annotations
import platform
from dataclasses import dataclass
from pathlib import Path

@dataclass
class HostEnv:
    os: str            # "linux" | "darwin" | "windows"
    is_wsl: bool
    distro: str        # best-effort
    shell: str
    home: str

def detect_env() -> HostEnv:
    osname = platform.system().lower()
    is_wsl = False
    distro = ""

    if osname == "linux":
        try:
            txt = Path("/proc/version").read_text().lower()
            is_wsl = "microsoft" in txt or "wsl" in txt
        except Exception:
            pass
        # distro best-effort
        try:
            distro = Path("/etc/os-release").read_text()
        except Exception:
            distro = ""

    shell = platform.os.environ.get("SHELL", "") if hasattr(platform, "os") else ""
    home = str(Path.home())
    return HostEnv(os=osname, is_wsl=is_wsl, distro=distro, shell=shell, home=home)
