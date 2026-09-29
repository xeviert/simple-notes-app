# Simple Notes

Lightweight notes app. Single file, Python standard library only (tkinter).

## Install

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

Builds `SimpleNotes.exe` with PyInstaller (in a local `.venv`), installs it to `%LOCALAPPDATA%\Programs\SimpleNotes`, and adds Desktop and Start Menu shortcuts. Re-run after changing `notes.pyw` to update the installed app.

Uninstall with `uninstall.ps1` (notes are kept).

## Run from source

```
pythonw notes.pyw
```

## Features

- Notes autosave half a second after you stop typing, and on close; status bar shows "All changes saved"
- Notes list on the left, newest edits first; give notes a title, or they use their first line
- Search matches every word you type, in any order, across titles and note text (case-insensitive)
- Delete asks for confirmation
- Ctrl+Shift+V toggles a note between editing and a rendered Markdown preview (headings, lists, tasks, tables, code, quotes, links); each note remembers its view
- Remembers window size and last open note
- Single instance: launching again focuses the open window

## Shortcuts

| Key | Action |
| --- | --- |
| Ctrl+N | New note (starts with renaming it) |
| F2 / double-click | Rename selected note; Enter saves, Esc cancels |
| Right-click note | Rename / Delete menu |
| Ctrl+F | Search (Esc clears, Enter jumps to editor) |
| Ctrl+Backspace / Ctrl+Delete | Delete previous / next word |
| Ctrl+Shift+V | Toggle Markdown preview for current note |
| Ctrl+Shift+Delete | Delete current note |
| Delete | Delete selected note (when list is focused) |
| Ctrl+Z / Ctrl+Y | Undo / redo |

## Data

Stored in `%APPDATA%\SimpleNotes\notes.json`. Writes are atomic, so a crash can't corrupt the file. If the file ever becomes unreadable, it's moved aside as `notes.corrupt-<timestamp>.json` rather than overwritten.
