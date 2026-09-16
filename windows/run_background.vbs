' VBScript untuk menjalankan Hardware Bridge di background tanpa jendela console hitam
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
BaseDir = FSO.GetParentFolderName(ScriptDir)

' Jalankan python app.py di background (0 = hide window)
WshShell.CurrentDirectory = BaseDir
WshShell.Run "cmd /c python app.py", 0, False
WScript.Sleep 1500
WshShell.Run "cmd /c python tray_indicator.py", 0, False
