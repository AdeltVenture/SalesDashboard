@echo off
wsl bash -c "cd /home/user/SalesDashboard && streamlit run app.py" &
timeout /t 4 /nobreak >nul
start http://localhost:8501
