# F9 Sticky Note

A lightweight floating sticky note that lives in the corner of your screen. Press **F9** anywhere to show or hide it. Everything auto-saves, so nothing is lost when you hide the window or close the app.

It comes with a couple of starter tabs — a notes pad and a checklist — and you can add, rename, delete, and fully restyle them.

### Custom tabs

- **Add a tab:** click the **＋** at the end of the tab row. You choose a name and whether it's a *Notes pad* (free typing) or a *Checklist* (add / check off / delete items).
- **Rename a tab:** right-click it and choose **Rename**.
- **Delete a tab:** right-click it and choose **Delete**. (You can't delete your last remaining tab, and you'll be asked to confirm if it still has content.)

All tab names, types, and contents are saved automatically. If you're upgrading from an older version, your existing notes carry over with no setup.

### Settings (⚙)

Click the **⚙ gear** in the top-right to open Settings. Drag its title bar to move it; **✕** to close.

- **Theme color** — pick one color and the whole note is recolored in shades of it, with the text automatically set to a contrasting color so it stays readable.
- **Accent color** — the highlight color (active tab, ＋, checkmarks).
- **Text color** — set your own, or click **Auto** to let it auto-contrast with the theme.
- **Text size** — make the writing bigger or smaller with **–** / **+**.
- **Text background shade** — lighten or darken the box behind the text while the text itself stays fully solid and readable.
- **Reset to defaults** — back to the original dark/gold look.

## Features

- Global **F9** hotkey to toggle the window from anywhere.
- Frameless, always-on-top, dark UI (fully themeable in Settings).
- **Customizable tabs** — add, rename, and delete tabs; each is either a notes pad or a checklist.
- **Customizable look** — theme/accent/text colors, text size, and text-background shade.
- Drag the title bar to move it; drag the corner grip (◢) to resize. Text wraps to the window width automatically.
- Window size, theme, and all content persist between launches.

## Requirements

- **Windows** (this is what the app is built and tested for — see note below).
- **Python 3.8+** ([python.org/downloads](https://www.python.org/downloads/)). During install, check **"Add Python to PATH."**
- One external package: `keyboard` (installed in the step below). `tkinter` ships with Python on Windows.

## Download (no Python needed)

Grab the prebuilt **`StickyNote.exe`** from the [Releases](https://github.com/daiwikm29/sticky-notes-app/releases) page, double-click it, and press **F9**. That's it — Python is not required to run the prebuilt app.

## Run from source

```bash
pip install -r requirements.txt
python sticky_launcher.py
```

The window starts hidden. Press **F9** to show it.

### Run on startup (optional)

1. Press `Win + R`, type `shell:startup`, and press Enter.
2. Put a shortcut to `sticky_launcher.py` (or `StickyNote.exe`) in the folder that opens.

## Where are my notes stored?

In a single file in your home folder:

```
~/sticky_data.json
```

On Windows that's `C:\Users\<you>\sticky_data.json`. Because it lives in your personal home folder, each user account on a PC keeps its own separate notes, and the file survives reboots and app updates. Notes from older versions (the previous `notes` / `to-do` / `tech` format) are migrated into the new tabbed format automatically the first time you run this version.

If that file ever becomes unreadable, the app won't wipe it — it saves a copy as `sticky_data.json.corrupt` next to it and starts fresh, so you can recover the old contents.

## A note on platform support

This is built and tested for **Windows only**. The app also runs on macOS and Linux (the save file goes to `~/sticky_data.json` there too), but on those systems the `keyboard` library needs elevated privileges (admin/root) to capture a global hotkey, and the frameless window behaves differently. It may work, but it's not officially supported or tested.

## License

[MIT **with an attribution requirement**](LICENSE) — free to use, modify, and sell, but any distribution or public/commercial use (including rebranded or modified versions) must give clear, visible credit to the original author (daiwikm29). See [LICENSE](LICENSE) for the exact terms.
