# FastTodoist

A minimal Windows tray app for capturing tasks to your Todoist inbox — without opening Todoist.

Press a hotkey, type, hit Enter. Done.

## Features

- **Global hotkey** — `Ctrl+Shift+.` opens a slim centered input box from anywhere
- **Selection capture** — if you have text selected, it pre-fills the input
- **Zero friction** — type your task, press Enter, it's in your inbox
- **Secure token storage** — API token saved to Windows Credential Manager, never on disk in plaintext
- **System tray** — runs silently in the background; quit or change token from the tray icon
- **Single instance** — launching a second time does nothing
- **Toggle** — press the hotkey again (or Escape, or click away) to dismiss

## Requirements

- Windows 10/11
- Python 3.9+

## Setup

**1. Clone the repo**

```
git clone https://github.com/Bnuz001/FastTodoist.git
cd FastTodoist
```

**2. Install dependencies**

```
pip install -r requirements.txt
```

**3. Create the launcher shortcut**

```
python install.py
```

This generates a `run.lnk` shortcut on your machine. Double-click it to launch FastTodoist silently with no console window. You only need to run `install.py` once.

**4. Get your Todoist API token**

Go to [todoist.com](https://todoist.com) → Settings → Integrations → Developer → copy your API token.

On first launch a dialog will ask for it. It's saved to Windows Credential Manager and never asked again.

## Usage

| Action | Result |
|---|---|
| `Ctrl+Shift+.` | Open input box (pre-fills with selected text if any) |
| `Ctrl+Shift+.` again | Dismiss |
| Type + `Enter` | Add task to Todoist inbox |
| `Escape` | Dismiss |
| Click elsewhere | Dismiss |
| Tray → Change API token | Update stored token |
| Tray → Quit | Exit |

## Run on startup

Press `Win+R`, type `shell:startup`, and place a shortcut to `run.lnk` in that folder.

## Dependencies

| Package | Purpose |
|---|---|
| `keyboard` | Global hotkey hooks |
| `requests` | Todoist API calls |
| `keyring` | Windows Credential Manager |
| `pystray` | System tray icon |
| `Pillow` | Tray icon rendering |
