Set WshShell = CreateObject("WScript.Shell")
Set fso      = CreateObject("Scripting.FileSystemObject")

' Stabilen Ordner in AppData anlegen
Dim loyagoDir
loyagoDir = WshShell.ExpandEnvironmentStrings("%APPDATA%") & "\LOYAGO"
If Not fso.FolderExists(loyagoDir) Then fso.CreateFolder(loyagoDir)

' Launcher-VBS dauerhaft in AppData speichern
Dim launcherPath
launcherPath = loyagoDir & "\dashboard-starten.vbs"

Dim ts
Set ts = fso.CreateTextFile(launcherPath, True)
ts.WriteLine "Set WshShell = CreateObject(""WScript.Shell"")"
ts.WriteLine "WshShell.Run ""wsl bash -c """"pkill -f streamlit; sleep 1; /home/adelt/.local/bin/streamlit run /home/adelt/SalesDashboard/app.py --server.port 8501"""""", 0, False"
ts.WriteLine "WScript.Sleep 6000"
ts.WriteLine "WshShell.Run ""http://localhost:8501"""
ts.Close

' Desktop-Verknüpfung mit Icon anlegen
Dim strDesktop
strDesktop = WshShell.SpecialFolders("Desktop")
Set oLink = WshShell.CreateShortcut(strDesktop & "\LOYAGO Sales Dashboard.lnk")
oLink.TargetPath   = "wscript.exe"
oLink.Arguments    = Chr(34) & launcherPath & Chr(34)
oLink.IconLocation = "%SystemRoot%\System32\imageres.dll, 174"
oLink.WindowStyle  = 7
oLink.Description  = "LOYAGO Sales Dashboard starten"
oLink.Save

MsgBox "Fertig! Das Icon liegt jetzt auf deinem Desktop.", 64, "LOYAGO"
