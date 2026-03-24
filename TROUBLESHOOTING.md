# zh-ppt 技能 - 问题修复清单

## 已修复的问题

### 1. 配置路径问题
**问题**: `generate.py` 中 `resolve_settings()` 从错误的配置路径获取模型名称

**修复前**:
```python
'model': config.get('model') or ...
```

**修复后**:
```python
models_config = config.get('models', {})
'model': models_config.get('image') or ...
```

### 2. 日志路径问题
**问题**: `ppt_generator.py` 中使用相对路径 `'logs/ppt_generator.log'`，可能导致日志文件创建失败

**修复**: 使用绝对路径
```python
logs_dir = Path(__file__).parent.parent / 'logs'
logs_dir.mkdir(parents=True, exist_ok=True)
logging.FileHandler(logs_dir / 'ppt_generator.log', encoding='utf-8')
```

### 3. 脚本调用输出解析问题
**问题**: `ppt_generator.py` 调用 `generate.py` 时解析中文输出不可靠

**修复**: 添加 `--json` 参数，使用 JSON 格式输出
```python
cmd = [
    sys.executable,
    str(Path(__file__).parent / 'generate.py'),
    '--prompt', prompt,
    '--json',  # 使用 JSON 输出
]

# 解析 JSON 输出
for line in result.stdout.split('\n'):
    if line.startswith('JSON 输出：'):
        json_str = line.replace('JSON 输出：', '').strip()
        output = json.loads(json_str)
        image_path = output['path']
```

### 4. 缺少 image_prompt 时的降级处理
**问题**: 当页面缺少 `image_prompt` 时直接跳过

**修复**: 使用 `description` 作为备选 prompt
```python
if not prompt:
    description = page.get('description', '')
    if description:
        prompt = description[:200]
```

### 5. 导入语句位置问题
**问题**: `import subprocess` 和 `import requests` 在函数内部

**修复**: 移动到文件顶部

---

## 配置验证

### config.json 正确格式
```json
{
  "api_key": "YOUR_QWEN_API_KEY",
  "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "models": {
    "text": "qwen-max",
    "image": "qwen-image-2.0-pro",
    "vision": "qwen-vl-max"
  },
  "image_settings": {
    "aspect_ratio": "16:9",
    "resolution": "2K"
  },
  "output_dir": "./output",
  "banana_slides": {
    "api_base": "http://localhost:15280"
  }
}
```

**注意**: `models.image` 是正确路径，不是 `model`

### 配置同步

zh-ppt 和 banana-slides 的配置是独立的，需要手动同步：

```bash
# 自动同步配置
python scripts/sync_config.py

# 只检查配置，不同步
python scripts/sync_config.py --check
```

同步后，banana-slides 会自动使用 zh-ppt/config.json 中的配置。

---

## 依赖安装

### zh-ppt 技能依赖
```bash
cd zh-ppt
pip install -r requirements.txt
```

### banana-slides 依赖
```bash
cd zh-ppt/banana-slides
uv sync
# 或
pip install -e .
```

---

## 使用验证

### 1. 测试生图脚本
```bash
cd zh-ppt/scripts
python generate.py --prompt "测试图片" --json
```

期望输出:
```
JSON 输出：{"success": true, "model": "qwen-image-2.0-pro", "size": [2048, 1152], "path": "..."}
```

### 2. 测试 PPT 生成
```bash
cd zh-ppt/scripts
python ppt_generator.py --mode theme --prompt "测试 PPT" --verbose
```

### 3. 检查日志
```bash
cat zh-ppt/logs/ppt_generator.log
```

---

## 剩余注意事项

### 1. API Key 配置
使用前必须在 `config.json` 中配置有效的 Qwen API Key

### 2. banana-slides 服务
确保 banana-slides 后端服务已启动：
```bash
cd zh-ppt/banana-slides
python backend/app.py
# 默认端口：15280 (谐音"我要爱 PPT")
```

### 3. 网络要求
- 需要能够访问阿里云百炼 API
- 如遇网络问题，可配置代理

### 4. 端口配置
默认端口：15280 (谐音"我要爱 PPT")

如果 banana-slides 使用非默认端口，需要更新 `config.json`：
```json
{
  "banana_slides": {
    "api_base": "http://localhost:YOUR_PORT"
  }
}
```

---

## 文件清单

```
zh-ppt/
├── SKILL.md                     # OpenClaw 技能说明书
├── README.md                    # 使用说明
├── DEPLOY.md                    # 部署说明
├── TROUBLESHOOTING.md           # 问题修复清单（本文件）
├── requirements.txt             # Python 依赖
├── config.json                  # 配置文件
├── .gitignore
├── scripts/
│   ├── generate.py              # 生图脚本（已修复）
│   └── ppt_generator.py         # PPT 生成主脚本（已修复）
└── banana-slides/               # banana-slides 源码
```
