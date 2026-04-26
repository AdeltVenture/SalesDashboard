Set WshShell = CreateObject("WScript.Shell")

Dim scriptDir
scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

Dim strDesktop
strDesktop = WshShell.SpecialFolders("Desktop")

Set oLink = WshShell.CreateShortcut(strDesktop & "\LOYAGO Sales Dashboard.lnk")
oLink.TargetPath   = "wscript.exe"
oLink.Arguments    = Chr(34) & scriptDir & "LOYAGO Sales Dashboard starten.vbs" & Chr(34)
oLink.IconLocation = "%SystemRoot%\System32\imageres.dll, 174"
oLink.WindowStyle  = 7
oLink.Description  = "LOYAGO Sales Dashboard starten"
oLink.Save

MsgBox "Desktop-Icon wurde erstellt!" & Chr(10) & Chr(10) & "Du findest es jetzt auf deinem Desktop.", 64, "LOYAGO"
