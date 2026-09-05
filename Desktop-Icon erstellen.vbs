Set WshShell = CreateObject("WScript.Shell")
Set fso      = CreateObject("Scripting.FileSystemObject")

Dim loyagoDir
loyagoDir = WshShell.ExpandEnvironmentStrings("%APPDATA%") & "\LOYAGO"
If Not fso.FolderExists(loyagoDir) Then fso.CreateFolder(loyagoDir)

Dim launcherPath
launcherPath = loyagoDir & "\dashboard-starten.vbs"

Dim ts
Set ts = fso.CreateTextFile(launcherPath, True)
ts.WriteLine "Set W = CreateObject(""WScript.Shell"")"
ts.WriteLine "Dim Q : Q = Chr(34)"
ts.WriteLine ""
ts.WriteLine "Dim cmd1 : cmd1 = ""wsl bash -c "" & Q & ""pkill -f streamlit"" & Q"
ts.WriteLine "Dim cmd2 : cmd2 = ""wsl bash -c "" & Q & ""/home/adelt/.local/bin/streamlit run /home/adelt/SalesDashboard/app.py --server.port 8501"" & Q"
ts.WriteLine ""
ts.WriteLine "W.Run cmd1, 0, True"
ts.WriteLine "WScript.Sleep 1500"
ts.WriteLine "W.Run cmd2, 0, False"
ts.WriteLine ""
ts.WriteLine "Dim i, rc"
ts.WriteLine "For i = 1 To 20"
ts.WriteLine "    WScript.Sleep 2000"
ts.WriteLine "    rc = W.Run(""powershell -WindowStyle Hidden -Command "" & Q & ""try{$null=New-Object Net.Sockets.TcpClient('localhost',8501);exit 0}catch{exit 1}"" & Q, 0, True)"
ts.WriteLine "    If rc = 0 Then Exit For"
ts.WriteLine "Next"
ts.WriteLine ""
ts.WriteLine "W.Run ""http://localhost:8501"""
ts.Close

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
