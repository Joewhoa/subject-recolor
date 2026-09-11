@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/4] 检查 Python...
py -3 --version >nul 2>&1
if errorlevel 1 (
  echo 未找到Python。请让Agent协助安装Python 3.10-3.13，并勾选Add Python to PATH。
  pause
  exit /b 1
)
echo [2/4] 检查 curl...
where curl >nul 2>&1
if errorlevel 1 (
  echo 未找到curl。Windows 10/11通常自带，请把此窗口截图发给Agent。
  pause
  exit /b 1
)
echo [3/4] 创建独立环境 .venv 并安装依赖...
py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo [4/4] 运行离线环境自检...
python check_environment.py
if errorlevel 1 goto :fail
echo 安装完成。以后请让Agent代为运行，不要把API Key写进文件。
pause
exit /b 0
:fail
echo 安装或自检失败。请复制完整窗口内容给Agent，不要反复尝试付费任务。
pause
exit /b 1
