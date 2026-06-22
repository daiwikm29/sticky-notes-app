"""
F9 Sticky Note
==============
A lightweight floating sticky note that lives in the corner of your screen.
Press F9 anywhere to show or hide it. Everything auto-saves.

HOW TO USE:
1. Install the one dependency:  pip install -r requirements.txt
2. Run it:                      python sticky_launcher.py
3. Press F9 anywhere on your PC to show/hide the note window.
4. Drag the title bar to move it; drag the corner grip to resize.
5. Everything auto-saves. Nothing is lost when you hide it.

RUN ON STARTUP (optional):
  Press Win+R -> type: shell:startup -> OK
  Put a shortcut to this file in that folder.

Your notes are stored in your personal app-data folder, so every user on the
machine gets their own separate notes automatically. See get_data_dir() below.
"""

import os
import sys
import json
import shutil
import tempfile
import threading
from pathlib import Path

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


# ── Data location & persistence ───────────────────────────────────────────────
APP_NAME = "F9StickyNote"


def get_data_dir() -> Path:
    """Return this user's app-data folder, creating it if needed.

    Each OS user gets their own folder, so notes are never shared between
    accounts and the file is kept out of the home directory's top level.
    """
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux / other
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    data_dir = base / APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


SAVE_FILE = get_data_dir() / "sticky_data.json"

DEFAULTS = {"notes": "", "todos": [], "tech": [], "win_w": 340, "win_h": 430}


def load() -> dict:
    """Load saved data. If the file is missing, return defaults. If it is
    corrupt, back it up so the user can recover it, then start fresh."""
    if not SAVE_FILE.exists():
        return dict(DEFAULTS)
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Don't silently wipe the user's data — preserve the broken file.
        backup = SAVE_FILE.with_suffix(".json.corrupt")
        try:
            shutil.copy2(SAVE_FILE, backup)
            sys.stderr.write(
                f"\nWarning: notes file was unreadable. A backup was saved to:\n"
                f"    {backup}\nStarting with empty notes.\n\n"
            )
        except OSError:
            pass
        return dict(DEFAULTS)

    # Fill in any keys missing from older save files.
    for key, default in DEFAULTS.items():
        data.setdefault(key, default)
    return data


def save(data: dict) -> None:
    """Write data atomically: write to a temp file, then replace the real one.

    A rename is atomic on every OS, so the notes file is never left half-written
    if the program crashes or is force-quit mid-save.
    """
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(SAVE_FILE.parent), prefix=".sticky_", suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, SAVE_FILE)
    except OSError as e:
        sys.stderr.write(f"\nWarning: could not save notes: {e}\n")
        try:
            os.unlink(tmp_path)
        except (OSError, NameError):
            pass


# ── UI ────────────────────────────────────────────────────────────────────────
class StickyNote:
    BG     = "#141414"
    HEADER = "#1e1e1e"
    ENTRY  = "#242424"
    ACCENT = "#f5c518"
    FG     = "#ececec"
    DIM    = "#555"
    DONE   = "#484848"

    MIN_W = 240
    MIN_H = 200

    def __init__(self):
        self.data    = load()
        self.visible = False
        self.root    = tk.Tk()
        self._build()
        self._position()
        self.root.withdraw()
        # hotkey on background thread
        threading.Thread(target=self._hotkey_loop, daemon=True).start()

    # ── build ──────────────────────────────────────────────────────────────
    def _build(self):
        r = self.root
        r.title("Sticky")
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-alpha", 0.96)
        r.configure(bg=self.BG)
        r.resizable(True, True)
        r.bind("<Escape>", lambda _: self._hide())

        # header
        hdr = tk.Frame(r, bg=self.HEADER, height=38)
        hdr.pack(fill="x"); hdr.pack_propagate(False)

        tk.Label(hdr, text="●", fg=self.ACCENT, bg=self.HEADER,
                 font=("Courier New", 13)).pack(side="left", padx=(10, 4))
        tk.Label(hdr, text="notes", fg=self.FG, bg=self.HEADER,
                 font=("Courier New", 11, "bold")).pack(side="left")

        close = tk.Label(hdr, text="✕", fg=self.DIM, bg=self.HEADER,
                         font=("Courier New", 12), cursor="hand2")
        close.pack(side="right", padx=10)
        close.bind("<Button-1>", lambda _: self._hide())

        for w in hdr.winfo_children():
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_move)

        # tabs
        tabs = tk.Frame(r, bg=self.BG)
        tabs.pack(fill="x")
        self._tab_labels = {}
        for name, label in [("scratch", "SCRATCH"), ("todo", "TO-DO"), ("tech", "TECH")]:
            lbl = tk.Label(tabs, text=label, fg=self.DIM, bg=self.BG,
                           font=("Courier New", 9, "bold"), pady=6, cursor="hand2")
            lbl.pack(side="left", padx=12)
            lbl.bind("<Button-1>", lambda _, n=name: self._switch(n))
            self._tab_labels[name] = lbl

        tk.Frame(r, bg="#2a2a2a", height=1).pack(fill="x")

        # body container holds the pages; resize grip sits over its corner
        self._body = tk.Frame(r, bg=self.BG)
        self._body.pack(fill="both", expand=True)

        # pages
        self._page_scratch = tk.Frame(self._body, bg=self.BG)
        self._page_todo    = tk.Frame(self._body, bg=self.BG)
        self._page_tech    = tk.Frame(self._body, bg=self.BG)

        # scratch
        self.txt = tk.Text(self._page_scratch, bg=self.ENTRY, fg=self.FG,
                           insertbackground=self.ACCENT, font=("Courier New", 11),
                           relief="flat", padx=10, pady=10, wrap="word",
                           selectbackground="#3a3a3a", borderwidth=0)
        self.txt.pack(fill="both", expand=True, padx=8, pady=8)
        self.txt.insert("1.0", self.data.get("notes", ""))
        self.txt.bind("<KeyRelease>", self._schedule_save)

        # todo list — scrollable canvas
        self._canvas, self._todo_frame, self.entry = self._build_checklist_page(
            self._page_todo, self._add_todo
        )

        # tech list — scrollable canvas (same style as todo)
        self._tech_canvas, self._tech_frame, self.tech_entry = self._build_checklist_page(
            self._page_tech, self._add_tech
        )

        # resize grip — bottom-right corner, floats above everything
        grip = tk.Label(r, text="◢", fg=self.DIM, bg=self.BG,
                        font=("Courier New", 11), cursor="size_nw_se")
        grip.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-2)
        grip.bind("<ButtonPress-1>",   self._resize_start)
        grip.bind("<B1-Motion>",       self._resize_move)
        grip.bind("<ButtonRelease-1>", self._resize_end)

        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        self._render_todos()
        self._render_tech()
        self._switch("scratch")

        # rewrap on any resize of the window
        r.bind("<Configure>", self._on_root_configure)

    # ── reusable checklist page builder ───────────────────────────────────
    def _build_checklist_page(self, page, add_fn):
        canvas_container = tk.Frame(page, bg=self.BG)
        canvas_container.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        canvas = tk.Canvas(canvas_container, bg=self.BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        item_frame = tk.Frame(canvas, bg=self.BG)
        canvas_window = canvas.create_window((0, 0), window=item_frame, anchor="nw")

        item_frame.bind("<Configure>", lambda _, c=canvas: c.configure(scrollregion=c.bbox("all")))
        canvas.bind("<Configure>", lambda e, c=canvas, w=canvas_window: c.itemconfig(w, width=e.width))

        # add-item bar
        add = tk.Frame(page, bg=self.BG)
        add.pack(fill="x", padx=8, pady=(0, 8))
        entry = tk.Entry(add, bg=self.ENTRY, fg=self.FG,
                         insertbackground=self.ACCENT,
                         font=("Courier New", 10), relief="flat", bd=4)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", add_fn)
        plus = tk.Label(add, text="＋", fg=self.ACCENT, bg=self.BG,
                        font=("Courier New", 14), cursor="hand2")
        plus.pack(side="right", padx=(8, 0))
        plus.bind("<Button-1>", add_fn)

        return canvas, item_frame, entry

    def _position(self):
        w = self.data.get("win_w", 340)
        h = self.data.get("win_h", 430)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{sw - w - 24}+{sh - h - 64}")

    # ── resize handling ───────────────────────────────────────────────────
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
        # recompute checklist text wraplength to fit current width
        w = self.root.winfo_width()
        wrap = max(80, w - 80)  # leave room for checkbox + delete icon + padding
        self._rewrap(self._todo_frame, wrap)
        self._rewrap(self._tech_frame, wrap)

    def _rewrap(self, frame, wrap):
        for row in frame.winfo_children():
            for child in row.winfo_children():
                if isinstance(child, tk.Label) and child.cget("wraplength"):
                    child.config(wraplength=wrap)

    def _on_mousewheel(self, e):
        canvas = self._canvas if self._tab == "todo" else self._tech_canvas
        if self._tab in ("todo", "tech"):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    # ── tabs ───────────────────────────────────────────────────────────────
    def _switch(self, tab):
        self._tab = tab
        for name, lbl in self._tab_labels.items():
            lbl.config(fg=self.ACCENT if name == tab else self.DIM)

        self._page_scratch.pack_forget()
        self._page_todo.pack_forget()
        self._page_tech.pack_forget()

        if tab == "scratch":
            self._page_scratch.pack(fill="both", expand=True)
            self.txt.focus_set()
        elif tab == "todo":
            self._page_todo.pack(fill="both", expand=True)
            self.entry.focus_set()
        else:
            self._page_tech.pack(fill="both", expand=True)
            self.tech_entry.focus_set()

    # ── scratch ────────────────────────────────────────────────────────────
    def _schedule_save(self, _=None):
        if hasattr(self, "_save_after_id"):
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = self.root.after(500, self._save_scratch)

    def _save_scratch(self, _=None):
        self.data["notes"] = self.txt.get("1.0", "end-1c")
        save(self.data)

    # ── generic checklist logic ──────────────────────────────────────────
    def _add_item(self, items_list, entry, render_fn):
        t = entry.get().strip()
        if t:
            items_list.append({"text": t, "done": False})
            save(self.data)
            entry.delete(0, "end")
            render_fn()

    def _toggle_item(self, items_list, i, render_fn):
        items_list[i]["done"] = not items_list[i]["done"]
        save(self.data)
        render_fn()

    def _delete_item(self, items_list, i, render_fn):
        items_list.pop(i)
        save(self.data)
        render_fn()

    def _render_checklist(self, frame, items_list, render_fn):
        for w in frame.winfo_children():
            w.destroy()
        wrap = max(80, self.root.winfo_width() - 80)
        for i, item in enumerate(items_list):
            row = tk.Frame(frame, bg=self.BG)
            row.pack(fill="x", pady=2)
            done = item["done"]
            ck = tk.Label(row, text="☑" if done else "☐",
                          fg=self.ACCENT if done else "#888",
                          bg=self.BG, font=("Courier New", 13), cursor="hand2")
            ck.pack(side="left", padx=(0, 6))
            ck.bind("<Button-1>", lambda _, i=i: self._toggle_item(items_list, i, render_fn))
            lbl = tk.Label(row, text=item["text"],
                           fg=self.DONE if done else self.FG,
                           bg=self.BG, font=("Courier New", 10),
                           anchor="w", cursor="hand2",
                           wraplength=wrap, justify="left")
            lbl.pack(side="left", fill="x", expand=True)
            lbl.bind("<Button-1>", lambda _, i=i: self._toggle_item(items_list, i, render_fn))
            x = tk.Label(row, text="✕", fg=self.DIM, bg=self.BG,
                         font=("Courier New", 10), cursor="hand2")
            x.pack(side="right", padx=4)
            x.bind("<Button-1>", lambda _, i=i: self._delete_item(items_list, i, render_fn))

    # ── todos ──────────────────────────────────────────────────────────────
    def _add_todo(self, _=None):
        self._add_item(self.data["todos"], self.entry, self._render_todos)

    def _render_todos(self):
        self._render_checklist(self._todo_frame, self.data["todos"], self._render_todos)

    # ── tech ───────────────────────────────────────────────────────────────
    def _add_tech(self, _=None):
        self._add_item(self.data["tech"], self.tech_entry, self._render_tech)

    def _render_tech(self):
        self._render_checklist(self._tech_frame, self.data["tech"], self._render_tech)

    # ── drag (titlebar move) ──────────────────────────────────────────────
    def _drag_start(self, e):
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    # ── show/hide ──────────────────────────────────────────────────────────
    def _show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.visible = True

    def _hide(self):
        self._save_scratch()
        self.root.withdraw()
        self.visible = False

    def _toggle_window(self):
        self.root.after(0, self._hide if self.visible else self._show)

    # ── hotkey loop ────────────────────────────────────────────────────────
    def _hotkey_loop(self):
        keyboard.add_hotkey("F9", self._toggle_window, suppress=False)
        keyboard.wait()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    StickyNote().run()
