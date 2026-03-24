# zh-ppt 技能

基于 banana-slides 和 Qwen-Image 的 PPT 自动生成技能，适用于 OpenClaw 平台。

## 元数据

```yaml
name: zh-ppt
version: 1.0.0
description: 从主题、参考文档或现有 PPT 生成完整幻灯片（大纲 + 描述 + 配图 + 导出）
author: Your Name
language: zh-CN
tags:
  - ppt
  - presentation
  - qwen-image
  - banana-slides
  - document-to-ppt
  - vibe-ppt
capabilities:
  - theme_to_ppt: 根据主题生成 PPT
  - document_to_ppt: 文档/参考材料转 PPT
  - ppt_refresh: PPT 翻新美化
  - generate_images: 根据页面描述生成配图
  - export_pptx: 导出标准 PPTX 文件
models:
  text: qwen-max                    # 大纲与描述生成
  image: qwen-image-2.0-pro         # 页面配图生成
  vision: qwen-vl-max               # 图片理解（可选）
runtime:
  python: ">=3.10"
  node: ">=18"
```

---

## 技能说明

本技能将本地 `banana-slides` 源码封装为 PPT 生产技能，实现"文档/一句话 → PPT"完整链路：

| 模块 | 职责 | 源码位置 |
|------|------|----------|
| **banana-slides** | PPT 结构规划、内容生成、页面排版 | `./banana-slides/` |
| **zh-ppt 技能** | 调用调度、生图、组装导出 | `./scripts/` |
| **Qwen-Image** | 根据页面描述生成高质量配图 | 阿里云百炼 API |

### 核心流程

```
用户请求 → 识别类型 → banana-slides 生成大纲/描述 → zh-ppt 调用 Qwen-Image 生图 → 组装 PPTX → 输出
```

---

## 源码映射

### banana-slides 核心模块

| 功能 | 源码路径 | 说明 |
|------|----------|------|
| 项目入口 | `./banana-slides/backend/app.py` | Flask 后端服务启动 |
| 工作流总控 | `./banana-slides/backend/controllers/project_controller.py` | 项目创建、大纲生成、描述生成 |
| 单页生成与改图 | `./banana-slides/backend/controllers/page_controller.py` | 单页内容编辑、图片替换 |
| 提示词中心 | `./banana-slides/backend/services/prompts.py` | 所有 AI 提示词模板 |
| AI 调度 | `./banana-slides/backend/services/ai_service.py` | 调用文本/图像/视觉模型 |
| 参考文档解析 | `./banana-slides/backend/services/file_parser_service.py` | PDF/Word/Markdown 解析 |
| 导出服务 | `./banana-slides/backend/controllers/export_controller.py` | PPTX/PDF 导出接口 |
| 导出实现 | `./banana-slides/backend/services/export_service.py` | PPTX 组装逻辑 |
| 前端流程编排 | `./banana-slides/frontend/src/store/useProjectStore.ts` | 前端状态管理（参考） |

### zh-ppt 技能模块

| 模块 | 源码路径 | 说明 |
|------|----------|------|
| 生图脚本 | `./scripts/generate.py` | 调用 Qwen-Image API 生成配图 |
| PPT 生成主脚本 | `./scripts/ppt_generator.py` | 整合 banana-slides 和生图流程 |
| 配置文件 | `./config.json` | API Key、模型、输出目录配置 |

---

## 调度规则

### 规则 1：主题生成 PPT

```
触发：用户给定主题/想法
流程:
  1. POST /api/projects (creationType=idea)
     → banana-slides 生成大纲
  2. POST /api/projects/{id}/descriptions
     → banana-slides 生成页面描述
  3. 调用 generate.py
     → Qwen-Image 为每页生成配图
  4. GET /api/projects/{id}/export
     → 组装 PPTX 输出
```

### 规则 2：文档转 PPT

```
触发：用户上传文档（PDF/Word/Markdown）+ "做成 PPT"
流程:
  1. POST /api/files (上传文档)
     → 获取 file_id
  2. POST /api/projects (creationType=document, referenceFileIds=[file_id])
     → banana-slides 解析文档并生成大纲
  3. POST /api/projects/{id}/descriptions
     → 生成页面描述
  4. 调用 generate.py
     → Qwen-Image 生成配图
  5. GET /api/projects/{id}/export
     → 组装 PPTX 输出
```

### 规则 3：PPT 翻新

```
触发：用户上传 PPT 文件 + "翻新/美化"
流程:
  1. POST /api/files (上传 PPT)
     → 获取 file_id
  2. POST /api/projects (creationType=ppt_refresh, referenceFileIds=[file_id])
     → banana-slides 解析原 PPT 并重新设计
  3. POST /api/projects/{id}/descriptions
     → 生成新页面描述
  4. 调用 generate.py
     → Qwen-Image 生成新配图
  5. GET /api/projects/{id}/export
     → 组装 PPTX 输出
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
    "ideaPrompt": "人工智能发展史",
    "creationType": "idea",
    "outlineRequirements": "包含发展历程、重要人物、未来趋势"
  }'

# 返回：{"id": 1, "status": "generating", ...}

# 3. 等待大纲生成完成（轮询）
curl http://localhost:15280/api/projects/1

# 4. 生成页面描述
curl -X POST http://localhost:15280/api/projects/1/descriptions

# 5. 等待描述生成完成
curl http://localhost:15280/api/projects/1
```

### 流程 2：调用 generate.py 生图

```bash
# 为每页生成配图
cd scripts

python generate.py \
  --prompt "人工智能发展历程的时间轴图表，科技感风格，蓝色调" \
  --model qwen-image-2.0-pro \
  --aspect-ratio 16:9 \
  --resolution 2K \
  --prefix page_1

# 输出：output/images/page_1_20250324_143025.png
```

### 流程 3：组装成标准 PPTX 文件

```bash
# 调用 banana-slides 导出接口
curl -X GET http://localhost:15280/api/projects/1/export \
  --output output/presentation.pptx
```

---

## 配置说明

### 配置同步

zh-ppt 的配置 (`config.json`) 和 banana-slides 的配置 (`.env` / 数据库) 是独立的。

**首次部署或更新配置时**，运行同步脚本：

```bash
cd zh-ppt/scripts
python sync_config.py
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
    "api_base": "http://localhost:5000",
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
├── ppt_20250324_143022.pptx      # 最终 PPT 文件
├── images/
│   ├── page_1_20250324_143025.png
│   ├── page_2_20250324_143030.png
│   └── ...
├── metadata.json                  # 项目元数据
└── logs/
    └── generation_20250324.log   # 生成日志
```

### metadata.json 格式

```json
{
  "project_id": 1,
  "theme": "人工智能发展史",
  "created_at": "2025-03-24T14:30:22Z",
  "page_count": 12,
  "images": [
    {"page": 1, "path": "images/page_1_...png", "prompt": "..."},
    {"page": 2, "path": "images/page_2_...png", "prompt": "..."}
  ],
  "pptx_path": "output/ppt_20250324_143022.pptx",
  "models_used": {
    "text": "qwen-max",
    "image": "qwen-image-2.0-pro"
  }
}
```

---

## 使用示例

### 示例 1：主题生成 PPT

**用户输入**：
```
帮我做一个关于"人工智能发展史"的 PPT，需要包含发展历程、重要人物和未来趋势
```

**技能响应**：
```
📊 正在生成 PPT...

1. ✓ 生成大纲（使用 qwen-max）
   - 第一部分：AI 起源（1950-1980）
   - 第二部分：机器学习时代（1980-2010）
   - 第三部分：深度学习革命（2010-至今）
   - 第四部分：未来趋势

2. ✓ 生成页面描述（12 页）

3. ✓ 生成配图（12 张，使用 qwen-image-2.0-pro）

4. ✓ 组装 PPTX 文件

✅ PPT 生成完成！
📁 文件位置：output/ppt_20250324_143022.pptx
🖼️ 配图数量：12 张
📄 页数：12 页
```

### 示例 2：文档转 PPT

**用户输入**：
```
[上传 quarterly_report.pdf]
把这个季度报告总结成 PPT，重点突出业绩增长和市场分析
```

**技能响应**：
```
📊 正在解析文档...

1. ✓ 解析 PDF 内容（3 页）

2. ✓ 提取关键信息生成大纲
   - Q1 业绩概览
   - 各业务线表现
   - 市场分析
   - Q2 展望

3. ✓ 生成页面描述和配图

✅ PPT 生成完成！
📁 文件位置：output/ppt_20250324_150045.pptx
```

### 示例 3：PPT 翻新

**用户输入**：
```
[上传 old_design.pptx]
帮我把这个 PPT 翻新一下，做得更现代、更简洁
```

**技能响应**：
```
📊 正在分析原 PPT...

1. ✓ 解析原有内容（8 页）

2. ✓ 保留核心内容，重新设计样式
   - 更新配色方案
   - 优化排版布局
   - 生成新配图

✅ PPT 翻新完成！
📁 文件位置：output/ppt_20250324_160030_refreshed.pptx
```

---

## 注意事项

### 1. API Key 配置
- 使用前请在 config.json 中配置 `QWEN_API_KEY`
- 获取 API Key：https://bailian.console.aliyun.com/

### 2. 网络要求
- 需要能够访问阿里云百炼 API
- banana-slides 服务需本地启动

### 3. 生成时间
- 大纲生成：约 10-30 秒
- 页面描述：约 5-15 秒/页
- 图片生成：约 10-30 秒/张
- 一个 12 页 PPT 总计约 5-10 分钟

### 4. 费用参考
| 模型 | 价格 | 说明 |
|------|------|------|
| qwen-max | ~0.04 元/千 tokens | 文本生成 |
| qwen-vl-max | ~0.03 元/千 tokens | 视觉理解 |
| qwen-image-2.0-pro | ~0.12 元/张 | 文生图 |

生成一个 12 页 PPT，预计费用约 2-5 元。

---

## 故障排除

### 问题 1：生图失败
**错误**：`Error generating image with Qwen-Image`
**解决**：
1. 检查 config.json 中的 api_key 是否正确
2. 确认网络连接正常
3. 查看 logs/ 目录下的日志

### 问题 2：banana-slides 服务无法连接
**解决**：
1. 确认后端服务已启动：`python banana-slides/backend/app.py`
2. 检查端口是否正确（默认 15280）
3. 查看 config.json 中的 api_base 配置

### 问题 3：图片质量不佳
**解决**：
1. 尝试使用 `qwen-image-2.0-pro` 模型
2. 在 prompt 中添加更详细的描述
3. 调整 resolution 参数为 2K 或 4K

---

## 许可证

本技能基于 banana-slides 项目改造，遵循原项目许可证。

---

## 更新日志

### v1.0.0 (2025-03-24)
- 初始版本
- 完整支持 Qwen 文本、视觉、图像模型
- 支持三种生成模式（主题/文档/翻新）
- OpenClaw 技能集成
- 源码映射清晰，边界明确
