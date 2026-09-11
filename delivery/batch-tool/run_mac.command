#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then echo "尚未安装，请先双击install_mac.command或让Agent处理。"; read -r; exit 1; fi
.venv/bin/python main.py
code=$?
echo "程序结束，退出码：$code。看不懂时请把本窗口和生成图/记录交给Agent。"
read -r -p "按回车关闭窗口..." _
exit $code
