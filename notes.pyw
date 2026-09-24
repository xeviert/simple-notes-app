import ctypes
import json
import os
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
import uuid
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

DATA_FILE = Path(os.environ.get("APPDATA", Path.home())) / "SimpleNotes" / "notes.json"
SAVE_DELAY_MS = 500
APP_TITLE = "Simple Notes"
APP_ID = "SimpleNotes.App"
ICON_FILE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "icon.ico"

SIDEBAR_BG = "#f3f3f3"
EDITOR_BG = "#ffffff"
TEXT_FG = "#1b1b1b"
MUTED_FG = "#6b6b6b"
SELECTED_BG = "#dce9f7"
TEXT_SELECT_BG = "#cce4f7"

# A word, or a run of punctuation, plus the whitespace separating it from the cursor.
WORD_BEFORE = re.compile(r"(?:\w+|[^\w\s]+)?\s*$")
WORD_AFTER = re.compile(r"\s*(?:\w+|[^\w\s]+)?")


def now():
    return datetime.now().isoformat(timespec="milliseconds")


def title_of(note):
    if note.get("title"):
        return note["title"]
    first_line = note["body"].strip().split("\n", 1)[0].strip()
    return first_line[:60] or "Untitled"


def pick_font(*families):
    available = set(tkfont.families())
    return next((f for f in families if f in available), "TkDefaultFont")


def delete_word(event, backward):
    widget = event.widget
    if isinstance(widget, tk.Text):
        if widget.tag_ranges("sel"):
            widget.delete("sel.first", "sel.last")
        elif backward:
            n = len(WORD_BEFORE.search(widget.get("insert linestart", "insert")).group()) or 1
            widget.delete(f"insert-{n}c", "insert")
        else:
            n = len(WORD_AFTER.match(widget.get("insert", "insert lineend")).group()) or 1
            widget.delete("insert", f"insert+{n}c")
    else:
        if widget.selection_present():
            widget.delete("sel.first", "sel.last")
            return "break"
        text, pos = widget.get(), widget.index("insert")
        if backward:
            widget.delete(pos - len(WORD_BEFORE.search(text[:pos]).group()), pos)
        else:
            widget.delete(pos, pos + len(WORD_AFTER.match(text[pos:]).group()))
    return "break"


class NotesStore:
    def __init__(self, path):
        self.path = path
        self.notes = []
        self.window = {}
        self.warning = None
        self.load()

    def load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.notes = data["notes"]
            self.window = data.get("window", {})
        except (ValueError, KeyError, TypeError):
            # Keep the unreadable file around instead of overwriting it on next save.
            backup = self.path.with_name(f"notes.corrupt-{datetime.now():%Y%m%d-%H%M%S}.json")
            self.path.replace(backup)
            self.warning = f"Notes file was unreadable and was moved to:\n{backup}"

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"notes": self.notes, "window": self.window}, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)


class NotesApp(tk.Tk):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.current = None
        self.save_job = None
        self.rename_entry = None

        self.title(APP_TITLE)
        if ICON_FILE.exists():
            self.iconbitmap(default=str(ICON_FILE))
        self.geometry(store.window.get("geometry", "1000x650"))
        if store.window.get("zoomed"):
            self.state("zoomed")
        self.minsize(560, 320)
        self.setup_style()
        self.build_ui()
        self.bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if store.warning:
            self.after(100, lambda: messagebox.showwarning(APP_TITLE, store.warning, parent=self))

        last = self.find(store.window.get("last_id"))
        self.refresh_list()
        visible = self.tree.get_children()
        if last:
            self.open_note(last)
        elif visible:
            self.open_note(self.find(visible[0]))
        else:
            self.new_note()

    def setup_style(self):
        ui = pick_font("Segoe UI Variable Text", "Segoe UI")
        small = pick_font("Segoe UI Variable Small", "Segoe UI")
        self.ui_font = tkfont.Font(family=ui, size=10)
        self.list_font = tkfont.Font(family=ui, size=11)
        self.editor_font = tkfont.Font(family=ui, size=12)
        self.status_font = tkfont.Font(family=small, size=9)
        self.option_add("*Font", self.ui_font)
        self.configure(background=SIDEBAR_BG)

        style = ttk.Style(self)
        style.configure(".", font=self.ui_font)
        style.configure("Sidebar.TFrame", background=SIDEBAR_BG)
        style.configure("Editor.TFrame", background=EDITOR_BG)
        style.configure("Sidebar.TLabel", background=SIDEBAR_BG, foreground=MUTED_FG)
        style.configure("Status.TLabel", background=SIDEBAR_BG, foreground=MUTED_FG, font=self.status_font)
        style.configure(
            "Notes.Treeview", background=SIDEBAR_BG, fieldbackground=SIDEBAR_BG, foreground=TEXT_FG,
            font=self.list_font, borderwidth=0,
            rowheight=int(self.list_font.metrics("linespace") * 2),
        )
        style.map("Notes.Treeview", background=[("selected", SELECTED_BG)], foreground=[("selected", TEXT_FG)])
        style.layout("Notes.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def build_ui(self):
        self.status = ttk.Label(self, style="Status.TLabel", anchor=tk.W, padding=(12, 4))
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, style="Sidebar.TFrame", padding=(10, 10, 6, 6), width=260)
        ttk.Label(left, text="Search", style="Sidebar.TLabel").pack(anchor=tk.W)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_list())
        self.search = ttk.Entry(left, textvariable=self.search_var, font=self.ui_font)
        self.search.pack(fill=tk.X, pady=(2, 8), ipady=2)
        self.search.bind("<Escape>", lambda _e: self.search_var.set(""))
        self.search.bind("<Return>", lambda _e: self.text.focus_set())

        buttons = ttk.Frame(left, style="Sidebar.TFrame")
        buttons.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))
        for label, command in (("New", self.new_note), ("Rename", self.rename_note), ("Delete", self.delete_note)):
            ttk.Button(buttons, text=label, command=command, width=7).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.tree = ttk.Treeview(left, style="Notes.Treeview", show="tree", selectmode="browse")
        self.tree.column("#0", width=240)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.rename_note)
        self.tree.bind("<F2>", self.rename_note)
        self.tree.bind("<Delete>", self.delete_note)
        self.tree.bind("<Button-3>", self.show_menu)
        paned.add(left, weight=1)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Rename", command=self.rename_note)
        self.menu.add_command(label="Delete", command=self.delete_note)

        right = ttk.Frame(paned, style="Editor.TFrame")
        self.text = tk.Text(
            right, wrap=tk.WORD, undo=True, font=self.editor_font, padx=28, pady=22,
            background=EDITOR_BG, foreground=TEXT_FG, insertbackground=TEXT_FG,
            selectbackground=TEXT_SELECT_BG, selectforeground=TEXT_FG, inactiveselectbackground=TEXT_SELECT_BG,
            borderwidth=0, highlightthickness=0, spacing1=2, spacing3=2,
        )
        scroll = ttk.Scrollbar(right, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.bind("<<Modified>>", self.on_edit)
        paned.add(right, weight=3)

    def bind_keys(self):
        for widget_class in ("Text", "TEntry"):
            self.bind_class(widget_class, "<Control-BackSpace>", lambda e: delete_word(e, backward=True))
            self.bind_class(widget_class, "<Control-Delete>", lambda e: delete_word(e, backward=False))

        for seq, handler in (
            ("<Control-n>", self.new_note), ("<Control-N>", self.new_note),
            ("<Control-f>", self.focus_search), ("<Control-F>", self.focus_search),
        ):
            self.bind_all(seq, handler)
            # Instance binding runs before Text's class bindings, so "break" overrides them.
            self.text.bind(seq, handler)
        # Bound per widget so it wins over the Ctrl+Delete word binding above.
        for widget in (self.text, self.search, self.tree):
            widget.bind("<Control-Shift-Delete>", self.delete_note)

    def find(self, note_id):
        return next((n for n in self.store.notes if n["id"] == note_id), None)

    def refresh_list(self):
        words = self.search_var.get().lower().split()
        notes = sorted(self.store.notes, key=lambda n: n["modified"], reverse=True)
        self.tree.delete(*self.tree.get_children())
        for note in notes:
            haystack = f"{note.get('title', '')}\n{note['body']}".lower()
            if all(word in haystack for word in words):
                self.tree.insert("", tk.END, iid=note["id"], text=f"  {title_of(note)}")
        if self.current and self.tree.exists(self.current["id"]):
            self.tree.selection_set(self.current["id"])
            self.tree.see(self.current["id"])

    def update_status(self, extra=""):
        count = f"{len(self.store.notes)} note{'s' if len(self.store.notes) != 1 else ''}"
        if self.current is None:
            text = f"{count}   ·   Press Ctrl+N to create a note"
        else:
            modified = datetime.fromisoformat(self.current["modified"]).strftime("%b %d, %Y %I:%M %p")
            text = f"Edited {modified}   ·   {count}"
        self.status.configure(text=f"{text}   ·   {extra}" if extra else text)

    def open_note(self, note):
        self.current = note
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", note["body"])
        self.text.mark_set(tk.INSERT, "1.0")
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.refresh_list()
        self.update_status()

    def show_empty(self):
        self.current = None
        self.text.delete("1.0", tk.END)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.configure(state=tk.DISABLED)
        self.refresh_list()
        self.update_status()

    def on_select(self, _event=None):
        selection = self.tree.selection()
        if selection and (self.current is None or selection[0] != self.current["id"]):
            self.open_note(self.find(selection[0]))

    def show_menu(self, event):
        note_id = self.tree.identify_row(event.y)
        if note_id:
            if self.current is None or note_id != self.current["id"]:
                self.open_note(self.find(note_id))
            self.menu.tk_popup(event.x_root, event.y_root)

    def on_edit(self, _event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if self.current is None:
            return
        self.current["body"] = self.text.get("1.0", "end-1c")
        self.current["modified"] = now()
        self.update_status("Saving…")
        self.schedule_save()

    def new_note(self, _event=None):
        if self.current is not None and not self.current["body"].strip() and not self.current.get("title"):
            self.rename_note()
            return "break"
        note = {"id": uuid.uuid4().hex, "title": "", "body": "", "created": now(), "modified": now()}
        self.store.notes.append(note)
        self.search_var.set("")
        self.open_note(note)
        self.save_now()
        self.rename_note()
        return "break"

    def rename_note(self, _event=None):
        if self.current is None or self.rename_entry is not None:
            return "break"
        note = self.current
        if not self.tree.exists(note["id"]):
            self.search_var.set("")
        self.tree.see(note["id"])
        self.update_idletasks()
        bbox = self.tree.bbox(note["id"])
        if not bbox:
            return "break"
        x, y, _w, h = bbox

        entry = ttk.Entry(self.tree, font=self.list_font)
        entry.insert(0, note.get("title", ""))
        entry.select_range(0, tk.END)
        entry.place(x=x, y=y, width=self.tree.winfo_width() - x, height=h)
        entry.focus_set()
        self.rename_entry = entry

        def finish(keep):
            if self.rename_entry is not entry:
                return
            self.rename_entry = None
            if keep and entry.get().strip() != note.get("title", ""):
                note["title"] = entry.get().strip()
                note["modified"] = now()
            entry.destroy()
            self.save_now()
            self.text.focus_set()

        entry.bind("<Return>", lambda _e: finish(True))
        entry.bind("<KP_Enter>", lambda _e: finish(True))
        entry.bind("<Escape>", lambda _e: finish(False))
        entry.bind("<FocusOut>", lambda _e: finish(True))
        return "break"

    def delete_note(self, _event=None):
        if self.current is None:
            return "break"
        confirmed = messagebox.askyesno(
            "Delete note",
            f'Delete "{title_of(self.current)}"?\n\nThis cannot be undone.',
            icon=messagebox.WARNING, default=messagebox.NO, parent=self,
        )
        if confirmed:
            self.store.notes = [n for n in self.store.notes if n is not self.current]
            self.current = None
            self.refresh_list()
            visible = self.tree.get_children()
            if visible:
                self.open_note(self.find(visible[0]))
            else:
                self.show_empty()
            self.save_now()
        return "break"

    def focus_search(self, _event=None):
        self.search.focus_set()
        self.search.select_range(0, tk.END)
        return "break"

    def schedule_save(self):
        if self.save_job:
            self.after_cancel(self.save_job)
        self.save_job = self.after(SAVE_DELAY_MS, self.save_now)

    def save_now(self):
        if self.save_job:
            self.after_cancel(self.save_job)
            self.save_job = None
        self.store.window["last_id"] = self.current["id"] if self.current else None
        self.store.window["zoomed"] = self.state() == "zoomed"
        if self.state() == "normal":
            self.store.window["geometry"] = self.geometry()
        try:
            self.store.save()
        except OSError as e:
            self.update_status(f"SAVE FAILED: {e}")
            return False
        if self.rename_entry is None:
            self.refresh_list()
        self.update_status("All changes saved")
        return True

    def on_close(self):
        if self.rename_entry is not None:
            self.rename_entry.event_generate("<Return>")
        if self.save_now() or messagebox.askyesno(
            "Save failed", "Notes could not be saved. Close anyway and lose recent changes?",
            icon=messagebox.WARNING, default=messagebox.NO, parent=self,
        ):
            self.destroy()


def already_running():
    """Hold a named mutex for the app's lifetime; if another instance owns it, focus that window."""
    kernel32, user32 = ctypes.windll.kernel32, ctypes.windll.user32
    global _instance_mutex
    _instance_mutex = kernel32.CreateMutexW(None, False, APP_ID)
    if kernel32.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
        return False
    hwnd = user32.FindWindowW("TkTopLevel", APP_TITLE)
    if hwnd:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
    return True


def main():
    if sys.platform == "win32":
        if already_running():
            return
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    NotesApp(NotesStore(DATA_FILE)).mainloop()


if __name__ == "__main__":
    main()
