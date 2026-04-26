Set WshShell = CreateObject("WScript.Shell")
Set fso      = CreateObject("Scripting.FileSystemObject")

Dim strDesktop
strDesktop = WshShell.SpecialFolders("Desktop")

' Launcher-VBS direkt auf dem Desktop anlegen
Dim launcherPath
launcherPath = strDesktop & "\LOYAGO Sales Dashboard starten.vbs"

Dim ts
Set ts = fso.CreateTextFile(launcherPath, True)
ts.WriteLine "Set WshShell = CreateObject(""WScript.Shell"")"
ts.WriteLine "WshShell.Run ""wsl bash -c """"pkill -f streamlit; sleep 1; /home/adelt/.local/bin/streamlit run /home/adelt/SalesDashboard/app.py --server.port 8501"""""", 0, False"
ts.WriteLine "WScript.Sleep 6000"
ts.WriteLine "WshShell.Run ""http://localhost:8501"""
ts.Close

' Desktop-Verknüpfung mit Icon erstellen
Set oLink = WshShell.CreateShortcut(strDesktop & "\LOYAGO Sales Dashboard.lnk")
oLink.TargetPath   = "wscript.exe"
oLink.Arguments    = Chr(34) & launcherPath & Chr(34)
oLink.IconLocation = "%SystemRoot%\System32\imageres.dll, 174"
oLink.WindowStyle  = 7
oLink.Description  = "LOYAGO Sales Dashboard starten"
oLink.Save

MsgBox "Desktop-Icon wurde erstellt!" & Chr(10) & Chr(10) & "Du findest 'LOYAGO Sales Dashboard' jetzt auf deinem Desktop.", 64, "LOYAGO"
