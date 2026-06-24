"""
Run once after cloning: python install.py
Creates run.lnk — a Windows shortcut that launches FastTodoist silently.
"""
import pathlib
import subprocess
import sys


def main():
    here = pathlib.Path(__file__).parent.resolve()
    pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")

    if not pythonw.exists():
        print(f"Error: pythonw.exe not found at {pythonw}")
        sys.exit(1)

    lnk = here / "run.lnk"
    ps = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{lnk}')
$s.TargetPath = '{pythonw}'
$s.Arguments = '"{here / "main.py"}"'
$s.WorkingDirectory = '{here}'
$s.WindowStyle = 7
$s.Save()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    print(f"Created {lnk}")
    print("Double-click run.lnk to launch FastTodoist.")


if __name__ == "__main__":
    main()
