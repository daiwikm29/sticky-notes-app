"""
F9 Sticky Note
==============
A lightweight floating sticky note that lives in the corner of your screen.
Press F9 anywhere to show or hide it. Everything auto-saves.

The first time you run it, a popup lets you pick your own show/hide shortcut
(in case F9 is already used by another app). You can change it any time from
Settings -> Shortcut.

FEATURES
  - Custom tabs: click  ＋  to add a tab. When you add one you choose a name
    and a type — a free-text "Notes pad" or a "Checklist" (to-do list).
    Right-click any tab to Rename or Delete it.
  - Settings gear  ⚙  in the top bar:
      * Theme color — pick one color and the whole note becomes shades of it,
        with the text automatically set to a contrasting color for visibility.
      * Accent color and Text color (with "Auto" = auto-contrast) overrides.
      * Text size — make the writing bigger or smaller.
      * Text-background shade — lighten/darken the box behind the text while the
        text itself stays fully solid and readable.
  - Resize grip  ◢  in the bottom-right corner: drag to resize. Text wraps to
    the window width automatically on both notes pads and checklists.

HOW TO USE
  1. Install the one dependency:  pip install -r requirements.txt
  2. Run it:                      python sticky_launcher.py
  3. Press F9 anywhere on your PC to show/hide the note window.

RUN ON STARTUP (optional)
  Press Win+R -> type: shell:startup -> OK
  Put a shortcut to this file (or the built .exe) in that folder.

Your notes are saved to  ~/sticky_data.json  (your user folder), so they
survive reboots and stay put even if this program is moved or replaced.
Older save files (the {notes, todos, tech} format) are migrated automatically.
"""

import os
import sys
import json
import uuid
import shutil
import tempfile
import threading

# ── Dependency check ──────────────────────────────────────────────────────────
# tkinter and json ship with Python. `keyboard` is the only external dependency,
# and it is what lets us catch the global F9 press from anywhere on the system.
try:
    import keyboard
except ImportError:
    sys.stderr.write(
        "\nMissing dependency: 'keyboard'\n"
        "Install it with:\n"
        "    pip install -r requirements.txt\n"
        "  (or)\n"
        "    pip install keyboard\n\n"
    )
    sys.exit(1)

import tkinter as tk
from tkinter import simpledialog, messagebox, colorchooser


# ── Data location & persistence ───────────────────────────────────────────────
# Saved in the user's home folder so notes persist across reboots and are
# independent of where this program lives. This is the same file the older
# versions used, so existing notes are picked up automatically.
SAVE_FILE = os.path.join(os.path.expanduser("~"), "sticky_data.json")

FONT_FAMILY = "Courier New"


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _default_theme() -> dict:
    return {"base": "#141414", "accent": "#f5c518", "text": None,
            "font_size": 11, "box_shade": 50}


def _default_data() -> dict:
    tabs = [
        {"id": _new_id(), "name": "SCRATCH", "type": "text", "content": ""},
        {"id": _new_id(), "name": "TO-DO", "type": "checklist", "items": []},
    ]
    return {
        "version": 2,
        "win_w": 340,
        "win_h": 430,
        "theme": _default_theme(),
        "hotkey": "f9",
        "hotkey_prompted": False,   # show the "pick your shortcut" popup on first run
        "active": tabs[0]["id"],
        "tabs": tabs,
    }


def _migrate_v1(old: dict) -> dict:
    """Convert the old {notes, todos, tech} format into the tabbed v2 format,
    preserving every bit of existing content."""
    tabs = [
        {"id": _new_id(), "name": "SCRATCH", "type": "text",
         "content": old.get("notes", "") or ""},
        {"id": _new_id(), "name": "TO-DO", "type": "checklist",
         "items": list(old.get("todos", []) or [])},
        {"id": _new_id(), "name": "TECH", "type": "checklist",
         "items": list(old.get("tech", []) or [])},
    ]
    return {
        "version": 2,
        "win_w": old.get("win_w", 340),
        "win_h": old.get("win_h", 430),
        "theme": _default_theme(),
        "hotkey": "f9",
        "hotkey_prompted": True,    # existing users already use F9 — don't nag them
        "active": tabs[0]["id"],
        "tabs": tabs,
    }


def _normalize(data: dict) -> dict:
    """Make sure a v2 save file has every key/shape we expect."""
    data.setdefault("version", 2)
    data.setdefault("win_w", 340)
    data.setdefault("win_h", 430)
    data.setdefault("hotkey", "f9")
    data.setdefault("hotkey_prompted", True)   # already-saved files = existing users
    theme = data.setdefault("theme", _default_theme())
    for k, v in _default_theme().items():
        theme.setdefault(k, v)
    if not isinstance(data.get("tabs"), list) or not data["tabs"]:
        fresh = _default_data()
        fresh["win_w"] = data.get("win_w", 340)
        fresh["win_h"] = data.get("win_h", 430)
        fresh["theme"] = theme
        return fresh
    for t in data["tabs"]:
        t.setdefault("id", _new_id())
        t.setdefault("name", "TAB")
        if t.get("type") not in ("text", "checklist"):
            t["type"] = "text"
        if t["type"] == "checklist":
            t.setdefault("items", [])
        else:
            t.setdefault("content", "")
    ids = [t["id"] for t in data["tabs"]]
    if data.get("active") not in ids:
        data["active"] = ids[0]
    return data


def load() -> dict:
    """Load saved data, migrating/repairing as needed. Never silently destroys
    an unreadable file — it is backed up first."""
    if not os.path.exists(SAVE_FILE):
        return _default_data()
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        try:
            shutil.copy2(SAVE_FILE, SAVE_FILE + ".corrupt")
            sys.stderr.write(
                f"\nWarning: notes file was unreadable. A backup was saved to:\n"
                f"    {SAVE_FILE}.corrupt\nStarting fresh.\n\n"
            )
        except OSError:
            pass
        return _default_data()

    if isinstance(data.get("tabs"), list):
        return _normalize(data)
    return _migrate_v1(data)  # old {notes, todos, tech} format


def save(data: dict) -> None:
    """Write data atomically: temp file + rename, so the notes file is never
    left half-written if the program crashes mid-save."""
    try:
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(SAVE_FILE) or ".", prefix=".sticky_", suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SAVE_FILE)
    except OSError as e:
        sys.stderr.write(f"\nWarning: could not save notes: {e}\n")
        try:
            os.unlink(tmp)
        except (OSError, NameError):
            pass


# ── colour helpers ────────────────────────────────────────────────────────────
def _hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _blend(c1, c2, t):
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def _lum(h):
    r, g, b = _hex_to_rgb(h)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _contrast(h):
    """A light or dark colour that stands out against `h`."""
    return "#f4f4f4" if _lum(h) < 0.5 else "#161616"


def _shade(base, t):
    """Move `base` toward its contrasting end by fraction t (gives readable
    'shades of' the base colour for both dark and light themes)."""
    return _blend(base, _contrast(base), t)


# ── UI ────────────────────────────────────────────────────────────────────────
class StickyNote:
    MIN_W = 240
    MIN_H = 200

    def __init__(self):
        self.data = load()
        self.visible = False
        self._settings_win = None
        self._popup_win = None
        self._recording = False               # True while capturing a new shortcut
        self._rec_binding = None               # tkinter <KeyPress> binding id while recording
        self._rec_button = None               # the Record/Done toggle label
        self._rec_binding_rel = None          # tkinter <KeyRelease> binding id while recording
        self._rec_keys = []                   # unique keys captured for the current combo
        self._rec_down = set()                # keysyms currently held (to ignore auto-repeat)
        self._pending_hotkey = self.data.get("hotkey", "f9")
        self._active_text = None              # tk.Text of the active notes tab (or None)
        self._active_checklist_frame = None   # row container of the active checklist (or None)

        self._apply_theme()

        self.root = tk.Tk()
        self.root.title("Sticky")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=self.BG)
        self.root.bind("<Escape>", lambda _: self._hide())
        self.root.bind("<Configure>", self._on_root_configure)

        self._build_chrome()
        self._render_tabs()
        self._render_active()
        self._position()
        self.root.withdraw()
        threading.Thread(target=self._hotkey_loop, daemon=True).start()

        # First launch: greet the user and let them pick their own shortcut in case
        # F9 already does something else on their machine.
        if not self.data.get("hotkey_prompted", True):
            self.root.after(400, self._first_run)

    # ── theme ─────────────────────────────────────────────────────────────────
    def _theme(self) -> dict:
        th = self.data.setdefault("theme", _default_theme())
        for k, v in _default_theme().items():
            th.setdefault(k, v)
        return th

    def _apply_theme(self):
        """Compute the working palette + font size from the saved theme."""
        th = self._theme()
        base = th["base"]
        text = th.get("text") or _contrast(base)
        box = th.get("box_shade", 50)
        self.font_size = int(th.get("font_size", 11))

        self.ACCENT = th["accent"]
        self.BG     = base
        self.HEADER = _shade(base, 0.07)
        self.SEP    = _shade(base, 0.14)
        self.SEL    = _shade(base, 0.20)
        self.ENTRY  = _shade(base, 0.02 + (box / 100.0) * 0.22)   # text-box background
        self.FG     = text
        self.DIM    = _blend(text, base, 0.55)
        self.DONE   = _blend(text, base, 0.70)
        self.CHK    = _blend(text, base, 0.40)
        self.GRIP   = _blend(text, base, 0.45)

    def _f(self, delta=0, bold=False):
        size = max(7, self.font_size + delta)
        return (FONT_FAMILY, size, "bold") if bold else (FONT_FAMILY, size)

    def _retheme(self):
        self._apply_theme()
        self.root.configure(bg=self.BG)
        self._build_chrome()
        self._render_tabs()
        self._render_active()
        if self._settings_win and self._settings_win.winfo_exists():
            self._build_settings_panel()

    # ── small helpers ────────────────────────────────────────────────────────
    def _tabs(self) -> list:
        return self.data["tabs"]

    def _active_tab(self) -> dict:
        for t in self._tabs():
            if t["id"] == self.data.get("active"):
                return t
        return self._tabs()[0]

    # ── window chrome (header, tab strip, body, grip) ─────────────────────────
    def _build_chrome(self):
        if getattr(self, "_main", None) is not None and self._main.winfo_exists():
            self._main.destroy()
        self._main = tk.Frame(self.root, bg=self.BG)
        self._main.pack(fill="both", expand=True)
        m = self._main

        # header
        hdr = tk.Frame(m, bg=self.HEADER, height=38)
        hdr.pack(fill="x"); hdr.pack_propagate(False)

        dot = tk.Label(hdr, text="●", fg=self.ACCENT, bg=self.HEADER,
                       font=(FONT_FAMILY, 13))
        dot.pack(side="left", padx=(10, 4))
        title = tk.Label(hdr, text="notes", fg=self.FG, bg=self.HEADER,
                         font=self._f(0, bold=True))
        title.pack(side="left")

        close = tk.Label(hdr, text="✕", fg=self.DIM, bg=self.HEADER,
                         font=(FONT_FAMILY, 12), cursor="hand2")
        close.pack(side="right", padx=(4, 10))
        close.bind("<Button-1>", lambda _: self._hide())
        self._hover(close)

        gear = tk.Label(hdr, text="⚙", fg=self.DIM, bg=self.HEADER,
                        font=("Segoe UI Symbol", 12), cursor="hand2")
        gear.pack(side="right", padx=2)
        gear.bind("<Button-1>", lambda _: self._toggle_settings())
        self._hover(gear)

        for w in (hdr, dot, title):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        # tab strip (contents rebuilt by _render_tabs)
        self._tabbar = tk.Frame(m, bg=self.BG)
        self._tabbar.pack(fill="x")
        tk.Frame(m, bg=self.SEP, height=1).pack(fill="x")

        # body (contents rebuilt by _render_active)
        self._body = tk.Frame(m, bg=self.BG)
        self._body.pack(fill="both", expand=True)

        # resize grip — floats over the bottom-right corner
        grip = tk.Label(m, text="◢", fg=self.GRIP, bg=self.BG,
                        font=(FONT_FAMILY, 13), cursor="size_nw_se")
        grip.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-2)
        grip.bind("<ButtonPress-1>", self._resize_start)
        grip.bind("<B1-Motion>", self._resize_move)
        grip.bind("<ButtonRelease-1>", self._resize_end)
        grip.bind("<Enter>", lambda _: grip.config(fg=self.ACCENT))
        grip.bind("<Leave>", lambda _: grip.config(fg=self.GRIP))

    def _hover(self, widget):
        widget.bind("<Enter>", lambda _: widget.config(fg=self.ACCENT))
        widget.bind("<Leave>", lambda _: widget.config(fg=self.DIM))

    # ── tab strip ─────────────────────────────────────────────────────────────
    def _render_tabs(self):
        for w in self._tabbar.winfo_children():
            w.destroy()
        active = self.data.get("active")
        for t in self._tabs():
            lbl = tk.Label(self._tabbar, text=t["name"].upper(),
                           fg=self.ACCENT if t["id"] == active else self.DIM,
                           bg=self.BG, font=self._f(-2, bold=True),
                           pady=6, cursor="hand2")
            lbl.pack(side="left", padx=10)
            lbl.bind("<Button-1>", lambda _, i=t["id"]: self._switch(i))
            lbl.bind("<Button-3>", lambda e, i=t["id"]: self._tab_menu(e, i))

        plus = tk.Label(self._tabbar, text="＋", fg=self.DIM, bg=self.BG,
                        font=self._f(1, bold=True), pady=4, cursor="hand2")
        plus.pack(side="left", padx=(4, 0))
        plus.bind("<Button-1>", lambda _: self._open_add_tab())
        self._hover(plus)

    def _switch(self, tab_id):
        self.data["active"] = tab_id
        save(self.data)
        self._render_tabs()
        self._render_active()

    def _tab_menu(self, event, tab_id):
        m = tk.Menu(self.root, tearoff=0, bg=self.HEADER, fg=self.FG,
                    activebackground=self.ACCENT, activeforeground=_contrast(self.ACCENT),
                    bd=0)
        m.add_command(label="Rename", command=lambda: self._rename_tab(tab_id))
        m.add_command(label="Delete", command=lambda: self._delete_tab(tab_id))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    # ── add / rename / delete tabs ────────────────────────────────────────────
    def _open_add_tab(self):
        if self._popup_win and self._popup_win.winfo_exists():
            self._popup_win.lift()
            return
        win = tk.Toplevel(self.root)
        self._popup_win = win
        win.title("New tab")
        win.configure(bg=self.HEADER)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.geometry("+%d+%d" % (self.root.winfo_rootx() + 30,
                                 self.root.winfo_rooty() + 60))

        tk.Label(win, text="Tab name", fg=self.FG, bg=self.HEADER,
                 font=self._f(-1)).pack(anchor="w", padx=14, pady=(14, 2))
        name_var = tk.StringVar()
        ent = tk.Entry(win, textvariable=name_var, bg=self.ENTRY, fg=self.FG,
                       insertbackground=self.ACCENT, font=self._f(0),
                       relief="flat", bd=4, width=24)
        ent.pack(padx=14)
        ent.focus_set()

        type_var = tk.StringVar(value="text")
        tk.Label(win, text="Type", fg=self.FG, bg=self.HEADER,
                 font=self._f(-1)).pack(anchor="w", padx=14, pady=(12, 2))
        for val, label in (("text", "Notes pad (free text)"),
                           ("checklist", "Checklist (to-do list)")):
            tk.Radiobutton(win, text=label, variable=type_var, value=val,
                           fg=self.FG, bg=self.HEADER, selectcolor=self.ENTRY,
                           activebackground=self.HEADER, activeforeground=self.ACCENT,
                           font=self._f(-1), anchor="w",
                           highlightthickness=0, bd=0).pack(anchor="w", padx=14)

        def create(_=None):
            name = name_var.get().strip() or "TAB"
            tab = {"id": _new_id(), "name": name, "type": type_var.get()}
            if tab["type"] == "checklist":
                tab["items"] = []
            else:
                tab["content"] = ""
            self.data["tabs"].append(tab)
            self.data["active"] = tab["id"]
            save(self.data)
            self._close_popup()
            self._render_tabs()
            self._render_active()

        bar = tk.Frame(win, bg=self.HEADER)
        bar.pack(fill="x", padx=14, pady=14)
        self._button(bar, "Add", create).pack(side="right")
        self._button(bar, "Cancel", lambda: self._close_popup(),
                     fg=self.FG, bg=self.ENTRY).pack(side="right", padx=(0, 8))
        ent.bind("<Return>", create)
        win.bind("<Escape>", lambda _: self._close_popup())

    def _rename_tab(self, tab_id):
        tab = next((t for t in self._tabs() if t["id"] == tab_id), None)
        if not tab:
            return
        self.root.attributes("-topmost", False)
        name = simpledialog.askstring("Rename tab", "New name:",
                                      initialvalue=tab["name"], parent=self.root)
        self.root.attributes("-topmost", True)
        if name and name.strip():
            tab["name"] = name.strip()
            save(self.data)
            self._render_tabs()

    def _delete_tab(self, tab_id):
        tabs = self._tabs()
        if len(tabs) <= 1:
            self._info("You need at least one tab.")
            return
        idx = next((i for i, t in enumerate(tabs) if t["id"] == tab_id), None)
        if idx is None:
            return
        tab = tabs[idx]
        has_content = ((tab["type"] == "text" and tab.get("content", "").strip())
                       or (tab["type"] == "checklist" and tab.get("items")))
        if has_content and not self._confirm(f'Delete tab "{tab["name"]}" and everything in it?'):
            return
        tabs.pop(idx)
        if self.data.get("active") == tab_id:
            self.data["active"] = tabs[max(0, idx - 1)]["id"]
        save(self.data)
        self._render_tabs()
        self._render_active()

    # ── active page rendering ─────────────────────────────────────────────────
    def _render_active(self):
        for w in self._body.winfo_children():
            w.destroy()
        self._active_text = None
        self._active_checklist_frame = None
        tab = self._active_tab()
        if tab["type"] == "checklist":
            self._build_checklist(tab)
        else:
            self._build_text(tab)

    def _build_text(self, tab):
        txt = tk.Text(self._body, bg=self.ENTRY, fg=self.FG,
                      insertbackground=self.ACCENT, font=self._f(0),
                      relief="flat", padx=10, pady=10, wrap="word",
                      selectbackground=self.SEL, borderwidth=0)
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", tab.get("content", ""))

        def _save(_=None):
            tab["content"] = txt.get("1.0", "end-1c")
            save(self.data)

        txt.bind("<KeyRelease>", _save)
        self._active_text = txt
        txt.focus_set()

    def _build_checklist(self, tab):
        items = tab.setdefault("items", [])

        container = tk.Frame(self._body, bg=self.BG)
        container.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        canvas = tk.Canvas(container, bg=self.BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame = tk.Frame(canvas, bg=self.BG)
        win = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.winfo_exists() and
                        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        addbar = tk.Frame(self._body, bg=self.BG)
        addbar.pack(fill="x", padx=8, pady=(0, 8))
        entry = tk.Entry(addbar, bg=self.ENTRY, fg=self.FG, insertbackground=self.ACCENT,
                         font=self._f(-1), relief="flat", bd=4)
        entry.pack(side="left", fill="x", expand=True)
        plus = tk.Label(addbar, text="＋", fg=self.ACCENT, bg=self.BG,
                        font=self._f(3), cursor="hand2")
        plus.pack(side="right", padx=(8, 0))

        self._active_checklist_frame = frame

        def render():
            for w in frame.winfo_children():
                w.destroy()
            wrap = max(80, self.root.winfo_width() - 80)
            for i, item in enumerate(items):
                row = tk.Frame(frame, bg=self.BG)
                row.pack(fill="x", pady=2)
                done = item.get("done", False)
                ck = tk.Label(row, text="☑" if done else "☐",
                              fg=self.ACCENT if done else self.CHK,
                              bg=self.BG, font=self._f(2), cursor="hand2")
                ck.pack(side="left", padx=(0, 6))
                ck.bind("<Button-1>", lambda _, i=i: toggle(i))
                lbl = tk.Label(row, text=item.get("text", ""),
                               fg=self.DONE if done else self.FG, bg=self.BG,
                               font=self._f(-1), anchor="w", justify="left",
                               cursor="hand2", wraplength=wrap)
                lbl.pack(side="left", fill="x", expand=True)
                lbl.bind("<Button-1>", lambda _, i=i: toggle(i))
                x = tk.Label(row, text="✕", fg=self.DIM, bg=self.BG,
                             font=self._f(-1), cursor="hand2")
                x.pack(side="right", padx=4)
                x.bind("<Button-1>", lambda _, i=i: delete(i))

        def add(_=None):
            t = entry.get().strip()
            if t:
                items.append({"text": t, "done": False})
                save(self.data)
                entry.delete(0, "end")
                render()

        def toggle(i):
            items[i]["done"] = not items[i].get("done", False)
            save(self.data)
            render()

        def delete(i):
            items.pop(i)
            save(self.data)
            render()

        entry.bind("<Return>", add)
        plus.bind("<Button-1>", add)
        render()
        entry.focus_set()

    # ── settings ──────────────────────────────────────────────────────────────
    def _toggle_settings(self):
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.destroy()
            self._settings_win = None
            return
        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        x = self.root.winfo_rootx() + self.root.winfo_width() + 8
        y = self.root.winfo_rooty()
        sw = self.root.winfo_screenwidth()
        if x + 250 > sw:                      # not enough room on the right -> go left
            x = max(0, self.root.winfo_rootx() - 250)
        win.geometry("+%d+%d" % (max(0, x), max(0, y)))
        self._build_settings_panel()
        win.bind("<Escape>", lambda _: self._toggle_settings())

    def _build_settings_panel(self):
        win = self._settings_win
        for w in win.winfo_children():
            w.destroy()
        win.configure(bg=self.HEADER, highlightbackground=self.SEP, highlightthickness=1)
        th = self._theme()

        bar = tk.Frame(win, bg=self.HEADER)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        tl = tk.Label(bar, text="SETTINGS", fg=self.ACCENT, bg=self.HEADER,
                      font=self._f(-2, bold=True))
        tl.pack(side="left")
        cl = tk.Label(bar, text="✕", fg=self.DIM, bg=self.HEADER,
                      font=self._f(-1), cursor="hand2")
        cl.pack(side="right")
        cl.bind("<Button-1>", lambda _: self._toggle_settings())
        for w in (bar, tl):
            w.bind("<ButtonPress-1>", self._set_drag_start)
            w.bind("<B1-Motion>", self._set_drag_move)

        def row(label):
            f = tk.Frame(win, bg=self.HEADER)
            f.pack(fill="x", padx=12, pady=4)
            tk.Label(f, text=label, fg=self.FG, bg=self.HEADER,
                     font=self._f(-2)).pack(side="left")
            return f

        f = row("Theme color")
        self._swatch(f, th["base"], lambda c: self._set_theme("base", c))

        f = row("Accent color")
        self._swatch(f, th["accent"], lambda c: self._set_theme("accent", c))

        f = row("Text color")
        self._swatch(f, th.get("text") or _contrast(th["base"]),
                     lambda c: self._set_theme("text", c))
        self._mini(f, "Auto", lambda: self._set_theme("text", None)).pack(side="right", padx=(0, 6))

        f = row("Text size")
        self._mini(f, "+", lambda: self._bump_font(1)).pack(side="right")
        tk.Label(f, text=str(self.font_size), fg=self.ACCENT, bg=self.HEADER,
                 font=self._f(-2, bold=True), width=3).pack(side="right")
        self._mini(f, "–", lambda: self._bump_font(-1)).pack(side="right", padx=(0, 4))

        f = row("Shortcut")
        tk.Label(f, text=self._pretty_hotkey(self.data.get("hotkey", "f9")),
                 fg=self.ACCENT, bg=self.HEADER,
                 font=self._f(-2, bold=True)).pack(side="right")
        self._mini(f, "Change", lambda: self._open_hotkey_setup()).pack(side="right", padx=(0, 8))

        tk.Label(win, text="Text background shade", fg=self.FG, bg=self.HEADER,
                 font=self._f(-3)).pack(anchor="w", padx=12, pady=(8, 0))
        sc = tk.Scale(win, from_=0, to=100, orient="horizontal", bg=self.HEADER,
                      fg=self.FG, troughcolor=self.ENTRY, highlightthickness=0, bd=0,
                      sliderrelief="flat", activebackground=self.ACCENT, length=210)
        sc.set(int(th.get("box_shade", 50)))
        sc.pack(padx=12)
        sc.config(command=self._box_shade_live)
        sc.bind("<ButtonRelease-1>", lambda _: self._set_theme("box_shade", int(float(sc.get()))))

        self._mini(win, "Reset to defaults", self._reset_theme).pack(pady=(8, 12))

    def _swatch(self, parent, color, on_pick):
        sw = tk.Label(parent, text="    ", bg=color, cursor="hand2",
                      highlightbackground=self.SEP, highlightthickness=1)
        sw.pack(side="right")
        sw.bind("<Button-1>", lambda _: self._pick_color(color, on_pick))

    def _mini(self, parent, text, cmd):
        b = tk.Label(parent, text=text, fg=self.FG, bg=self.ENTRY,
                     font=self._f(-2, bold=True), cursor="hand2", padx=8, pady=2)
        b.bind("<Button-1>", lambda _: cmd())
        return b

    def _pick_color(self, initial, on_pick):
        parent = self._settings_win if (self._settings_win and self._settings_win.winfo_exists()) else self.root
        self.root.attributes("-topmost", False)
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.attributes("-topmost", False)
        try:
            _, hexv = colorchooser.askcolor(color=initial, parent=parent, title="Pick a color")
        finally:
            self.root.attributes("-topmost", True)
            if self._settings_win and self._settings_win.winfo_exists():
                self._settings_win.attributes("-topmost", True)
        if hexv:
            on_pick(hexv)

    def _set_theme(self, key, value):
        self._theme()[key] = value
        save(self.data)
        self._retheme()

    def _bump_font(self, d):
        self._theme()["font_size"] = max(8, min(28, int(self._theme().get("font_size", 11)) + d))
        save(self.data)
        self._retheme()

    def _box_shade_live(self, v):
        # live preview while dragging; persisted on release via _set_theme
        box = int(float(v))
        self.ENTRY = _shade(self._theme()["base"], 0.02 + (box / 100.0) * 0.22)
        if self._active_text is not None and self._active_text.winfo_exists():
            self._active_text.config(bg=self.ENTRY)

    def _reset_theme(self):
        self.data["theme"] = _default_theme()
        save(self.data)
        self._retheme()

    # ── keyboard shortcut setup ────────────────────────────────────────────────
    def _pretty_hotkey(self, hk) -> str:
        names = {"ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift",
                 "windows": "Win", "win": "Win", "cmd": "Cmd", "esc": "Esc"}
        steps = []
        for step in str(hk).split(","):
            parts = [p.strip() for p in step.split("+") if p.strip()]
            if not parts:
                continue
            steps.append(" + ".join(
                names.get(p.lower(), p.upper() if len(p) <= 2 else p.capitalize())
                for p in parts))
        return "  ,  ".join(steps) if steps else "—"

    def _first_run(self):
        """Greet a brand-new user and let them set their own shortcut right away."""
        self._show()
        self._open_hotkey_setup(first_run=True)

    def _open_hotkey_setup(self, first_run=False):
        if self._popup_win and self._popup_win.winfo_exists():
            self._popup_win.lift()
            return
        self._pending_hotkey = self.data.get("hotkey", "f9")

        win = tk.Toplevel(self.root)
        self._popup_win = win
        win.title("Keyboard shortcut")
        win.configure(bg=self.HEADER, highlightbackground=self.SEP, highlightthickness=1)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.geometry("+%d+%d" % (self.root.winfo_rootx() + 24,
                                 self.root.winfo_rooty() + 44))

        tk.Label(win, text="Show / hide shortcut", fg=self.ACCENT, bg=self.HEADER,
                 font=self._f(0, bold=True)).pack(anchor="w", padx=16, pady=(14, 2))
        msg = ("Welcome! Press your shortcut anywhere to show or hide this note.\n"
               "F9 is the default — if another app already uses it, pick your own."
               if first_run else
               "Choose the shortcut that shows and hides this note from anywhere.")
        tk.Label(win, text=msg, fg=self.FG, bg=self.HEADER, font=self._f(-2),
                 justify="left").pack(anchor="w", padx=16)

        self._recording = False
        self._rec_keys = []
        self._rec_label = tk.Label(win, text=self._pretty_hotkey(self._pending_hotkey),
                                   fg=self.FG, bg=self.ENTRY, font=self._f(1, bold=True),
                                   padx=12, pady=10, width=22)
        self._rec_label.pack(padx=16, pady=(12, 6))

        self._rec_button = self._button(win, "Record a shortcut", self._toggle_record)
        self._rec_button.pack(padx=16)
        tk.Label(win, text="Tip: hold the keys you want together, then click Done.",
                 fg=self.DIM, bg=self.HEADER, font=self._f(-3)).pack(anchor="w", padx=16, pady=(4, 0))

        tk.Label(win, text="…or tap a quick pick:", fg=self.DIM, bg=self.HEADER,
                 font=self._f(-3)).pack(anchor="w", padx=16, pady=(12, 2))
        grid = tk.Frame(win, bg=self.HEADER)
        grid.pack(padx=14, pady=(0, 2))
        picks = ["f9", "f8", "f10", "ctrl+shift+s", "ctrl+alt+n", "pause"]
        for idx, combo in enumerate(picks):
            self._mini(grid, self._pretty_hotkey(combo),
                       lambda c=combo: self._set_pending(c)
                       ).grid(row=idx // 3, column=idx % 3, padx=3, pady=3, sticky="ew")

        bar = tk.Frame(win, bg=self.HEADER)
        bar.pack(fill="x", padx=16, pady=14)
        self._button(bar, "Save", self._save_hotkey).pack(side="right")
        keep_text = "Keep F9" if first_run else "Cancel"
        self._button(bar, keep_text, self._cancel_hotkey,
                     fg=self.FG, bg=self.ENTRY).pack(side="right", padx=(0, 8))
        win.bind("<Escape>", lambda _: self._cancel_hotkey())
        win.protocol("WM_DELETE_WINDOW", self._cancel_hotkey)

    def _set_pending(self, combo):
        self._pending_hotkey = combo
        if self._rec_label and self._rec_label.winfo_exists():
            self._rec_label.config(text=self._pretty_hotkey(combo), fg=self.FG)

    # Keys that are modifiers only — we wait for a "real" key to finish the combo.
    _MOD_KEYSYMS = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
                    "Meta_L", "Meta_R", "Super_L", "Super_R", "Win_L", "Win_R",
                    "Caps_Lock", "Num_Lock", "Mode_switch", "ISO_Level3_Shift"}
    # tkinter keysym -> name the `keyboard` library understands.
    _KEYSYM_MAP = {"space": "space", "Return": "enter", "Tab": "tab",
                   "BackSpace": "backspace", "Delete": "delete", "Insert": "insert",
                   "Home": "home", "End": "end", "Prior": "page up", "Next": "page down",
                   "Up": "up", "Down": "down", "Left": "left", "Right": "right",
                   "Pause": "pause", "Print": "print screen", "Menu": "menu"}
    # modifier keysyms -> their canonical names (left/right collapse to one)
    _MOD_CANON = {"Shift_L": "shift", "Shift_R": "shift",
                  "Control_L": "ctrl", "Control_R": "ctrl",
                  "Alt_L": "alt", "Alt_R": "alt",
                  "Win_L": "windows", "Win_R": "windows",
                  "Super_L": "windows", "Super_R": "windows",
                  "Meta_L": "windows", "Meta_R": "windows"}
    _MOD_ORDER = {"ctrl": 0, "alt": 1, "shift": 2, "windows": 3}

    def _canon_key(self, keysym):
        """tkinter keysym -> a single canonical key name (or None to ignore)."""
        if keysym in self._MOD_CANON:
            return self._MOD_CANON[keysym]
        if keysym in ("Caps_Lock", "Num_Lock", "Mode_switch", "ISO_Level3_Shift"):
            return None
        return self._KEYSYM_MAP.get(keysym, keysym.lower())

    def _format_chord(self):
        """Build a 'ctrl+shift+r' style string from the captured keys, modifiers first."""
        mods = sorted((k for k in self._rec_keys if k in self._MOD_ORDER),
                      key=lambda k: self._MOD_ORDER[k])
        others = [k for k in self._rec_keys if k not in self._MOD_ORDER]
        return "+".join(mods + others)

    def _toggle_record(self):
        """One button: start recording, or finish (Done) if already recording."""
        if self._recording:
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self):
        self._recording = True
        self._rec_keys = []
        self._rec_down = set()
        if self._rec_label and self._rec_label.winfo_exists():
            self._rec_label.config(text="Press keys…  (Esc cancels)", fg=self.ACCENT)
        if self._rec_button and self._rec_button.winfo_exists():
            self._rec_button.config(text="Done  ✓")
        # Pause the live global shortcut so pressing it can't toggle the window mid-record.
        try:
            keyboard.clear_all_hotkeys()
        except Exception:
            pass
        win = self._popup_win
        if win and win.winfo_exists():
            win.focus_force()
            self._rec_binding = win.bind("<KeyPress>", self._on_record_key)
            self._rec_binding_rel = win.bind("<KeyRelease>", self._on_record_release)

    def _on_record_release(self, e):
        # Key let go — allow it to be recorded again on a fresh press.
        self._rec_down.discard(e.keysym)
        return "break"

    def _on_record_key(self, e):
        if not self._recording:
            return "break"
        if e.keysym == "Escape":                 # cancel this recording
            self._cancel_record()
            return "break"
        if e.keysym in self._rec_down:
            return "break"                       # ignore OS auto-repeat while key is held
        self._rec_down.add(e.keysym)
        name = self._canon_key(e.keysym)
        if name and name not in self._rec_keys:  # each key counts only once
            self._rec_keys.append(name)
            if self._rec_label and self._rec_label.winfo_exists():
                self._rec_label.config(text=self._pretty_hotkey(self._format_chord()),
                                       fg=self.ACCENT)
        return "break"

    def _end_record(self):
        """Shared teardown for both finishing and cancelling a recording."""
        win = self._popup_win
        if win and win.winfo_exists():
            if self._rec_binding:
                try:
                    win.unbind("<KeyPress>", self._rec_binding)
                except Exception:
                    pass
            if self._rec_binding_rel:
                try:
                    win.unbind("<KeyRelease>", self._rec_binding_rel)
                except Exception:
                    pass
        self._rec_binding = None
        self._rec_binding_rel = None
        self._rec_down = set()
        self._rec_keys = []
        self._recording = False
        if self._rec_button and self._rec_button.winfo_exists():
            self._rec_button.config(text="Record a shortcut")
        self._apply_hotkey()        # restore the saved shortcut until they hit Save

    def _stop_record(self):
        combo = self._format_chord()
        self._end_record()
        self._set_pending(combo if combo else self._pending_hotkey)

    def _cancel_record(self):
        self._end_record()
        self._set_pending(self._pending_hotkey)   # discard whatever was pressed

    def _save_hotkey(self):
        if self._recording:                 # finish an in-progress recording first
            self._stop_record()
        self.data["hotkey"] = (self._pending_hotkey or "f9").strip() or "f9"
        self.data["hotkey_prompted"] = True
        save(self.data)
        self._apply_hotkey()
        self._close_popup()
        if self._settings_win and self._settings_win.winfo_exists():
            self._build_settings_panel()
        self._info("Shortcut set to  " + self._pretty_hotkey(self.data["hotkey"]) +
                   "\nPress it anywhere to show or hide your notes.")

    def _cancel_hotkey(self):
        if self._recording:
            self._end_record()
        # Mark as handled either way so first-run users aren't asked again.
        self.data["hotkey_prompted"] = True
        save(self.data)
        self._apply_hotkey()
        self._close_popup()

    # ── styled "button" (Label, so it matches the dark theme) ─────────────────
    def _button(self, parent, text, cmd, fg=None, bg=None):
        bg = bg or self.ACCENT
        fg = fg if fg is not None else _contrast(self.ACCENT)
        b = tk.Label(parent, text=text, fg=fg, bg=bg,
                     font=self._f(-1, bold=True), cursor="hand2", padx=14, pady=4)
        b.bind("<Button-1>", lambda _: cmd())
        return b

    def _close_popup(self):
        if self._popup_win and self._popup_win.winfo_exists():
            self._popup_win.destroy()
        self._popup_win = None

    def _confirm(self, msg) -> bool:
        self.root.attributes("-topmost", False)
        ok = messagebox.askyesno("Sticky", msg, parent=self.root)
        self.root.attributes("-topmost", True)
        return ok

    def _info(self, msg):
        self.root.attributes("-topmost", False)
        messagebox.showinfo("Sticky", msg, parent=self.root)
        self.root.attributes("-topmost", True)

    # ── geometry ──────────────────────────────────────────────────────────────
    def _position(self):
        w = self.data.get("win_w", 340)
        h = self.data.get("win_h", 430)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{sw - w - 24}+{sh - h - 64}")

    def _resize_start(self, e):
        self._resize_origin = (e.x_root, e.y_root,
                               self.root.winfo_width(), self.root.winfo_height())

    def _resize_move(self, e):
        x0, y0, w0, h0 = self._resize_origin
        new_w = max(self.MIN_W, w0 + (e.x_root - x0))
        new_h = max(self.MIN_H, h0 + (e.y_root - y0))
        self.root.geometry(f"{new_w}x{new_h}")

    def _resize_end(self, _e):
        self.data["win_w"] = self.root.winfo_width()
        self.data["win_h"] = self.root.winfo_height()
        save(self.data)

    def _on_root_configure(self, _e=None):
        # keep checklist text wrapped to the current window width
        frame = self._active_checklist_frame
        if frame is not None and frame.winfo_exists():
            wrap = max(80, self.root.winfo_width() - 80)
            for row in frame.winfo_children():
                for child in row.winfo_children():
                    if isinstance(child, tk.Label):
                        try:
                            if int(child.cget("wraplength")) > 0:
                                child.config(wraplength=wrap)
                        except (tk.TclError, ValueError):
                            pass

    # ── drag (titlebar move) ──────────────────────────────────────────────────
    def _drag_start(self, e):
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _set_drag_start(self, e):
        self._sdx = e.x_root - self._settings_win.winfo_x()
        self._sdy = e.y_root - self._settings_win.winfo_y()

    def _set_drag_move(self, e):
        self._settings_win.geometry(f"+{e.x_root - self._sdx}+{e.y_root - self._sdy}")

    # ── show / hide ───────────────────────────────────────────────────────────
    def _show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.visible = True

    def _hide(self):
        if self._active_text is not None and self._active_text.winfo_exists():
            self._active_tab()["content"] = self._active_text.get("1.0", "end-1c")
            save(self.data)
        for w in (self._settings_win, self._popup_win):
            if w and w.winfo_exists():
                w.destroy()
        self._settings_win = None
        self._popup_win = None
        self.root.withdraw()
        self.visible = False

    def _toggle_window(self):
        self.root.after(0, self._hide if self.visible else self._show)

    # ── hotkey loop ───────────────────────────────────────────────────────────
    def _apply_hotkey(self):
        """(Re)register the global show/hide shortcut from self.data['hotkey'].
        Falls back to F9 if the saved combo is invalid."""
        try:
            keyboard.clear_all_hotkeys()
        except Exception:
            pass
        hk = (self.data.get("hotkey") or "f9").strip() or "f9"
        try:
            keyboard.add_hotkey(hk, self._toggle_window, suppress=False)
        except Exception:
            try:
                keyboard.add_hotkey("f9", self._toggle_window, suppress=False)
                self.data["hotkey"] = "f9"
            except Exception:
                pass

    def _hotkey_loop(self):
        self._apply_hotkey()
        keyboard.wait()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    StickyNote().run()
