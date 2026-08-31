#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "[1/4] 检查 Python 3..."
command -v python3 >/dev/null || { echo "未找到python3，请让Agent协助安装Python 3.10-3.13。"; exit 1; }
echo "[2/4] 检查 curl..."
command -v curl >/dev/null || { echo "未找到curl，请让Agent协助。"; exit 1; }
echo "[3/4] 创建独立Python环境 .venv..."
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
echo "[4/4] 运行离线环境自检..."
./.venv/bin/python check_environment.py
echo "安装完成。以后请让Agent代为运行，不要把API Key写进文件。"
read -r -p "按回车关闭窗口..." _
