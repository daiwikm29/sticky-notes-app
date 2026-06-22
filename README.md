# F9 Sticky Note

A lightweight floating sticky note that lives in the corner of your screen. Press **F9** anywhere to show or hide it. Everything auto-saves, so nothing is lost when you hide the window or close the app.

Three tabs in one small window:

- **Scratch** — a free-form text pad for quick notes.
- **To-Do** — a checklist you can add, check off, and delete.
- **Tech** — a second checklist (handy for snippets, commands, or anything you want kept separate).

## Features

- Global **F9** hotkey to toggle the window from anywhere.
- Frameless, always-on-top, dark UI.
- Drag the title bar to move it; drag the corner grip (◢) to resize.
- Window size and all content persist between launches.
- Notes are saved per-user in your OS app-data folder, so multiple accounts on the same PC don't share notes.

## Requirements

- **Windows** (this is what the app is built and tested for — see note below).
- **Python 3.8+** ([python.org/downloads](https://www.python.org/downloads/)). During install, check **"Add Python to PATH."**
- One external package: `keyboard` (installed in the step below). `tkinter` ships with Python on Windows.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python sticky_launcher.py
```

The window starts hidden. Press **F9** to show it.

### Run on startup (optional)

1. Press `Win + R`, type `shell:startup`, and press Enter.
2. Put a shortcut to `sticky_launcher.py` in the folder that opens.

## Where are my notes stored?

In your personal Windows app-data folder:

```
%APPDATA%\F9StickyNote\sticky_data.json
```

If that file ever becomes unreadable, the app won't wipe it — it saves a copy as `sticky_data.json.corrupt` next to it and starts with empty notes, so you can recover the old contents.

## A note on platform support

This is built and tested for **Windows only**. The code paths for macOS and Linux storage locations exist, but on those systems the `keyboard` library needs to run with elevated privileges (admin/root) to capture a global hotkey, and the frameless window behaves differently. It may work, but it's not officially supported or tested.

## License

[MIT](LICENSE) — do what you like, just keep the copyright notice.
