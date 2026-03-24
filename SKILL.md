# zh-ppt 技能

基于 banana-slides 和阿里云 Qwen 模型的 PPT 自动生成技能，适用于 OpenClaw 平台。

## 元数据

```yaml
name: zh-ppt
version: 1.3.0
description: 从主题、文档、大段文本或现有 PPT 生成完整幻灯片（智能分析 + 大纲 + 描述 + 配图 + 导出）
author: Your Name
language: zh-CN
tags:
  - ppt
  - presentation
  - qwen
  - qwen-image
  - banana-slides
  - document-to-ppt
  - vibe-ppt
  - auto-ppt
capabilities:
  - theme_to_ppt: 根据主题生成 PPT
  - document_to_ppt: 文档/参考材料转 PPT
  - ppt_refresh: PPT 翻新美化
  - text_to_ppt: 大段文本智能分析生成 PPT
  - generate_images: 根据页面描述生成配图（banana-slides 原生 API）
  - export_pptx: 导出标准 PPTX 文件
models:
  text: qwen-max                    # 大纲与描述生成、文本分析
  image: qwen-image-2.0-pro         # 页面配图生成
  vision: qwen-vl-max               # 图片理解（可选）
runtime:
  python: ">=3.10"
  node: ">=18"
```

---

## 技能说明

本技能将本地 `banana-slides` 源码封装为 PPT 生产技能，实现"文档/一句话/大段文本 → PPT"完整链路：

| 模块 | 职责 | 源码位置 |
|------|------|----------|
| **banana-slides** | PPT 结构规划、内容生成、页面排版、导出、图片生成 | `./banana-slides/` |
| **zh-ppt 技能** | 调用调度、智能分析、流程整合 | `./scripts/` |
| **Qwen 系列** | 文本分析、视觉理解、文生图 | 阿里云百炼 API |

### 核心流程

```
用户请求 → 识别类型 → 智能分析（可选）→ banana-slides 生成大纲/描述 
       → banana-slides 调用 Qwen-Image 生图 → 组装 PPTX → 输出
```

### 支持的生成模式

| 模式 | 输入 | 说明 |
|------|------|------|
| **theme** | 主题文字 | 根据简短主题生成 PPT |
| **document** | PDF/Word/Markdown 文件 | 从文档提取内容生成 PPT |
| **refresh** | PPTX 文件 | 翻新美化已有 PPT |
| **auto** | 大段文本/需求描述 | 智能分析文本后自动生成 |

---

## 源码映射

### banana-slides 核心模块

| 功能 | 源码路径 | 说明 |
|------|----------|------|
| 项目入口 | `./banana-slides/backend/app.py` | Flask 后端服务启动（默认端口 15280） |
| 工作流总控 | `./banana-slides/backend/controllers/project_controller.py` | 项目创建、大纲生成、描述生成 |
| 单页生成与改图 | `./banana-slides/backend/controllers/page_controller.py` | 单页内容编辑、图片生成 |
| 提示词中心 | `./banana-slides/backend/services/prompts.py` | 所有 AI 提示词模板 |
| AI 调度 | `./banana-slides/backend/services/ai_service.py` | 调用文本/图像/视觉模型 |
| 参考文档解析 | `./banana-slides/backend/services/file_parser_service.py` | PDF/Word/Markdown 解析 |
| 导出服务 | `./banana-slides/backend/controllers/export_controller.py` | PPTX/PDF 导出接口 |
| 导出实现 | `./banana-slides/backend/services/export_service.py` | PPTX 组装逻辑 |
| Qwen 文本支持 | `./banana-slides/backend/services/ai_providers/text/qwen_provider.py` | Qwen 文本模型 Provider |
| Qwen 图像支持 | `./banana-slides/backend/services/ai_providers/image/qwen_provider.py` | Qwen 文生图 Provider（multimodal-generation API） |

### zh-ppt 技能模块

| 模块 | 源码路径 | 说明 |
|------|----------|------|
| PPT 生成主脚本 | `./scripts/ppt_generator.py` | 整合 banana-slides 流程，支持 4 种模式 |
| 配置同步脚本 | `./scripts/sync_config.py` | 同步配置到 banana-slides .env 和数据库 |
| 数据库初始化 | `./scripts/init_db.py` | 首次运行时创建数据库表 |
| 独立生图脚本 | `./scripts/generate.py` | 单独调用 Qwen-Image API 生成配图（可选） |
| 配置文件 | `./config.json` | API Key、模型、输出目录配置 |

---

## 调度规则

### 规则 1：主题生成 PPT

```
触发：用户给定简短主题/想法
流程:
  1. POST /api/projects (creation_type=idea, idea_prompt="主题", outline_requirements="要求")
     → banana-slides 创建项目
  2. POST /api/projects/{id}/generate/outline
     → 触发后台任务生成大纲
  3. GET /api/projects/{id}/tasks/{task_id} (轮询)
     → 等待大纲完成（状态：COMPLETED）
  4. GET /api/projects/{id}
     → 获取大纲结果
  5. POST /api/projects/{id}/generate/descriptions
     → 生成页面描述
  6. 轮询任务状态 → 等待描述完成
  7. GET /api/projects/{id}
     → 获取描述结果
  8. POST /api/projects/{id}/pages/{page_id}/generate/image (每页)
     → banana-slides 调用 Qwen-Image 生成配图
  9. GET /api/projects/{id}/export/pptx
     → 导出 PPTX（图片路径已保存到数据库）
```

### 规则 2：文档转 PPT

```
触发：用户上传文档（PDF/Word/Markdown）+ "做成 PPT"
流程:
  1. POST /api/reference-files/upload (上传文档)
     → 获取 file_id
  2. POST /api/projects (creation_type=idea, reference_file_ids=[file_id], outline_requirements="要求")
     → banana-slides 解析文档并生成大纲
  3. 后续流程同规则 1
```

### 规则 3：PPT 翻新

```
触发：用户上传 PPT 文件 + "翻新/美化"
流程:
  1. POST /api/reference-files/upload (上传 PPT)
     → 获取 file_id
  2. POST /api/projects (creation_type=idea, reference_file_ids=[file_id], outline_requirements="要求")
     → banana-slides 解析原 PPT 并重新设计
  3. 后续流程同规则 1
```

### 规则 4：大段文本智能分析生成

```
触发：用户提供大段文本需求描述
流程:
  1. 调用 Qwen 文本模型分析文本（qwen-max）
     → 提取主题（theme）
     → 提取详细要求（detailed_requirements）
     → 提取风格要求（style_requirements）
     → 提取关键要点（key_points）
     → 提取必须包含内容（must_include）
     → 建议页数（page_count）
     → 判断生成模式（mode: theme/document）
  2. 合并要求为 outline_requirements
  3. 根据分析结果调用相应模式
     → 主题生成 或 文档转 PPT
  4. 后续流程同规则 1/2
```

---

## 触发条件

### 条件 1：给定主题生成 PPT

**触发关键词**：
- "做一个 PPT"
- "生成幻灯片"
- "做个演示文稿"
- "关于 XX 的 PPT"
- "帮我做 PPT"

**示例**：
```
用户：帮我做一个关于"人工智能发展史"的 PPT
用户：生成一个产品介绍幻灯片
用户：关于气候变化的演示文稿
```

### 条件 2：文档资料总结为 PPT

**触发条件**：
- 用户上传文档（PDF/Word/Markdown/TXT）
- 用户要求"总结为 PPT"、"做成幻灯片"、"生成 PPT"

**示例**：
```
用户：[上传 report.pdf] 把这个报告做成 PPT
用户：[上传 notes.md] 总结这些笔记生成幻灯片
用户：[上传 whitepaper.docx] 把这个白皮书总结成 PPT
```

### 条件 3：PPT 翻新美化

**触发条件**：
- 用户上传已有 PPT 文件
- 用户要求"翻新"、"美化"、"重新设计"、"做得更现代"

**示例**：
```
用户：[上传 old.pptx] 帮我把这个 PPT 美化一下
用户：[上传 draft.pptx] 重新设计这个幻灯片，做得更简洁
用户：[上传 quarterly.pptx] 翻新这个季度汇报 PPT
```

### 条件 4：大段文本智能分析

**触发条件**：
- 用户提供大段文本需求描述
- 用户要求"根据以下内容生成 PPT"、"分析这个需求做 PPT"

**示例**：
```
用户：我需要做一个产品发布 PPT，包含以下部分：
     1. 产品介绍：我们的新产品是一款 AI 助手
     2. 功能特点：支持多轮对话、知识问答、代码生成
     3. 市场分析：目标用户是企业客户
     4. 竞争优势：相比竞品有更好的性价比
     大概需要 15 页左右，风格要科技感强一些

用户：[上传 requirements.txt] 根据这个需求文档生成 PPT
```

---

## 调用流程

### 流程 1：调用 banana-slides 生成 PPT 大纲与内容

```bash
# 1. 启动 banana-slides 后端服务
cd ./banana-slides
python backend/app.py
# 默认端口：15280 (谐音"我要爱 PPT")

# 2. 创建项目（生成大纲）
curl -X POST http://localhost:15280/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "idea_prompt": "人工智能发展史",
    "creation_type": "idea",
    "outline_requirements": "包含发展历程、重要人物、未来趋势"
  }'

# 返回：{"success": true, "data": {"project_id": "uuid", "status": "DRAFT"}}

# 3. 生成大纲（触发后台任务）
curl -X POST http://localhost:15280/api/projects/{project_id}/generate/outline \
  -H "Content-Type: application/json" \
  -d '{}'

# 返回：{"success": true, "data": {"task_id": "uuid", "status": "PENDING"}}

# 4. 轮询任务状态
curl http://localhost:15280/api/projects/{project_id}/tasks/{task_id}

# 5. 生成页面描述
curl -X POST http://localhost:15280/api/projects/{project_id}/generate/descriptions \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 流程 2：调用 banana-slides 原生 API 生成配图

```bash
# 为每页生成配图（使用 banana-slides 原生 API）
curl -X POST http://localhost:15280/api/projects/{project_id}/pages/{page_id}/generate/image \
  -H "Content-Type: application/json" \
  -d '{
    "use_template": false,
    "force_regenerate": true,
    "style_description": "科技感风格，蓝色调"
  }'

# 返回：{"success": true, "data": {"page_id": "uuid", "generated_image_path": "/files/.../page_xxx.png"}}
# 图片路径自动保存到数据库，导出时可直接使用
```

### 流程 3：导出 PPTX

```bash
# 调用 banana-slides 导出接口
curl -X GET http://localhost:15280/api/projects/{project_id}/export/pptx \
  --output output/presentation.pptx
```

---

## 配置说明

### 配置同步

zh-ppt 的配置 (`config.json`) 和 banana-slides 的配置 (`.env` / 数据库) 是独立的。

**首次部署或更新配置时**，运行同步脚本：

```bash
cd scripts
python scripts/sync_config.py
```

这会自动将 `config.json` 同步到：
- `banana-slides/.env` 文件
- banana-slides 数据库 settings 表（通过 API）

### config.json

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
    "api_base": "http://localhost:15280",
    "timeout": 300
  }
}
```

### 配置项说明

| 配置项 | 说明 | 必填 | 默认值 |
|--------|------|------|--------|
| `api_key` | Qwen API Key（阿里云百炼） | 是 | - |
| `api_url` | Qwen API 地址 | 否 | 阿里云百炼地址 |
| `models.text` | 文本生成模型 | 否 | qwen-max |
| `models.image` | 文生图模型 | 否 | qwen-image-2.0-pro |
| `models.vision` | 视觉理解模型 | 否 | qwen-vl-max |
| `image_settings.aspect_ratio` | 图片比例 | 否 | 16:9 |
| `image_settings.resolution` | 图片分辨率 | 否 | 2K |
| `output_dir` | 输出目录 | 否 | ./output |
| `banana_slides.api_base` | banana-slides API 地址 | 否 | http://localhost:15280 |

---

## 输出说明

### 目录结构

```
output/
├── ppt_20260324_143022.pptx      # 最终 PPT 文件
├── images/
│   ├── page_1_20260324_143025.png
│   ├── page_2_20260324_143030.png
│   └── ...
├── metadata.json                  # 项目元数据
└── logs/
    └── ppt_generator.log         # 生成日志
```

### metadata.json 格式

```json
{
  "project_id": "uuid",
  "theme": "人工智能发展史",
  "created_at": "2026-03-24T14:30:22",
  "page_count": 12,
  "images": [
    {"page": 1, "path": "images/page_1_...png", "prompt": "..."},
    {"page": 2, "path": "images/page_2_...png", "prompt": "..."}
  ],
  "pptx_path": "output/ppt_20260324_143022.pptx",
  "models_used": {
    "text": "qwen-max",
    "image": "qwen-image-2.0-pro"
  }
}
```

---

## 使用示例

### 示例 1：主题生成 PPT

**命令行**:
```bash
python scripts/ppt_generator.py --mode theme \
  --prompt "人工智能发展史" \
  --requirement "包含发展历程、重要人物、未来趋势"
```

**技能响应**:
```
📊 正在生成 PPT...

1. ✓ 创建项目
2. ✓ 生成大纲（使用 qwen-max）
   - 第一部分：AI 起源（1950-1980）
   - 第二部分：机器学习时代（1980-2010）
   - 第三部分：深度学习革命（2010-至今）
   - 第四部分：未来趋势

3. ✓ 生成页面描述（12 页）

4. ✓ 生成配图（12 张，使用 banana-slides 原生 API + qwen-image-2.0-pro）

5. ✓ 导出 PPTX 文件

============================================================
✅ PPT 生成完成！
============================================================
📁 PPT 文件：output/ppt_20260324_143022.pptx
🖼️ 配图数量：12 张
📄 页数：12 页
📋 元数据：output/metadata.json
============================================================
```

### 示例 2：文档转 PPT

**命令行**:
```bash
python scripts/ppt_generator.py --mode document \
  --file quarterly_report.pdf \
  --requirement "重点突出业绩增长和市场分析"
```

**技能响应**:
```
📊 正在解析文档...

1. ✓ 上传文件
2. ✓ 创建项目
3. ✓ 生成大纲
4. ✓ 生成页面描述和配图

============================================================
✅ PPT 生成完成！
============================================================
📁 PPT 文件：output/ppt_20260324_150045.pptx
🖼️ 配图数量：10 张
📄 页数：10 页
============================================================
```

### 示例 3：大段文本智能分析生成

**命令行**:
```bash
python scripts/ppt_generator.py --mode auto \
  --text "我需要做一个产品发布 PPT，包含以下部分：
         1. 产品介绍：我们的新产品是一款 AI 助手
         2. 功能特点：支持多轮对话、知识问答、代码生成
         3. 市场分析：目标用户是企业客户
         4. 竞争优势：相比竞品有更好的性价比
         大概需要 15 页左右，风格要科技感强一些"
```

**技能响应**:
```
📊 正在分析文本内容，提取主题和要求...
📊 文本分析完成：
   - 主题：产品发布 PPT - AI 助手
   - 风格要求：科技感强一些
   - 模式：theme
   - 建议页数：15 页

📊 开始从主题生成 PPT...
...（后续流程同示例 1）

============================================================
✅ PPT 生成完成！
============================================================
📁 PPT 文件：output/ppt_20260324_160030.pptx
🖼️ 配图数量：15 张
📄 页数：15 页

📊 智能分析结果:
   主题：产品发布 PPT - AI 助手
   模式：theme
   原文长度：156 字符
   风格要求：科技感强一些
============================================================
```

### 示例 4：从文件读取大段文本

**命令行**:
```bash
python scripts/ppt_generator.py --mode auto \
  --text-file requirements.txt
```

---

## 注意事项

### 0. 首次部署流程

**重要**: 首次运行需要完成以下步骤：

```bash
# 1. 克隆仓库（包含子模块）
git clone --recursive https://github.com/proyy/zh-ppt.git
cd zh-ppt

# 2. 配置 API Key
编辑 config.json，填入 QWEN_API_KEY

# 3. 安装依赖
pip install -r requirements.txt

# 4. 同步配置到 banana-slides
python scripts/sync_config.py

# 5. 初始化数据库（首次运行必需）
python scripts/init_db.py

# 6. 启动 banana-slides 服务
cd banana-slides && python backend/app.py

# 7. 生成 PPT（新终端）
python scripts/ppt_generator.py --mode theme --prompt "人工智能发展史"
```

### 1. API Key 配置
- 使用前请在 config.json 中配置 `QWEN_API_KEY`
- 获取 API Key：https://bailian.console.aliyun.com/

### 2. 网络要求
- 需要能够访问阿里云百炼 API
- banana-slides 服务需本地启动

### 3. 生成时间
- 文本分析：约 5-10 秒（auto 模式）
- 大纲生成：约 10-30 秒
- 页面描述：约 5-15 秒/页
- 图片生成：约 10-30 秒/张（使用 banana-slides 原生 API）
- 一个 12 页 PPT 总计约 5-10 分钟

### 4. 费用参考
| 模型 | 价格 | 说明 |
|------|------|------|
| qwen-max | ~0.04 元/千 tokens | 文本生成、分析 |
| qwen-vl-max | ~0.03 元/千 tokens | 视觉理解 |
| qwen-image-2.0-pro | ~0.12 元/张 | 文生图 |

生成一个 12 页 PPT，预计费用约 2-5 元。

---

## 故障排除

### 问题 0：数据库表不存在

**错误**: `sqlite3.OperationalError: no such table: settings` 或 `no such table: projects`

**原因**: 首次运行时数据库未初始化

**解决**:
```bash
python scripts/init_db.py
```

### 问题 1：生图失败

**错误**: `Error generating image with Qwen-Image` 或 `NotFoundError: Error code: 404`

**解决**:
1. 检查 config.json 中的 api_key 是否正确
2. 确认网络连接正常
3. 查看 logs/ppt_generator.log 日志
4. 确认 banana-slides 已正确配置 QWEN_API_KEY（运行 sync_config.py）
5. 确认使用的是正确的 API 端点（multimodal-generation）

### 问题 2：配置同步失败

**错误**: `API 同步失败：500 - no such table: settings`

**原因**: 数据库未初始化或 banana-slides 服务未启动

**解决**:
1. 运行 `python scripts/init_db.py` 初始化数据库
2. 启动 banana-slides 服务：`cd banana-slides && python backend/app.py`
3. 重新运行同步：`python scripts/sync_config.py`

### 问题 3：banana-slides 服务无法连接

**解决**:
1. 确认后端服务已启动：`cd banana-slides && python backend/app.py`
2. 检查端口是否正确（默认 15280）
3. 查看 config.json 中的 api_base 配置
4. 查看 banana-slides 日志确认服务正常

### 问题 4：图片质量不佳

**解决**:
1. 尝试使用 `qwen-image-2.0-pro` 模型
2. 在 prompt 中添加更详细的描述
3. 调整 resolution 参数为 2K
4. 开启 prompt_extend（已默认开启）

### 问题 5：子模块为空

**错误**: `banana-slides/` 目录为空或缺少文件

**原因**: 克隆时未使用 `--recursive` 参数

**解决**:
```bash
# 方式 1：初始化子模块
git submodule update --init --recursive

# 方式 2：重新克隆
git clone --recursive https://github.com/proyy/zh-ppt.git
```

### 问题 6：auto 模式文本分析失败

**错误**: 文本分析失败，使用原文本作为主题

**原因**: Qwen 文本模型调用失败或 JSON 解析失败

**解决**:
1. 检查 config.json 中的 api_key 是否正确
2. 确认文本长度不超过 8000 字符（会自动分段）
3. 查看日志了解具体错误原因
4. 手动使用 theme 模式并提供明确的主题

### 问题 7：导出 PPTX 失败（400 错误）

**错误**: `400 Client Error: BAD REQUEST for url: .../export/pptx`

**原因**: 页面缺少 generated_image_path（图片未生成）

**解决**:
1. 确认图片生成步骤已完成
2. 检查 banana-slides 日志确认图片生成成功
3. 确认 style_description 参数已提供（banana-slides 需要）
4. 使用 banana-slides 原生 API 生成图片（已默认使用）

---

## 许可证

本技能基于 banana-slides 项目改造，遵循原项目许可证。

---

## 更新日志

### v1.3.0 (2026-03-24)
- **修复**：使用 banana-slides 原生 API 生成页面图片
- **修复**：auto 模式风格要求正确传递给图片生成 API
- **修复**：从 requirements 中提取 style_description
- **修复**：_continue_generation 传递 requirements 参数
- **优化**：图片生成成功后自动保存到数据库
- **优化**：导出 PPTX 时可正确找到图片路径

### v1.2.0 (2026-03-24)
- **新增 auto 模式**：支持大段文本智能分析生成 PPT
- **新增 generate_from_text()**：使用 Qwen 文本模型分析文本提取主题和要求
- **新增 --text 和 --text-file 参数**：支持直接输入或从文件读取文本
- 更新 SKILL.md 添加 auto 模式说明和示例
- 更新 print_result 显示智能分析结果

### v1.1.0 (2026-03-24)
- 添加数据库初始化脚本 `scripts/init_db.py`
- 修正 config.json 加载路径为仓库根目录
- 修复 _call_banana_api 自动提取 data 字段
- 修复 POST 请求发送空 JSON 对象避免 400 错误
- 修复任务状态检查使用大写比较
- 修复 description_content 提取 prompt 逻辑
- 使用阿里云百炼 multimodal-generation API
- 更新故障排除章节（数据库初始化、配置同步、生图 API）
- 完善首次部署流程说明

### v1.0.0 (2026-03-24)
- 初始版本
- 完整支持 Qwen 文本、视觉、图像模型
- 支持三种生成模式（主题/文档/翻新）
- OpenClaw 技能集成
- 源码映射清晰，边界明确
