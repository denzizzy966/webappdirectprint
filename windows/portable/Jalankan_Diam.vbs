' ============================================================================
' Menjalankan Hardware Bridge tanpa jendela CMD hitam (silent background).
' Dipakai otomatis oleh INSTALL.bat bila paket dijalankan dari kode sumber
' Python. Untuk paket portable, HardwareBridge.exe sudah senyap dengan
' sendirinya sehingga berkas ini tidak diperlukan.
' ============================================================================

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

BaseDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = BaseDir

If FSO.FileExists(BaseDir & "\HardwareBridge.exe") Then
    WshShell.Run """" & BaseDir & "\HardwareBridge.exe""", 0, False
ElseIf FSO.FileExists(BaseDir & "\app.py") Then
    WshShell.Run "cmd /c python """ & BaseDir & "\app.py""", 0, False
Else
    MsgBox "HardwareBridge.exe maupun app.py tidak ditemukan di:" & vbCrLf & _
           BaseDir & vbCrLf & vbCrLf & _
           "Pastikan berkas ZIP sudah diekstrak terlebih dahulu.", _
           vbExclamation, "WebApp Hardware Bridge"
End If
