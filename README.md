<img width="1080" height="1080" alt="LinkedIn post 1080×1080@1x (2)" src="https://github.com/user-attachments/assets/22d79886-cd65-407b-abc5-e5ba821faa40" />
# Suunday-hacks- ☁️

Tiny scripts for a cleaner, prettier setup. Built on lazy Sundays.

## 🖼️ Chrome Wallpaper Sync

Change your Windows wallpaper once and every Chrome profile's New Tab background matches it. It runs silently in the background and starts at login, so it feels like a built-in feature.

### Install

```
python chrome_wallpaper_sync.py --install
```

This copies the script to `C:\ChromeWallpaperSync`, starts it, and makes it launch at every login. No admin rights needed.

### How it works

- Checks the wallpaper Windows is showing every 5 seconds (slideshows and themes work too).
- Copies it into every Chrome profile as the custom New Tab background.
- Chrome overwrites its settings while running, so each profile is switched on once, the next time Chrome is fully closed. After that, changes apply even while Chrome is open (new tabs pick them up).

### Uninstall

Close Chrome, then:

```
python chrome_wallpaper_sync.py --uninstall
```

Stops the autostart and restores each profile's original Chrome settings from the backup.

### Requirements

- Windows + Google Chrome
- Python 3.10+
- `pip install pillow` only if your wallpaper is PNG/BMP (JPEG needs nothing)

### Other usage

```
python chrome_wallpaper_sync.py          # run in the foreground
python chrome_wallpaper_sync.py --once   # apply once and exit
```

Chrome's own sync may override the background on signed-in profiles.
