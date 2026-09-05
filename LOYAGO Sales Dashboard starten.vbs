Set W = CreateObject("WScript.Shell")
Dim Q : Q = Chr(34)

Dim cmd1 : cmd1 = "wsl bash -c " & Q & "pkill -f streamlit" & Q
Dim cmd2 : cmd2 = "wsl bash -c " & Q & "/home/adelt/.local/bin/streamlit run /home/adelt/SalesDashboard/app.py --server.port 8501" & Q

W.Run cmd1, 0, True
WScript.Sleep 1500
W.Run cmd2, 0, False

' Warten bis Port 8501 wirklich antwortet (max 40 Sek)
Dim i, rc
For i = 1 To 20
    WScript.Sleep 2000
    rc = W.Run("powershell -WindowStyle Hidden -Command " & Q & "try{$null=New-Object Net.Sockets.TcpClient('localhost',8501);exit 0}catch{exit 1}" & Q, 0, True)
    If rc = 0 Then Exit For
Next

W.Run "http://localhost:8501"
