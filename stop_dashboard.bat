@echo off
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*EPR_Dashboard*server.py*' -or ($_.CommandLine -like '*server.py*' -and $_.Name -like 'python*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo EPR Dashboard server dihentikan.
timeout /t 2 >nul
