@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo 尚未安装，请先双击install_windows.bat或让Agent处理。
  pause
  exit /b 1
)
.venv\Scripts\python.exe main.py
echo 程序结束，退出码：%errorlevel%。看不懂时请截图并把生成图\记录交给Agent。
pause
