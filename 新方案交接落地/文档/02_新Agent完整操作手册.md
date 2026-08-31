# 新Agent完整操作手册

## 0. 角色定位

用户完全不懂Python。你不是只提供命令的顾问，而是**代操作员＋解释员＋费用安全守门人**。应主动检查环境、目录和状态；每个付费步骤前用中文说明调用上限；执行后解释结果和下一步。不要要求用户理解终端。

## 1. 不可违反的生产规则

1. 唯一主入口：`正式工具_batch_recolor_tool/main.py`。
2. Python负责任务管理；system curl作为该部署的验证适配器负责multipart传输。不要恢复httpx作为默认，也不要把httpx与curl的差异描述成“httpx必然失败”。
3. 当前稳定版固定单线程`context_workers=1`；README不得宣称已实现并发。
4. 默认`profile=B`；A只能由用户明确指定到个别复检任务，绝不A+B双跑；A/B输出必须隔离。
5. 每个请求只上传一张原图和prompt；不上传色卡、不传mask、quality、size。
6. 色卡取正中心200×200 RGB均值；写入描述、HEX、RGB。
7. PNG是Base64直接解码母版；JPG只由PNG转换，quality 85、progressive、RGB，保持模型输出尺寸。
8. 不修改原图；上传压缩默认最长边2048、上限4MB、JPEG quality 90。
9. 任何批次先dry-run、prepare-only、limit 1；首张审阅后再全量。
10. uncertain禁止自动重提。只有用户明确要求且已按request ID/usage确认未扣费，才用`--retry-uncertain`。
11. Key不得进入Git、持久配置、应用日志、curl argv、终端/聊天或输出产物。工具从进程环境读取，仅在每次调用期间写入权限受限的短期临时curl header文件，并在调用后尽力删除；权限限制或清理失败属于本机安全卫生问题，必须停止并由Agent检查，不得宣称绝对不可能留下本地残留。不得在代码、配置或文档中内置私有网关；运行时使用`base_url`、`SUB2API_BASE_URL`或`--base-url`注入，公开示例统一使用`https://your-image-gateway.example`。若实际端点使用明文HTTP，应向用户说明传输风险。
12. 不修改正式工具，除非用户明确要求。修改后必须离线测试并更新文档/校验清单。

## 2. 第一次接手清单

1. 阅读交接根目录`00_README_先看这里.md`；
2. 确认工作目录，不要从工具安装路径推断项目路径；
3. 检查目标日期目录是否有`待处理/`、`色卡/`；
4. 检查交接包是否完整；
5. 在工具目录创建`.venv`并安装依赖，或复用已验证环境；
6. 确认系统curl存在；
7. 运行`check_environment.py`；
8. 运行离线单元测试；
9. dry-run并把原图数×色卡数、色值、预计调用数告诉用户；
10. prepare-only并报告压缩前后尺寸；
11. 明确用户授权后limit 1；
12. 验证PNG/JPG/checkpoint/审阅页；
13. 用户审阅通过后才全量。

## 3. 环境安装

### macOS

优先让Agent执行：

```bash
cd ".../新方案交接落地/正式工具_batch_recolor_tool"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python check_environment.py
PYTHONPATH=. .venv/bin/python -m unittest -v tests.test_offline
```

用户也可双击`install_mac.command`，但Agent应代为解释任何错误。

### Windows PowerShell/CMD

可双击`install_windows.bat`，或：

```powershell
cd "...\新方案交接落地\正式工具_batch_recolor_tool"
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe check_environment.py
$env:PYTHONPATH="."
.venv\Scripts\python.exe -m unittest -v tests.test_offline
```

Python建议3.10–3.13。依赖只有Pillow；curl由系统提供。不要在交接包中包含`.venv`。

## 4. 标准命令（macOS示例）

变量：

```bash
TOOL="/绝对路径/新方案交接落地/正式工具_batch_recolor_tool"
TASK="/绝对路径/0915"
PY="$TOOL/.venv/bin/python"
```

### 完全离线环境自检

```bash
cd "$TOOL" && "$PY" check_environment.py
```

### 离线测试

```bash
cd "$TOOL" && PYTHONPATH=. "$PY" -m unittest -v tests.test_offline
```

### 扫描计划，不收费

```bash
cd "$TOOL" && "$PY" main.py "$TASK" --profile B --workers 1 --dry-run
```

### 准备压缩缓存，不收费

```bash
cd "$TOOL" && "$PY" main.py "$TASK" --profile B --workers 1 --prepare-only
```

### 单任务探测，可能付费

先把Key安全注入当前进程环境，绝不回显：

```bash
SUB2API_API_KEY="$KEY" "$PY" main.py "$TASK" --profile B --workers 1 --limit 1
```

默认会要求精确输入`YES`。除非自动化运行且已获得明确授权，否则不要加`--yes`。

### 正式续跑/全量

```bash
SUB2API_API_KEY="$KEY" "$PY" main.py "$TASK" --profile B --workers 1
```

有效PNG+JPG会自动跳过。

## 5. Key处理

优先使用用户已有的安全本机凭据源或由用户在终端临时设置。除工具为单次调用创建的权限受限短期临时curl header文件外，不得：

- 写入`config.json`、源码、Markdown、其他持久文件或输出产物；
- 写Shell脚本或直接放进curl命令参数（argv）；
- 回显到屏幕、聊天或写入应用日志；
- 放进命令历史（使用进程环境或授权的安全凭据源读取）；
- 复制进交接包或Git。

工具读取：`SUB2API_API_KEY`，兼容`SUB2API_KEY`。它在每次调用期间把Key放入权限受限的临时header文件，调用后尽力删除。若权限设置或清理失败，停止后续调用并检查临时目录、文件权限和残留；这是本机安全卫生问题，不得声称工具能绝对保证不留下任何本地残留。

## 6. 计划和ID

- `context_id`：原图名＋原图SHA-256的本地隔离标识，不是模型会话；
- `task_id`：原图哈希/文件名＋色卡哈希/文件名＋主体＋profile＋prompt版本；
- 任务是原图×色卡笛卡尔积；
- `--limit N`选计划列表前N项，不保证恰好执行N个新增调用；
- 改主体/profile/prompt版本会生成不同task ID。

## 7. 状态机

- `pending`：尚未调用；
- `submitted`：已记录request ID并开始提交；
- `retry_wait`：明确429或未建立连接（HTTP 0），等待有限补试；503不进入此状态；
- `succeeded`：PNG/JPG有效；
- `failed_safe`：明确安全失败且补试用完；
- `uncertain`：可能已经进入上游/计费，禁止自动重提；
- `rejected`：400/401/403/404/413/422等，应修复配置/权限。

每次状态变化会写checkpoint和JSONL。事件日志fsync；checkpoint/输出原子替换。

## 8. 重试边界

### 允许有限安全补试

- curl无法解析主机/连接服务器（exit 5/6/7，且无HTTP状态，即连接未建立）；
- HTTP 429。

`max_safe_retries`是硬边界，只能是`0`或`1`：`0`表示不自动补试，`1`表示最多额外补试一次；任何更大值都会被配置校验拒绝。默认值为`1`，补试前默认等待30秒；两次均失败则停止整批。

curl进程本身无法启动（例如本机执行失败）属于本地`fatal/rejected`：请求未提交，但也不自动重试，应先修复本机环境。

### 503默认uncertain

HTTP 503不再自动补试，默认按`uncertain`处理：立即停止、记录request ID并对账，确认未扣费且用户明确授权后才可重提。

### 必须uncertain并停止

- curl进程超时；
- 上传后传输异常；
- 408、409、503及其他5xx；
- 2xx非JSON；
- 2xx缺少`data[0].b64_json`；
- Base64损坏。

request ID不是幂等键，不能防止重复扣费。

### rejected并停止

400/401/403/404/413/422及其他明确4xx。先修复，不要循环执行。

## 9. 输出验证

每次单测后必须检查：

1. `生成图/B增强方案/png/<任务>.png`存在且可解码；
2. JPG存在、RGB、progressive、由PNG生成；
3. PNG字节是模型返回的原始PNG；
4. 输出保持模型尺寸，不放大回原图；
5. checkpoint对应任务`succeeded`；
6. metadata含`transport: system-curl`；
7. 审阅页可打开；
8. 人工/视觉模型检查主体完整和背景保护。

## 10. A选择性调用

当前CLI没有`--task-id/--source/--card`筛选。不能为了一个任务直接对原日期目录全量运行A。临时做法：建立“A复检”目录，只复制需要复检的原图和色卡；注意仍然执行复检目录内笛卡尔积。运行前dry-run核对。

未来可增加精确筛选，但修改必须有测试且不改变完整manifest。

## 11. 停止条件

以下情况立即停止并向用户解释：

- uncertain；
- Key/权限错误；
- 连续空体503（按uncertain处理）；
- 输出不是PNG；
- checkpoint损坏；
- 输入在计划生成后被替换；
- 用户未确认预计付费调用数；
- 单任务结果尚未审阅；
- 发现错误主体、错误色卡或异常笛卡尔积。

## 12. 与用户沟通模板

执行前：

> 我先做离线检查，不会收费。识别到X张原图和Y张色卡，共X×Y个任务。默认B。随后只测试1个付费任务，成功后请你看结果，再决定是否全量。

成功后：

> 单任务已成功，request ID为……，PNG/JPG有效，耗时……。请重点查看……。你确认后我才继续剩余任务。

503后：

> 请求被网关以503拒绝，工具默认按uncertain处理并停止，没有自动补试，其余任务没有提交。不要反复运行；先按request ID对账，确认未扣费后再决定是否继续。

uncertain后：

> 请求可能已进入上游并可能计费，但结果未安全收到。我已停止整批。没有对该任务重提。需要先按request ID核对usage。
