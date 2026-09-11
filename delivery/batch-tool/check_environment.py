"""完全离线的环境自检：不会读取Key、不会调用API、不会产生费用。"""
from __future__ import annotations
import json, platform, shutil, subprocess, sys
from pathlib import Path

def version(command):
    try:
        p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=10,check=False)
        return p.returncode,(p.stdout or '').strip().splitlines()[0][:200]
    except Exception as exc: return 1,f"{type(exc).__name__}: {exc}"

def main():
    here=Path(__file__).resolve().parent
    checks=[]
    py_ok=sys.version_info >= (3,10)
    checks.append(("Python >= 3.10",py_ok,platform.python_version()))
    curl=shutil.which("curl")
    code,detail=version([curl,"--version"]) if curl else (1,"未找到")
    checks.append(("系统curl",bool(curl) and code==0,detail))
    try:
        from PIL import Image
        checks.append(("Pillow",True,Image.__version__))
    except Exception as exc: checks.append(("Pillow",False,str(exc)))
    required=["main.py","config.example.json","recolor/core/processor.py","recolor/api/image_edit_client.py"]
    missing=[p for p in required if not (here/p).is_file()]
    checks.append(("工具文件完整",not missing,"正常" if not missing else "缺少: "+", ".join(missing)))
    print("\n========== 环境自检（不会调用API） ==========")
    for name,ok,detail in checks: print(("[通过]" if ok else "[失败]"),name,"-",detail)
    print("===========================================\n")
    if not all(x[1] for x in checks):
        print("环境尚未准备好。请把完整输出发给Agent，不要自行反复尝试。")
        return 1
    print("环境准备完成。下一步让Agent执行 --dry-run，仍不会产生费用。")
    return 0
if __name__=="__main__": raise SystemExit(main())
