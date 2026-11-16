@echo off
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$pyw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source; " ^
  "if (-not $pyw) { $pyw = 'pythonw.exe' }; " ^
  "$startup = [Environment]::GetFolderPath('Startup'); " ^
  "$s1 = $ws.CreateShortcut((Join-Path $startup 'EPR Dashboard Server.lnk')); " ^
  "$s1.TargetPath = $pyw; " ^
  "$s1.Arguments = '\"' + '%APP_DIR%\server.py' + '\" --no-browser'; " ^
  "$s1.WorkingDirectory = '%APP_DIR%'; " ^
  "$s1.Description = 'Jalankan EPR Dashboard Server otomatis saat Windows login'; " ^
  "$s1.Save(); " ^
  "$desk = [Environment]::GetFolderPath('Desktop'); " ^
  "$s2 = $ws.CreateShortcut((Join-Path $desk 'EPR Dashboard.lnk')); " ^
  "$s2.TargetPath = '%APP_DIR%\start_dashboard.bat'; " ^
  "$s2.WorkingDirectory = '%APP_DIR%'; " ^
  "$s2.WindowStyle = 7; " ^
  "$s2.Description = 'Buka EPR Achievement Dashboard'; " ^
  "$s2.Save()"
echo Auto-start Windows dan Shortcut Desktop berhasil dipasang!
pause
