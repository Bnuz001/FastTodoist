import ctypes
import ctypes.wintypes
import os
import sys
import threading
import time
import tkinter as tk
import tkinter.messagebox
import tkinter.simpledialog
import requests
import keyring

# pythonw.exe runs with no console, so sys.stdout/stderr are None. Any library
# that tries to print/log during startup (pystray, PIL, keyboard) then crashes
# with AttributeError, silently killing that background thread.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

KEYRING_SERVICE = "FastTodoist"
KEYRING_USER = "todoist_token"
HOTKEY = "ctrl+shift+."

BG = "#1e1e1e"
FG = "#e8e8e8"
PLACEHOLDER_FG = "#555555"
ACCENT = "#db4035"  # Todoist red
FONT = ("Segoe UI", 13)
WIN_W = 500
WIN_H = 60


# ── Clipboard helpers (ctypes, work from any thread) ──────────────────────────

_CF_UNICODETEXT = 13
_u32 = ctypes.windll.user32
_k32 = ctypes.windll.kernel32

# Set argtypes + restype explicitly — ctypes defaults to c_int (32-bit), which
# truncates 64-bit pointers/handles on 64-bit Windows.
_HANDLE = ctypes.c_size_t  # pointer-sized integer, safe for HANDLE/HGLOBAL
_k32.GlobalAlloc.argtypes  = [ctypes.wintypes.UINT, ctypes.c_size_t]
_k32.GlobalAlloc.restype   = _HANDLE
_k32.GlobalLock.argtypes   = [_HANDLE]
_k32.GlobalLock.restype    = ctypes.c_void_p
_k32.GlobalUnlock.argtypes = [_HANDLE]
_k32.GlobalFree.argtypes   = [_HANDLE]
_u32.GetClipboardData.argtypes = [ctypes.wintypes.UINT]
_u32.GetClipboardData.restype  = _HANDLE
_u32.SetClipboardData.argtypes = [ctypes.wintypes.UINT, _HANDLE]


def _clipboard_get() -> str:
    if not _u32.OpenClipboard(None):
        return ""
    try:
        handle = _u32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = _k32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            _k32.GlobalUnlock(handle)
    except Exception:
        return ""
    finally:
        _u32.CloseClipboard()


def _clipboard_set(text: str) -> None:
    data = text.encode("utf-16-le") + b"\x00\x00"
    handle = _k32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    if not handle:
        return
    ptr = _k32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    _k32.GlobalUnlock(handle)
    if not _u32.OpenClipboard(None):
        _k32.GlobalFree(handle)
        return
    try:
        _u32.EmptyClipboard()
        _u32.SetClipboardData(_CF_UNICODETEXT, handle)
    finally:
        _u32.CloseClipboard()


# ── Token management ──────────────────────────────────────────────────────────

def _load_or_prompt_token(root):
    token = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    if token:
        return token
    return _prompt_for_token(root, first_run=True)


def _prompt_for_token(root, first_run=False):
    msg = (
        "Enter your Todoist API token:\n"
        "(todoist.com → Settings → Integrations → API token)"
    )
    token = tkinter.simpledialog.askstring(
        "FastTodoist — Setup" if first_run else "FastTodoist — Change token",
        msg,
        parent=root,
    )
    if not token or not token.strip():
        if first_run:
            tkinter.messagebox.showwarning("FastTodoist", "No token provided. Exiting.")
            sys.exit(0)
        return None
    token = token.strip()
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
    return token


# ── App ───────────────────────────────────────────────────────────────────────

class FastTodoist:
    def __init__(self, token: str):
        self.token = token
        self._visible = False
        self.root = tk.Tk()
        self.root.withdraw()
        self._build_popup()
        self._register_hotkey()
        self._start_tray()

    # ── Popup ─────────────────────────────────────────────────────────────────

    def _build_popup(self):
        p = tk.Toplevel(self.root)
        p.withdraw()
        p.overrideredirect(True)
        p.attributes("-topmost", True)
        p.configure(bg=ACCENT)

        frame = tk.Frame(p, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.entry = tk.Entry(
            frame,
            bg=BG,
            fg=PLACEHOLDER_FG,
            insertbackground=FG,
            font=FONT,
            relief=tk.FLAT,
            bd=0,
        )
        self.entry.pack(padx=14, ipady=11, fill=tk.BOTH, expand=True)
        self.entry.insert(0, "Add to inbox…")

        self.entry.bind("<FocusIn>", self._clear_placeholder)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Return>", self._submit)
        self.entry.bind("<Escape>", lambda _: self._hide())

        sw = p.winfo_screenwidth()
        sh = p.winfo_screenheight()
        p.geometry(f"{WIN_W}x{WIN_H}+{(sw - WIN_W) // 2}+{(sh - WIN_H) // 2}")

        self.popup = p

    def _clear_placeholder(self, _=None):
        if self.entry.cget("fg") == PLACEHOLDER_FG:
            self.entry.delete(0, tk.END)
            self.entry.config(fg=FG)

    def _set_placeholder(self):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, "Add to inbox…")
        self.entry.config(fg=PLACEHOLDER_FG)

    def _on_focus_out(self, _=None):
        self.root.after(100, self._maybe_hide)

    def _maybe_hide(self):
        if self.root.focus_displayof() not in (self.entry,):
            self._hide()

    def _show(self, prefill: str = ""):
        if self._visible:
            self._hide()
            return
        self._visible = True

        if prefill:
            self.entry.config(fg=FG)
            self.entry.delete(0, tk.END)
            self.entry.insert(0, prefill)
            self.entry.select_range(0, tk.END)
        else:
            self._set_placeholder()

        self.popup.deiconify()
        self.popup.lift()
        self.popup.focus_force()
        self.entry.focus_set()

    def _hide(self):
        self._visible = False
        self.popup.withdraw()
        self._set_placeholder()

    # ── Todoist ───────────────────────────────────────────────────────────────

    def _submit(self, _=None):
        is_placeholder = self.entry.cget("fg") == PLACEHOLDER_FG
        text = self.entry.get().strip()
        self._hide()
        if text and not is_placeholder:
            threading.Thread(target=self._post_task, args=(text,), daemon=True).start()

    def _post_task(self, content):
        try:
            r = requests.post(
                "https://api.todoist.com/api/v1/tasks",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"content": content},
                timeout=10,
            )
            r.raise_for_status()
        except Exception as e:
            print(f"[FastTodoist] Error adding task: {e}", file=sys.stderr)

    # ── Hotkey & tray ─────────────────────────────────────────────────────────

    def _register_hotkey(self):
        import keyboard
        keyboard.add_hotkey(HOTKEY, self._on_hotkey, suppress=True)

    def _on_hotkey(self):
        # Toggle off immediately if already visible
        if self._visible:
            self.root.after(0, self._hide)
            return
        # Grab selected text from whatever app is in focus, then show
        threading.Thread(target=self._grab_selection_and_show, daemon=True).start()

    def _grab_selection_and_show(self):
        import keyboard as kb

        old = _clipboard_get()
        old_stripped = old.strip()

        # Remove our hotkey before injecting Ctrl+C — the suppress=True hook
        # intercepts injected events too, which prevents them reaching Chrome
        # and other multi-process (Electron/Chromium) apps.
        try:
            kb.remove_hotkey(HOTKEY)
        except Exception:
            pass

        kb.send("ctrl+c")
        time.sleep(0.30)  # Chromium IPC roundtrip needs ~200-300 ms

        # Re-register immediately after reading clipboard
        kb.add_hotkey(HOTKEY, self._on_hotkey, suppress=True)

        new_stripped = _clipboard_get().strip()
        prefill = ""
        if new_stripped and new_stripped != old_stripped:
            prefill = new_stripped
            _clipboard_set(old)

        self.root.after(0, lambda: self._show(prefill=prefill))

    def _start_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw

            size = 64
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse([2, 2, size - 2, size - 2], fill=ACCENT)
            tx, ty = 22, 16
            d.rectangle([tx, ty, tx + 20, ty + 5], fill="white")
            d.rectangle([tx + 7, ty, tx + 13, ty + 30], fill="white")

            icon = pystray.Icon(
                "FastTodoist",
                img,
                f"FastTodoist  ({HOTKEY})",
                pystray.Menu(
                    pystray.MenuItem("Change API token", self._on_change_token),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Quit", self._quit),
                ),
            )
            self.tray_icon = icon
            threading.Thread(target=icon.run, daemon=True).start()
        except ImportError:
            pass

    def _on_change_token(self, *_):
        self.root.after(0, self._change_token_on_main_thread)

    def _change_token_on_main_thread(self):
        new_token = _prompt_for_token(self.root, first_run=False)
        if new_token:
            self.token = new_token

    def _quit(self, *_):
        if hasattr(self, "tray_icon"):
            self.tray_icon.stop()
        import keyboard
        keyboard.unhook_all()
        self.root.after(0, self.root.destroy)

    def run(self):
        self.root.mainloop()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Single-instance guard: exit silently if already running
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "FastTodoist_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

    root = tk.Tk()
    root.withdraw()
    token = _load_or_prompt_token(root)
    root.destroy()

    FastTodoist(token).run()


if __name__ == "__main__":
    main()
