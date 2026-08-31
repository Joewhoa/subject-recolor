# 主体换色批量工具｜正式稳定版（默认示例主体：户外窗帘）

> 用户完全不懂Python时，请让Agent阅读交接根目录文档并代操作。API Key不得进入Git、持久配置、应用日志、curl argv、终端/聊天或输出产物；工具从环境变量读取Key，仅在每次调用期间写入权限受限的短期临时curl header文件，并在调用后尽力删除。权限限制或清理失败属于需要Agent检查的本机安全卫生问题，不承诺不可能留下任何本地残留。

## 方案摘要

- Python管理：扫描、色卡取色、压缩缓存、任务计划、checkpoint、有限重试、PNG/JPG、CSV和审阅页；
- **系统curl发送API请求**：某次部署观察到httpx与curl的兼容性差异，system curl作为该部署的验证适配器（不是“httpx必然失败”）；
- 当前稳定版**固定单线程**；
- 默认B增强方案；A是显式可选的个别复检方案，绝不默认A+B双跑；
- 每次只上传一张原图＋prompt；色卡不上传；无mask；不传quality和size。

## 任务目录

```text
日期目录/
├── 待处理/
├── 色卡/
└── 生成图/       # 自动创建
    ├── B增强方案/png、jpg、审阅页.html
    ├── A参考方案/png、jpg、审阅页.html
    ├── 缓存/压缩输入
    └── 记录
```

原图×色卡形成全部组合。色卡读取中心200×200 RGB平均值。原图不修改；上传副本默认最长边2048、最大4MB。模型PNG原字节保存，JPG由PNG转换，quality 85、progressive、RGB，不放大。

## 安装

### macOS

双击`install_mac.command`，或：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python check_environment.py
PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_offline tests.test_curl_local_integration
```

### Windows

双击`install_windows.bat`，或在PowerShell执行：

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe check_environment.py
$env:PYTHONPATH="."
.venv\Scripts\python.exe -m unittest -v tests.test_offline tests.test_curl_local_integration
```

依赖：Python建议3.10–3.13、Pillow、系统curl。API Key通过环境变量`SUB2API_API_KEY`提供给工具；工具仅为当前调用创建权限受限的短期临时curl header文件，并在调用后尽力删除。

## 必须遵循的运行顺序

```bash
# 1. 离线扫描，不收费
python main.py "/path/to/日期目录" --profile B --workers 1 --dry-run

# 2. 准备压缩，不收费
python main.py "/path/to/日期目录" --profile B --workers 1 --prepare-only

# 3. 只探测计划第一个任务，可能付费
python main.py "/path/to/日期目录" --profile B --workers 1 --limit 1

# 4. 用户审阅首张后，断点全量/续跑
python main.py "/path/to/日期目录" --profile B --workers 1
```

不传目录时程序会提示粘贴或选择文件夹。正式调用默认要求精确输入`YES`。

## 状态和费用安全

- PNG+JPG有效：跳过；PNG有效但JPG缺失：本地补JPG；
- 每次提交前保存fresh request ID；它用于追踪，不是幂等键；
- 只有HTTP 429或确认连接未建立（curl exit 5/6/7且HTTP 0）可安全补试；`max_safe_retries`硬限制为`0`或`1`，默认`1`，即最多额外补试一次并默认等待30秒；
- curl进程无法启动属于本地`fatal/rejected`，请求未提交，不自动重试；
- HTTP 503：默认按uncertain处理，不自动重试，记录request ID并对账后决定；
- 超时、上传后传输异常、异常5xx、2xx缺图：`uncertain`并立即停止，禁止自动重提；
- 400/401/403/404/413/422：`rejected`并停止；
- 只有usage对账确认未扣费且用户明确授权，才允许`--retry-uncertain`。

## 配置

复制`config.example.json`为`config.json`再修改。不得放Key。稳定版要求`context_workers=1`。`max_safe_retries`只能配置为`0`或`1`，任何更大值都会被拒绝；它只适用于HTTP 429或确认连接未建立。其他常用项包括上传尺寸/字节、超时、补试间隔、JPG质量。

API端点通过`base_url`、`SUB2API_BASE_URL`或`--base-url`在运行时注入，代码和文档不内置私有网关；公开示例统一为`https://your-image-gateway.example/v1/images/edits`。不要把真实网关IP/端口写入文档或Git。成功响应可能报告模型`gpt-image-2-codex`。

## A方案

B全量审阅后，只对问题组合做A。当前没有精确任务筛选，建议建立隔离的“A复检”任务目录，放必要原图和色卡，先dry-run核对笛卡尔积。A/B输出目录隔离，不覆盖。

更多说明见交接根目录：`文档/01_完全小白用户手册.md`和`文档/02_新Agent完整操作手册.md`。
