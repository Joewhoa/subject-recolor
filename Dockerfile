# 基础镜像：Python 3.11（项目声明的最低版本，不擅自升级）。
# 用 -slim 变体：体积小、攻击面小；Pillow 的 wheel 自带图像编解码库，不需要额外系统包。
FROM python:3.11-slim

# 容器内路径固定，不依赖运行时所在目录。
WORKDIR /app

# 只声明「非敏感、且有安全默认值」的环境变量。
# IMAGE_API_KEY 故意不在这里声明——它必须由运行时注入（docker run -e），绝不能进镜像层。
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    IMAGE_API_BASE_URL="" \
    IMAGE_MODEL="gpt-image-2"

# ═══════════════════════════════════════════════════════════════
# 第一段：装「依赖 + 构建工具」（慢，要联网）—— 放最前面
#
# 下面这条命令做两件事：从 pyproject.toml 读出依赖清单 → 装它们（顺带装构建工具 hatchling）。
# 为什么不直接 pip install . ？因为那样必须先把 src/ 拷进来，
# 于是「改一行代码」就会连带触发「重装所有依赖」。
# 依赖从 pyproject.toml 动态读，避免把清单抄第二遍（保持单一真相源）。
#
# 只要 pyproject.toml 没变，这一层就一直复用 —— 这就是优化的全部秘密。
# ═══════════════════════════════════════════════════════════════
COPY pyproject.toml README.md ./
RUN python -c "import tomllib,subprocess,sys; \
    d=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; \
    subprocess.check_call([sys.executable,'-m','pip','install','--no-cache-dir','hatchling',*d])"

# ═══════════════════════════════════════════════════════════════
# 第二段：装「这个项目自己」（快，不用联网）—— 放最后
#
# 改代码只会让这一段失效，而它不需要联网：
#   --no-deps             依赖上一段已经装好了，不用再检查
#   --no-build-isolation  构建工具上一段已经装好了，不用再临时下载
# 所以这一段通常只要几秒。
# ═══════════════════════════════════════════════════════════════
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps --no-build-isolation .

# 这是命令行工具、不是常驻服务：
# 用 ENTRYPOINT（exec 形式）把「镜像本身」变成一个命令，子命令作为参数传入。
# 它不开端口，所以没有 EXPOSE。
ENTRYPOINT ["subject-recolor"]
