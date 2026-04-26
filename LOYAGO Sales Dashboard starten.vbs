Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "wsl bash -c ""/home/adelt/.local/bin/streamlit run /home/adelt/SalesDashboard/app.py""", 0, False
WScript.Sleep 5000
WshShell.Run "http://localhost:8501"
