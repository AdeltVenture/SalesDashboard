Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "wsl bash -c ""pkill -f streamlit; sleep 1; /home/adelt/.local/bin/streamlit run /home/adelt/SalesDashboard/app.py --server.port 8501""", 0, False
WScript.Sleep 6000
WshShell.Run "http://localhost:8501"
