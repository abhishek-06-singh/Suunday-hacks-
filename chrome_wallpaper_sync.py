"""Keep the Chrome New Tab Page background in sync with the Windows wallpaper.

Applies the current desktop wallpaper as the custom NTP background of every
Chrome profile on this PC (uploaded-image style: <profile>/background.jpg plus
ntp.custom_background_local_to_device).

Usage:
    python chrome_wallpaper_sync.py          # watch forever, re-apply on change
    python chrome_wallpaper_sync.py --once   # apply once and exit
    python chrome_wallpaper_sync.py --install  # copy to C:/ChromeWallpaperSync + autostart
    python chrome_wallpaper_sync.py --uninstall  # stop autostart, restore original Chrome settings

Chrome rewrites its Preferences file while running, so profile settings are only
edited while Chrome is closed (pending profiles are retried on every poll).
The image file itself is copied immediately, even while Chrome is open.
Run with pythonw.exe (or drop a shortcut in shell:startup) to keep it silent.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import winreg
from pathlib import Path

USER_DATA = Path(os.environ["LOCALAPPDATA"]) / "Google" / "Chrome" / "User Data"
TRANSCODED = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Themes" / "TranscodedWallpaper"
STATE_FILE = Path(__file__).with_name(".chrome_wallpaper_sync_state.json")
POLL_SECONDS = 5
SKIP_PROFILES = {"System Profile", "Guest Profile"}


def registry_wallpaper() -> Path | None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
        value, _ = winreg.QueryValueEx(key, "WallPaper")
    return Path(value) if value else None


def current_wallpaper() -> Path | None:
    # TranscodedWallpaper always holds what is actually shown (slideshow,
    # themes, Spotlight); the registry path is the fallback.
    if TRANSCODED.exists():
        return TRANSCODED
    path = registry_wallpaper()
    return path if path and path.exists() else None


def as_jpeg(src: Path) -> bytes:
    data = src.read_bytes()
    if data[:3] == b"\xff\xd8\xff":
        return data
    from PIL import Image  # only needed for PNG/BMP wallpapers

    buf = io.BytesIO()
    Image.open(io.BytesIO(data)).convert("RGB").save(buf, "JPEG", quality=95)
    return buf.getvalue()


def chrome_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
                         capture_output=True, text=True, creationflags=0x08000000).stdout
    return "chrome.exe" in out.lower()


def close_chrome() -> None:
    subprocess.run(["taskkill", "/IM", "chrome.exe", "/F"], capture_output=True, creationflags=0x08000000)
    for _ in range(20):
        if not chrome_running():
            return
        time.sleep(0.5)


def profiles() -> list[Path]:
    return [p for p in USER_DATA.iterdir()
            if p.is_dir() and p.name not in SKIP_PROFILES and (p / "Preferences").exists()]


def enable_local_background(profile: Path) -> bool:
    """Mark the profile as using an uploaded local NTP background. Chrome must be closed."""
    prefs_path = profile / "Preferences"
    prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
    ntp = prefs.setdefault("ntp", {})
    if (ntp.get("custom_background_local_to_device") is True
            and "custom_background_dict" not in ntp):
        return False
    backup = profile / "Preferences.wallpaper-sync.bak"
    if not backup.exists():
        shutil.copy2(prefs_path, backup)
    ntp["custom_background_local_to_device"] = True
    ntp.pop("custom_background_dict", None)
    ntp.pop("custom_background_dict2", None)
    prefs_path.write_text(json.dumps(prefs, separators=(",", ":"), ensure_ascii=False),
                          encoding="utf-8")
    return True


def log(msg: str) -> None:
    print(time.strftime("[%H:%M:%S]"), msg, flush=True)


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state))


INSTALL_DIR = Path(r"C:\ChromeWallpaperSync")
TASK_NAME = "ChromeWallpaperSync"


def copy_image(jpeg: bytes, only_missing: bool) -> None:
    for profile in profiles():
        target = profile / "background.jpg"
        if only_missing and target.exists():
            continue
        target.write_bytes(jpeg)


def install() -> None:
    """Copy to C:/ChromeWallpaperSync and start it automatically at every logon (HKCU Run)."""
    INSTALL_DIR.mkdir(exist_ok=True)
    dest = INSTALL_DIR / "chrome_wallpaper_sync.py"
    shutil.copy2(__file__, dest)
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                        0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, TASK_NAME, 0, winreg.REG_SZ, f'"{pythonw}" "{dest}"')
    subprocess.Popen([str(pythonw), str(dest)], creationflags=0x00000008 | 0x08000000)  # DETACHED_PROCESS | CREATE_NO_WINDOW
    print(f"Installed to {INSTALL_DIR}; it now starts automatically at logon.")


def uninstall() -> None:
    """Stop autostart and restore each profile's original Preferences from the backup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, TASK_NAME)
    except FileNotFoundError:
        pass
    subprocess.run(["taskkill", "/IM", "pythonw.exe", "/F"], capture_output=True, creationflags=0x08000000)
    if chrome_running():
        print("Close Chrome and run --uninstall again to restore the original backgrounds.")
        return
    for profile in profiles():
        backup = profile / "Preferences.wallpaper-sync.bak"
        if backup.exists():
            shutil.copy2(backup, profile / "Preferences")
            backup.unlink()
    print("Uninstalled. You can delete C:/ChromeWallpaperSync.")


def main() -> None:
    if "--install" in sys.argv:
        return install()
    if "--uninstall" in sys.argv:
        return uninstall()
    once = "--once" in sys.argv
    state = load_state()

    while True:
        try:
            src = current_wallpaper()
            if src:
                jpeg = as_jpeg(src)
                digest = hashlib.sha1(jpeg).hexdigest()
                changed = digest != state.get("digest")
                if changed:
                    log(f"wallpaper changed ({src.name})")
                copy_image(jpeg, only_missing=not changed)  # new profiles get it too
                if changed:
                    state["digest"] = digest
                    save_state(state)
                # Chrome overwrites Preferences while running, so the one-time
                # per-profile switch happens as soon as Chrome is closed.
                if not chrome_running():
                    for profile in profiles():
                        if enable_local_background(profile):
                            log(f"enabled custom background for {profile.name}")
        except Exception as exc:  # keep the watcher alive
            log(f"error: {exc!r}")
        if once:
            return
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
