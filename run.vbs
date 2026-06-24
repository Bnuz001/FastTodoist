Dim dir
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run "pythonw """ & dir & "\main.py""", 0, False
