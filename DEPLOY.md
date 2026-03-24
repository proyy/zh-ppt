# zh-ppt 项目部署说明

## 目录结构

```
zh-ppt/                          # 技能根目录（一级目录）
├── SKILL.md                     # OpenClaw 技能说明书
├── README.md                    # 使用说明
├── config.json                  # 配置文件
├── scripts/
│   ├── generate.py              # 生图脚本
│   ├── ppt_generator.py         # PPT 生成主脚本
│   └── requirements.txt         # 依赖
├── banana-slides/               # banana-slides 源码（二级目录）
├── output/                      # 输出目录
└── logs/                        # 日志目录
```

## 部署步骤

### 步骤 1：获取 banana-slides 源码

```bash
# 进入 zh-ppt 目录
cd zh-ppt

# 方式 1：从 GitHub 下载
git clone https://github.com/Anionex/banana-slides.git

# 方式 2：如果已在本地，复制过来
cp -r /path/to/your/banana-slides ./banana-slides
```

### 步骤 2：安装 banana-slides 依赖

```bash
cd banana-slides

# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 步骤 3：配置 API Key

编辑 `config.json`：

```json
{
  "api_key": "sk-your-qwen-api-key-here",
  "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "models": {
    "text": "qwen-max",
    "image": "qwen-image-2.0-pro"
  }
}
```

### 步骤 4：安装技能依赖

```bash
cd scripts
pip install -r requirements.txt
```

### 步骤 5：同步配置（推荐）

```bash
# 自动同步 zh-ppt/config.json 到 banana-slides/.env 和数据库
python scripts/sync_config.py
```

**注意**: 此步骤会自动配置 banana-slides 所需的所有环境变量，无需手动编辑 .env 文件。

### 步骤 6：配置环境变量（可选，手动配置）

创建 `.env` 文件（在 banana-slides 目录）：

```bash
# AI Provider 格式
AI_PROVIDER_FORMAT=qwen

# Qwen API 配置
QWEN_API_KEY=sk-your-api-key-here
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# 模型配置
TEXT_MODEL=qwen-max
IMAGE_MODEL=qwen-image-2.0-pro
IMAGE_CAPTION_MODEL=qwen-vl-max

# 端口配置（可选，默认 15280）
BACKEND_PORT=15280
```

### 步骤 7：启动服务

```bash
# 终端 1：启动 banana-slides 后端
# 默认端口：15280 (谐音"我要爱 PPT")
cd banana-slides
python backend/app.py

# 终端 2：运行 PPT 生成
cd zh-ppt/scripts
python ppt_generator.py --mode theme --prompt "人工智能发展史"
```

## 验证部署

### 检查 banana-slides 服务

```bash
# 默认端口 15280
curl http://localhost:15280/api/health
```

返回 `{"status": "ok"}` 表示服务正常。

### 检查生图脚本

```bash
python generate.py --prompt "测试图片" --model qwen-image-2.0-pro
```

成功生成图片表示配置正确。

### 完整测试

```bash
python ppt_generator.py --mode theme --prompt "测试 PPT" --verbose
```

## 常见问题

### 问题 1：找不到 banana-slides 模块

**解决**：
```bash
cd banana-slides
pip install -e .
```

### 问题 2：端口被占用

**解决**：修改 `.env` 中的 `BACKEND_PORT`，并更新 `config.json` 中的 `api_base`。

### 问题 3：生图失败

**解决**：
1. 检查 API Key 是否正确
2. 确认网络连接
3. 查看 `logs/` 目录日志

## OpenClaw 集成

将 `zh-ppt` 目录整体部署到 OpenClaw 技能目录，确保：
1. `SKILL.md` 在根目录
2. `banana-slides/` 子目录存在
3. `config.json` 已配置 API Key

## 更新 banana-slides

```bash
cd banana-slides
git pull origin main
```

然后重新安装依赖：
```bash
uv sync
```
