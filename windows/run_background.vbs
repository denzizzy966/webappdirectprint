' VBScript untuk menjalankan Hardware Bridge di background tanpa jendela console hitam
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
BaseDir = FSO.GetParentFolderName(ScriptDir)

' Jalankan HardwareBridge.exe jika ada, atau fallback ke python app.py
WshShell.CurrentDirectory = BaseDir
If FSO.FileExists(BaseDir & "\HardwareBridge.exe") Then
    WshShell.Run """" & BaseDir & "\HardwareBridge.exe""", 0, False
Else
    WshShell.Run "cmd /c python app.py", 0, False
    WScript.Sleep 1500
    WshShell.Run "cmd /c python tray_indicator.py", 0, False
End If
