Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "wsl bash -c ""cd /home/user/SalesDashboard && streamlit run app.py""", 0, False
WScript.Sleep 4000
WshShell.Run "http://localhost:8501"
