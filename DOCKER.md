# 在容器里跑 subject-recolor

> 这份手册是**操作步骤**，跟着敲就行。想理解每一步"为什么"，看文末「原理速查」。

## 前置条件

| 需要什么 | 怎么确认 |
|---|---|
| Docker Desktop 已安装并**正在运行** | 右下角鲸鱼图标稳定不转圈；`docker info` 不报错 |
| WSL2（Windows 上 Docker 的依赖） | 装 Docker Desktop 时若提示，跑 `wsl --install` 然后重启 |

**命令都在 PowerShell 里敲**（不是 WSL 里）。

**先约定一个变量**（下面所有命令都用它）——把路径换成你 clone 下来的实际位置：

```powershell
$proj = "D:\code\subject-recolor"
```

---

## 一、构建镜像

```powershell
cd $proj

# ⚠️ 末尾那个点「.」不能漏！它是"构建上下文路径"= 当前目录。
#    漏了会报：'docker buildx build' requires 1 argument
docker build -t subject-recolor:0.1.0 .
#                                    ↑
#                              就是这个点
```

**语法**：`docker build -t <镜像名> <构建上下文路径>`
—— 最后那个参数告诉 Docker「**去哪儿找要拷进镜像的文件**」，`.` 就是当前目录。

**看什么**：最后出现 `naming to docker.io/library/subject-recolor:0.1.0 done` 就是成功。
**耗时**：首次约 **40 秒**（要联网装依赖）。

确认一下：

```powershell
docker images subject-recolor
# 应该看到：subject-recolor:0.1.0   约 225MB
```

---

## 二、跑离线 demo 验证（**不用密钥、不花钱**）

```powershell
docker run --rm `
  -v "$proj\demo-workspace:/app/workspace" `
  subject-recolor:0.1.0 demo
```

> PowerShell 里的 `` ` `` 是换行符。嫌麻烦就写成一行。

**预期输出**：

```
workspace/2026-01-15/output/review.html
Offline deterministic demo complete; outputs are not AI-generated.
```

**去这儿看产物**（容器写出来的东西都在这儿）：

```
demo-workspace\2026-01-15\
├── input\          原图（程序自己画的合成图）
├── color_cards\    色卡
└── output\
    ├── review.html       ← 双击用浏览器打开
    ├── png\  jpg\        换色结果
    └── run.jsonl         执行账本
```

> ⚠️ **review.html 一定要用浏览器直接打开**（双击）。
> 原图/色卡用的是 `../` 相对路径，用"预览面板"之类只服务单个目录的工具会显示裂图。

---

## 三、验证「改代码不用重装依赖」这个优化

这一步是让你**亲眼看到分层缓存的效果**（也是这份 Dockerfile 最值得讲的地方）。

```powershell
cd $proj

# 随便改一下源码（加一行注释，无副作用）
Add-Content "src\subject_recolor\__init__.py" "`n# 测一下缓存"

# 再构建一次，注意看耗时（末尾的「.」同样不能漏）
docker build -t subject-recolor:0.1.0 .
```

**应该看到**（关键在这几行）：

```
#6 [2/6] WORKDIR /app                    CACHED
#7 [3/6] COPY pyproject.toml README.md   CACHED
#8 [4/6] RUN python -c "...装依赖..."     CACHED     ← 依赖层被复用，没重装
#9 [5/6] COPY src/ ./src/                DONE 0.1s
#10 [6/6] RUN pip install --no-deps ...  DONE 6.3s
```

**耗时应该从 40 秒掉到 8 秒左右。**

> **对比**：如果按"不优化"的写法（先 COPY 代码再装依赖），改一行代码就会让
> `RUN pip install .` 整层失效——实测**要 67 秒**。
> **改代码重建：67 秒 → 8.4 秒。**

测完把那行注释删掉即可。

---

## 四、跑真实换色（**需要密钥，会花钱**）

```powershell
# 密钥从运行环境注入，不写进镜像
$env:IMAGE_API_BASE_URL = "https://你的网关/v1"
$env:IMAGE_API_KEY = "你的密钥"

# 先建任务
docker run --rm -v "$proj\workspace:/app/workspace" `
  subject-recolor:0.1.0 init --date 2026-10-08 --subject 沙发

# 把原图放进 workspace\2026-10-08\input\，色卡放进 color_cards\

# 预检：先看要调几次（免费）
docker run --rm -v "$proj\workspace:/app/workspace" `
  subject-recolor:0.1.0 plan --date 2026-10-08 --json

# 确认后再真跑
docker run --rm -e IMAGE_API_KEY -e IMAGE_API_BASE_URL `
  -v "$proj\workspace:/app/workspace" `
  subject-recolor:0.1.0 run --date 2026-10-08 --expect-calls 1 --yes
```

> **`-e IMAGE_API_KEY`（不带 `=值`）** 的写法：Docker 会从你当前 PowerShell 环境里取，
> 这样密钥**不会留在命令历史里**。

---

## 五、常用命令速查

```powershell
docker images                    # 有哪些镜像
docker ps                        # 正在跑的容器
docker ps -a                     # 所有容器（含已停的）
docker system df                 # 占了多少磁盘
docker system prune              # 清理没用的（省磁盘）

docker run --rm <镜像> <子命令>   # 跑一次就删（最常用）
docker run --rm subject-recolor:0.1.0 --help          # 看有哪些子命令
docker run --rm -it --entrypoint bash subject-recolor:0.1.0   # 钻进容器里看
```

**这个镜像有 7 个子命令**：`init` / `plan` / `run` / `review` / `evaluate` / `doctor` / `demo`

**删镜像**：

```powershell
docker rmi subject-recolor:0.1.0
```

---

## 六、遇到问题

### 构建时报 `Bad Gateway` / 拉不到镜像

多半是**代理或 IPv6** 的问题（国内常见）：

```powershell
# 1. 临时清掉代理变量（注意：必须用「赋值」，Remove-Item 删不掉）
$env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; $env:http_proxy=""; $env:https_proxy=""

# 2. 如果还报 dial tcp [IPv6...] 超时，从国内源预拉基础镜像
docker pull docker.m.daocloud.io/library/python:3.11-slim
docker tag  docker.m.daocloud.io/library/python:3.11-slim python:3.11-slim
# 然后再 docker build
```

### 构建时提示 `failed to connect to the docker API`

**Docker Desktop 没启动**。点开它，等鲸鱼图标稳定。

### 报 `'docker buildx build' requires 1 argument`

**漏了末尾的 `.`**（构建上下文路径）。完整写法：

```powershell
docker build -t subject-recolor:0.1.0 .
```

### 跑完容器，发现产物"不见了"

看你是不是忘了 `-v`。**没挂 volume 的话，容器一删，里面的东西全没了。**

---

## 原理速查（为什么这么写）

| 写法 | 为什么 |
|---|---|
| `FROM python:3.11-slim` | 写死版本不用 `latest`；3.11 是项目声明的最低版本；Pillow 有预编译 wheel，slim 够用 |
| 只 `COPY` 三样（白名单） | **镜像层里的东西删不掉**，`COPY . .` 漏一个就是永久泄露 |
| 分两段装依赖 | 让"装依赖"单独成层，改代码时它能整层复用 |
| 不声明 `IMAGE_API_KEY` | 密钥烘进层里就跟着镜像走，必须运行时用 `-e` 注入 |
| `ENTRYPOINT` 而非 `CMD` | 这是命令行工具，镜像本身就是那个命令 |
| 没有 `EXPOSE` | CLI 工具不开端口 |
| 不写 `VOLUME` 指令 | 让用户用 `-v` 显式挂，行为更可控 |
| **没加非 root 用户** | 容器要往挂载目录写输出，非 root 在挂载卷上常没权限。**上生产应该补**（这是已知取舍，不是遗漏） |

---

_本手册中的命令均已在 Windows 11 + Docker Desktop 29.8.2（WSL2 后端）实测通过。_
