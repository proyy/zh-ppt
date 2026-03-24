# zh-ppt 技能 - 完整业务流程验证

## 流程总览

```
用户请求 → 识别类型 → 创建项目 → 生成大纲 → 生成描述 → 生成配图 → 导出 PPTX
```

---

## 1. 部署验证

### 1.1 检查目录结构

```bash
cd zh-ppt
ls -la
# 应包含：SKILL.md, README.md, config.json, scripts/, banana-slides/
```

### 1.2 检查配置文件

```bash
cat config.json
# 确认 api_key 已配置
# 确认 banana_slides.api_base = http://localhost:15280
```

### 1.3 同步配置

```bash
cd scripts
python sync_config.py
# 应输出：配置已同步到 banana-slides/.env
```

### 1.4 安装依赖

```bash
pip install -r requirements.txt
```

### 1.5 启动 banana-slides

```bash
cd ../banana-slides
python backend/app.py
# 应输出：Server starting on: http://localhost:15280
```

### 1.6 验证服务

```bash
curl http://localhost:15280/api/health
# 应返回：{"status": "ok"}
```

---

## 2. API 端点验证

### 2.1 创建项目

**请求**:
```bash
curl -X POST http://localhost:15280/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "idea_prompt": "测试 PPT",
    "creation_type": "idea"
  }'
```

**预期响应**:
```json
{
  "success": true,
  "data": {
    "project_id": "1",
    "status": "DRAFT",
    "pages": []
  }
}
```

**验证点**:
- ✅ 字段使用蛇形命名：`project_id`, `creation_type`, `idea_prompt`
- ✅ 返回 `project_id` 用于后续调用

---

### 2.2 生成大纲

**请求**:
```bash
curl -X POST http://localhost:15280/api/projects/1/generate/outline
```

**预期响应**:
```json
{
  "success": true,
  "data": {
    "task_id": "xxx-xxx-xxx",
    "status": "pending"
  }
}
```

**验证点**:
- ✅ 返回 `task_id` 用于轮询
- ✅ 后台任务开始执行

---

### 2.3 轮询任务状态

**请求**:
```bash
curl http://localhost:15280/api/projects/1/tasks/xxx-xxx-xxx
```

**预期响应**:
```json
{
  "success": true,
  "data": {
    "task_id": "xxx-xxx-xxx",
    "status": "completed",
    "result": {...}
  }
}
```

**状态流转**: `pending` → `running` → `completed`

---

### 2.4 获取项目（包含大纲）

**请求**:
```bash
curl http://localhost:15280/api/projects/1
```

**预期响应**:
```json
{
  "success": true,
  "data": {
    "id": "1",
    "idea_prompt": "测试 PPT",
    "outline_text": "1. 第一部分\n2. 第二部分...",
    "pages": [
      {"id": 1, "title": "...", "part": "..."},
      {"id": 2, "title": "...", "part": "..."}
    ]
  }
}
```

**验证点**:
- ✅ `pages` 数组包含大纲页面
- ✅ 每个页面有 `id`, `title`, `part` 字段

---

### 2.5 生成页面描述

**请求**:
```bash
curl -X POST http://localhost:15280/api/projects/1/generate/descriptions
```

**预期响应**:
```json
{
  "success": true,
  "data": {
    "task_id": "yyy-yyy-yyy",
    "status": "pending"
  }
}
```

**轮询任务状态**（同 2.3）

---

### 2.6 获取项目（包含描述）

**请求**:
```bash
curl http://localhost:15280/api/projects/1
```

**预期响应**:
```json
{
  "success": true,
  "data": {
    "id": "1",
    "pages": [
      {
        "id": 1,
        "title": "...",
        "description": "...",
        "image_prompt": "..."
      }
    ]
  }
}
```

**验证点**:
- ✅ 每个页面有 `description` 和 `image_prompt` 字段

---

### 2.7 导出 PPTX

**请求**:
```bash
curl -X GET http://localhost:15280/api/projects/1/export/pptx \
  --output test.pptx
```

**预期响应**:
- 二进制 PPTX 文件

**验证点**:
- ✅ 接口路径是 `/export/pptx`，不是 `/export`
- ✅ 返回可打开的 PPTX 文件

**注意**: 此接口需要页面有 `generated_image_path`

---

## 3. 完整流程验证（脚本）

### 3.1 主题生成 PPT

```bash
cd zh-ppt/scripts
python ppt_generator.py --mode theme --prompt "人工智能发展史" --verbose
```

**预期日志**:
```
PPT 生成器初始化完成...
开始从主题生成 PPT：人工智能发展史
步骤 1: 创建项目
项目创建成功，ID: 1
步骤 2: 生成大纲
大纲生成任务已提交，Task ID: xxx
任务状态：completed
步骤 3: 生成页面描述
描述生成任务已提交，Task ID: yyy
任务状态：completed
步骤 4: 生成配图
调用 Qwen-Image API...
图片已保存：...
步骤 5: 导出 PPTX
PPTX 已保存：...
步骤 6: 保存元数据
元数据已保存：...

============================================================
✅ PPT 生成完成！
============================================================
📁 PPT 文件：output/ppt_20250324_143022.pptx
🖼️ 配图数量：12 张
📄 页数：12 页
📋 元数据：output/metadata.json
============================================================
```

---

### 3.2 文档转 PPT

```bash
python ppt_generator.py --mode document --file test.pdf --verbose
```

**预期流程**:
1. 上传文件 → `/api/files` → 返回 `file_id`
2. 创建项目 → `reference_file_ids: [file_id]`
3. 后续同主题生成

---

### 3.3 PPT 翻新

```bash
python ppt_generator.py --mode refresh --file old.pptx --requirement "做得更现代" --verbose
```

---

## 4. 生图脚本验证

### 4.1 单独测试生图

```bash
python generate.py --prompt "一只可爱的卡通熊猫" --json
```

**预期输出**:
```
JSON 输出：{"success": true, "model": "qwen-image-2.0-pro", "size": [2048, 1152], "path": "output/images/page_...png"}
```

---

### 4.2 验证配置读取

```bash
# 1. 检查 config.json
cat ../config.json | jq .models.image

# 2. 检查 .env
cat ../banana-slides/.env | grep QWEN_API_KEY

# 3. 生图脚本应能从任一位置读取 API Key
```

---

## 5. 配置同步验证

### 5.1 测试同步

```bash
python sync_config.py --check
```

**预期输出**:
```
=== 预览 .env 内容 ===
AI_PROVIDER_FORMAT=qwen
QWEN_API_KEY=sk-...
TEXT_MODEL=qwen-max
IMAGE_MODEL=qwen-image-2.0-pro
...
=== 预览结束 ===
```

---

### 5.2 验证同步结果

```bash
# 1. 检查 .env 文件
cat ../banana-slides/.env

# 2. 重启 banana-slides
cd ../banana-slides
python backend/app.py

# 3. 检查设置 API
curl http://localhost:15280/api/settings
```

---

## 6. 常见问题排查

### 问题 1: 404 Not Found - /api/projects/1/export

**原因**: 接口路径错误，应该是 `/export/pptx`

**解决**: 已修复，见 `ppt_generator.py:253`

---

### 问题 2: 创建项目返回 400 Bad Request

**原因**: 字段命名错误（驼峰 vs 蛇形）

**解决**: 已修复，使用蛇形命名：
- `creation_type` ✅ (不是 `creationType`)
- `idea_prompt` ✅ (不是 `ideaPrompt`)
- `reference_file_ids` ✅ (不是 `referenceFileIds`)

---

### 问题 3: 任务状态一直是 pending

**原因**: 
1. banana-slides 后台任务未执行
2. 数据库配置不正确

**解决**:
```bash
# 检查日志
tail -f banana-slides/backend/logs/app.log

# 验证配置
python scripts/sync_config.py
```

---

### 问题 4: 生图失败 - API Key 无效

**原因**: API Key 未同步到 generate.py

**解决**: generate.py 现在支持从三个位置读取：
1. `config.json` → `api_key`
2. 环境变量 `QWEN_API_KEY`
3. `banana-slides/.env` → `QWEN_API_KEY`

---

## 7. 验收清单

### 部署验收
- [ ] config.json 配置正确
- [ ] 配置同步成功
- [ ] banana-slides 服务启动（端口 15280）
- [ ] 健康检查通过（/api/health）

### API 验收
- [ ] 创建项目（POST /api/projects）
- [ ] 生成大纲（POST /api/projects/{id}/generate/outline）
- [ ] 轮询任务（GET /api/projects/{id}/tasks/{task_id}）
- [ ] 获取项目（GET /api/projects/{id}）
- [ ] 生成描述（POST /api/projects/{id}/generate/descriptions）
- [ ] 导出 PPTX（GET /api/projects/{id}/export/pptx）

### 脚本验收
- [ ] 主题生成 PPT（--mode theme）
- [ ] 文档转 PPT（--mode document）
- [ ] PPT 翻新（--mode refresh）
- [ ] 单独生图（generate.py）

### 配置验收
- [ ] 配置同步（sync_config.py）
- [ ] API Key 多位置读取
- [ ] 端口配置（15280）

---

## 8. 性能基准

| 操作 | 预期时间 | 说明 |
|------|----------|------|
| 创建项目 | < 1 秒 | 数据库插入 |
| 生成大纲（10 页） | 10-30 秒 | Qwen-max |
| 生成描述（10 页） | 30-60 秒 | Qwen-max |
| 生成配图（10 张） | 100-300 秒 | Qwen-Image，10 秒/张 |
| 导出 PPTX | 5-10 秒 | 文件组装 |
| **总计（10 页）** | **3-7 分钟** | 完整流程 |

---

## 9. 更新日志

### v1.1.0 (2025-03-24)
- ✅ 修复 API 字段命名（驼峰 → 蛇形）
- ✅ 修复导出接口路径（/export → /export/pptx）
- ✅ 修复任务轮询逻辑（使用 task_id）
- ✅ 增强 API Key 读取（支持 3 个位置）
- ✅ 添加 python-dotenv 依赖
- ✅ 完善错误处理和日志输出
